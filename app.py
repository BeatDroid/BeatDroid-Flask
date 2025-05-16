import os
import dotenv
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flasgger import Swagger
from poster import Poster
from BeatPrints import lyrics, spotify
import base64

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
    "JWT_ACCESS_TOKEN_EXPIRES": False,
    "RATELIMIT_STORAGE_URI": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "CACHE_TYPE": "redis",
    "CACHE_REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/1"),
    "DOWNLOAD_DIR": os.getenv("DOWNLOAD_DIR", "/tmp/beatprints_downloads"),
    'SQLALCHEMY_ECHO': False
    
})

# Ensure download directories exist
os.makedirs(os.path.join(app.config['DOWNLOAD_DIR'], 'albums'), exist_ok=True)
os.makedirs(os.path.join(app.config['DOWNLOAD_DIR'], 'tracks'), exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["100 per hour"])
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

@app.route('/api/v1/auth/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json() or {}
    device_id = data.get('device_id')
    if not device_id:
        return jsonify(error="Missing device_id"), 400

    device = Device.query.filter_by(device_id=device_id).first()
    if device:
        logging.info(f"Device {device_id} already exists. Returning existing token.")
        return jsonify(access_token=device.token), 200
    else:
        access_token = create_access_token(identity=device_id)
        new_device = Device(device_id=device_id, token=access_token)
        db.session.add(new_device)
        db.session.commit()
        logging.info(f"New device {device_id} registered.")
        return jsonify(access_token=access_token), 200

@app.route('/api/v1/generate_album_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
def generate_album_endpoint():
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

    # Cache the final poster path, not just metadata
    cache_key = f"album_poster:{artist_name}:{album_name}:{theme}:{indexing}:{accent}:{custom_cover}"
    poster_path = cache.get(cache_key)
    if poster_path:
        rel_path = os.path.relpath(poster_path, app.config['DOWNLOAD_DIR'])
        return jsonify(message='Album poster generated (from cache)!', filePath=rel_path), 200

    # If not cached, generate as usual
    metadata_key = f"album_metadata:{artist_name}:{album_name}"
    metadata = cache.get(metadata_key)
    if not metadata:
        try:
            metadata = sp.get_album(f"{album_name} - {artist_name}", limit=1)[0]
            cache.set(metadata_key, metadata, timeout=3600)
        except Exception as e:
            logging.error(f"Album poster generation error: {e}")
            return jsonify(error='Failed to generate album poster', details=str(e)), 500

    save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'albums')
    try:
        local_path = ps.album(
            metadata,
            save_dir=save_dir,
            theme=theme,
            indexing=indexing,
            accent=accent,
            custom_cover=custom_cover
        )
        cache.set(cache_key, local_path, timeout=3600)
    except Exception as e:
        logging.error(f"Album poster generation error: {e}")
        return jsonify(error='Failed to generate album poster', details=str(e)), 500

    rel_path = os.path.relpath(local_path, app.config['DOWNLOAD_DIR'])
    return jsonify(message='Album poster generated!', filePath=rel_path), 200

@app.route('/api/v1/generate_track_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
def generate_track_endpoint():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json() or {}
    track_name = data.get('track_name')
    artist_name = data.get('artist_name')
    theme = data.get('theme', 'Light')

    if not track_name or not artist_name:
        return jsonify(error='track_name and artist_name required'), 400

    # Cache the final poster path, not just metadata
    cache_key = f"track_poster:{artist_name}:{track_name}:{theme}"
    poster_path = cache.get(cache_key)
    if poster_path:
        rel_path = os.path.relpath(poster_path, app.config['DOWNLOAD_DIR'])
        download_url = f"{request.url_root.rstrip('/')}/api/v1/get_poster/{rel_path}"
        return jsonify(message='Track poster generated (from cache)!', url=download_url), 200

    metadata_key = f"track_metadata:{artist_name}:{track_name}"
    track = cache.get(metadata_key)
    if not track:
        try:
            query = f"track:{track_name} artist:{artist_name}"
            search_results = sp.get_track(query, limit=1)
            if not search_results:
                logging.error(f"No track found for {track_name} by {artist_name}")
                return jsonify(error=f"No track found for {track_name} by {artist_name}"), 404
            track = search_results[0]
            cache.set(metadata_key, track, timeout=3600)
        except Exception as e:
            logging.error(f"Spotify API error: {e}", exc_info=True)
            return jsonify(error='Spotify API failed', details=str(e)), 500

    try:
        lyrics_text = ly.get_lyrics(track)
        if not lyrics_text:
            return jsonify(error='No lyrics could be retrieved for this track'), 404

        save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'tracks')
        local_path = ps.track(
            metadata=track,
            lyrics=lyrics_text,
            save_dir=save_dir,
            theme=theme,
            accent_color='Light'
        )
        cache.set(cache_key, local_path, timeout=3600)
    except Exception as e:
        logging.error(f"Track poster generation error: {e}", exc_info=True)
        return jsonify(error='Failed to generate track poster', details=str(e)), 500

    rel_path = os.path.relpath(local_path, app.config['DOWNLOAD_DIR'])
    download_url = f"{request.url_root.rstrip('/')}/api/v1/get_poster/{rel_path}"
    return jsonify(message='Track poster generated!', url=download_url), 200

@app.route('/api/v1/get_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
def get_poster():
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

@app.route('/api/v1/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(message="This is a protected route.")

@app.errorhandler(404)
def not_found(e):
    return jsonify(error='Not Found'), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify(error='Internal Server Error'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
