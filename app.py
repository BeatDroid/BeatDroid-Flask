import os
import dotenv
import logging
import base64
import blurhash
import numpy as np
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flasgger import Swagger
from poster import Poster
from BeatPrints import lyrics
from PIL import Image
import spotify  # Change to this import

# Load environment variables
dotenv.load_dotenv()
 
# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Flask app setup
app = Flask(__name__)

# Simple CORS headers without external dependency
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

app.after_request(add_cors_headers)
@app.before_request
def log_request_info():
    """Log details of every incoming request"""
    logging.info(f"Request Method: {request.method}")
    logging.info(f"Request URL: {request.url}")
    logging.info(f"Request Headers: {dict(request.headers)}")
    if request.is_json:
        logging.info(f"Request JSON Body: {request.get_json()}")
    else:
        logging.info("Request Body: Not JSON or empty")

# Configuration
app.config.update({
    "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY", "super-secret"),
    "SQLALCHEMY_DATABASE_URI": "sqlite:///devices.db",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "JWT_ACCESS_TOKEN_EXPIRES": False,  # Token never expires
    "RATELIMIT_STORAGE_URI": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "CACHE_TYPE": "redis",
    "CACHE_REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/1"),
    "DOWNLOAD_DIR": os.getenv("DOWNLOAD_DIR", "/tmp/beatprints_downloads"),
    'SQLALCHEMY_ECHO' : False

})

# Ensure download directories exist
download_dir = app.config['DOWNLOAD_DIR']
os.makedirs(os.path.join(download_dir, 'albums'), exist_ok=True)
os.makedirs(os.path.join(download_dir, 'tracks'), exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["10000 per hour"])
cache = Cache(app)
swagger = Swagger(app)

# Device model
class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(255), unique=True, nullable=False)
    token = db.Column(db.String(1024), nullable=False)

# Create the database tables
with app.app_context():
    db.create_all()

# Business logic components
ly = lyrics.Lyrics()
ps = Poster(app.config['DOWNLOAD_DIR'])
sp = spotify.Spotify(
    os.getenv("SPOTIFY_CLIENT_ID"),
    os.getenv("SPOTIFY_CLIENT_SECRET")
)

# --------- Authentication ---------
@app.route('/api/v1/auth/login', methods=['POST', 'OPTIONS'])
def login():
    """Authenticate and return JWT token based on device ID"""
    if request.method == 'OPTIONS':
        return '', 204

    # Get the device ID from the request
    data = request.get_json() or {}
    device_id = data.get('device_id')

    # Validate the device ID
    if not device_id:
        return jsonify(error="Missing device_id"), 400

    # Check if the device ID already exists in the database
    device = Device.query.filter_by(device_id=device_id).first()

    if device:
        # If the device exists, return the existing token
        logging.info(f"Device {device_id} already existss. Returning existing token.")
        return jsonify(access_token=device.token), 200
    else:
        # If the device does not exist, create a new token and store it
        access_token = create_access_token(identity=device_id)
        new_device = Device(device_id=device_id, token=access_token)
        db.session.add(new_device)
        db.session.commit()
        logging.info(f"New device {device_id} registered.")
        return jsonify(access_token=access_token), 200

# --------- Poster Generation (Synchronous) ---------
@app.route('/api/v1/generate_album_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
def generate_album_endpoint():
    """Generate album poster synchronously and return download URL"""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json() or {}
    album_name = data.get('album_name')
    artist_name = data.get('artist_name')
    theme = data.get('theme', 'Light')
    indexing = data.get('indexing', False)
    accent = data.get('accent', False)
    custom_cover = data.get('custom_cover')

    if not album_name or not artist_name:
        return jsonify(error='album_name and artist_name required'), 400

    # --- Redis cache key ---
    cache_key = f"album_poster:{artist_name}:{album_name}:{theme}:{indexing}:{accent}:{custom_cover}"
    poster_data = cache.get(cache_key)
    if poster_data:
        try:
            poster_data = json.loads(poster_data)
            logging.info("Returning cached album poster data, not calling Spotify API.")
            return jsonify(**poster_data), 200
        except Exception as e:
            logging.error(f"Error decoding cached poster_data: {e}")
            cache.delete(cache_key)

    logging.info("Calling sp.get_album from app.py")
    save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'albums')
    try:
        metadata = sp.get_album(f"{album_name} - {artist_name}", limit=1)
        logging.info(f"Got album metadata: {metadata}")
        
        if not metadata:
            return jsonify(error='Album not found'), 404
            
        local_path = ps.album(
            metadata,  # Pass the metadata directly
            save_dir=save_dir,
            theme=theme,
            indexing=indexing,
            accent=accent,
            custom_cover=custom_cover
        )
    except Exception as e:
        logging.error(f"Album poster generation error: {str(e)}")
        return jsonify(error='Failed to generate album poster', details=str(e)), 500

    rel_path = os.path.relpath(local_path, app.config['DOWNLOAD_DIR'])
    with Image.open(local_path) as image:
        image.thumbnail((228, 348))
        image = image.convert("RGB")  # Ensure 3 channels
        np_img = np.array(image)
    hash = blurhash.encode(np_img, components_x=2, components_y=3)
    response_data = {
        "message": 'Album poster generated!',
        "filePath": rel_path,
        "blurhash": hash
    }
    cache.set(cache_key, json.dumps(response_data), timeout=3600)
    return jsonify(**response_data), 200

@app.route('/api/v1/generate_track_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
def generate_track_endpoint():
    """Generate track poster synchronously and return download URL"""
    if request.method == 'OPTIONS':
        return '', 204

    logging.info(f"Request JSON Body: {request.get_json()}")

    data = request.get_json() or {}
    track_name = data.get('track_name')
    artist_name = data.get('artist_name')
    theme = data.get('theme', 'Light')
    indexing = data.get('indexing', False)
    accent = data.get('accent', False)
    custom_cover = data.get('custom_cover')

    if not track_name or not artist_name:
        return jsonify(error='track_name and artist_name required'), 400

    # --- Redis cache key ---
    cache_key = f"track_poster:{artist_name}:{track_name}:{theme}:{indexing}:{accent}:{custom_cover}"
    poster_data = cache.get(cache_key)
    if poster_data:
        try:
            poster_data = json.loads(poster_data)
            return jsonify(**poster_data), 200
        except Exception as e:
            logging.error(f"Error decoding cached poster_data: {e}")
            cache.delete(cache_key)

    save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'tracks')
    try:
        # Get track metadata from Spotify
        track = sp.get_track(f"{track_name} - {artist_name}")
        logging.info(f"Spotify API response: {track}")
        
        if not track:
            logging.error(f"No track found for {track_name} by {artist_name}")
            return jsonify(error=f"No track found for {track_name} by {artist_name}"), 404

        # Fetch lyrics using the lyrics component
        logging.info(f"Fetching lyrics for {track.name} by {track.artist}")
        lyrics = ly.get_lyrics(track)  
        
        # Ensure lyrics is a non-empty list of strings
        if not lyrics or not isinstance(lyrics, list):
            logging.warning(f"No lyrics found for {track.name} by {track.artist}")
            lyrics = ["No lyrics available"]
        else:
            # Filter out empty lines and ensure all items are strings
            lyrics = [str(line).strip() for line in lyrics if line and str(line).strip()]
            if not lyrics:  # If all lines were empty
                lyrics = ["No lyrics available"]
        
        logging.info(f"Processing lyrics: {len(lyrics)} lines")

        # Generate the poster using track metadata and lyrics
        local_path = ps.track(
            track,
            lyrics=lyrics,
            save_dir=save_dir,
            theme=theme,
            accent=accent,
            custom_cover=custom_cover
        )

        rel_path = os.path.relpath(local_path, app.config['DOWNLOAD_DIR'])
        download_url = f"{request.url_root.rstrip('/')}/api/v1/get_poster/{rel_path}"
        response_data = {
            "message": 'Track poster generated!',
            "url": download_url
        }
        cache.set(cache_key, json.dumps(response_data), timeout=3600)
        return jsonify(**response_data), 200

    except Exception as e:
        logging.error(f"Track poster generation error: {str(e)}")
        logging.error("Traceback: ", exc_info=True)
        return jsonify(error='Failed to generate track poster', details=str(e)), 500

# --------- File Serving ---------
@app.route('/api/v1/get_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
def get_poster():
    """Serve generated poster files via Base64"""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json() or {}
    filename = data.get('filename')
    if not filename:
        return jsonify(error='filename required'), 400
    try:
        filepath = os.path.join(app.config['DOWNLOAD_DIR'], filename)
        with open(filepath, 'rb') as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return jsonify(image=encoded_string), 200
    except FileNotFoundError:
        return jsonify(error='File not found'), 404

# --------- Protected Endpoint Example ---------
@app.route('/api/v1/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(message="This is a protected route.")

# --------- Error Handlers ---------
@app.errorhandler(404)
def not_found(e):
    return jsonify(error='Not Found'), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify(error='Internal Server Error'), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
