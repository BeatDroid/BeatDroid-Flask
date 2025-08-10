import os
import dotenv
import logging
import base64
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
import blurhash

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
    "RATELIMIT_STORAGE_URI": "memory://",  # Use in-memory storage for rate limiting
    "CACHE_TYPE": "simple",  # Use simple in-memory cache
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
@app.route('/auth/login', methods=['POST', 'OPTIONS'])
def login():
    """Authenticate and return JWT token based on device ID"""
    if request.method == 'OPTIONS':
        return '', 204

    # Get the device ID from the request
    data = request.get_json() or {}
    device_id = data.get('device_id')

    # Validate the device ID
    if not device_id:
        return jsonify({
            "success": False,
            "error": "Missing required parameters",
            "message": "device_id is required"
        }), 400

    # Check if the device ID already exists in the database
    device = Device.query.filter_by(device_id=device_id).first()

    if device:
        # If the device exists, return the existing token
        logging.info(f"Device {device_id} already exists. Returning existing token.")
        return jsonify({
            "success": True,
            "message": "Device authenticated successfully",
            "data": {
                "access_token": device.token,
                "device_id": device_id,
                "is_new_device": False
            }
        }), 200
    else:
        # If the device does not exist, create a new token and store it
        access_token = create_access_token(identity=device_id)
        new_device = Device(device_id=device_id, token=access_token)
        db.session.add(new_device)
        db.session.commit()
        logging.info(f"New device {device_id} registered.")
        return jsonify({
            "success": True,
            "message": "Device registered and authenticated successfully",
            "data": {
                "access_token": access_token,
                "device_id": device_id,
                "is_new_device": True
            }
        }), 201

# --------- Poster Generation (Synchronous) ---------
@app.route('/generate_album_poster', methods=['POST', 'OPTIONS'])
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
        return jsonify({
            "success": False,
            "error": "Missing required parameters",
            "message": "album_name and artist_name are required"
        }), 400

    # Cache checking has been removed as per user request
    logging.info("Calling sp.get_album from app.py")
    save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'albums')
    try:
        metadata = sp.get_album(f"{album_name} - {artist_name}", limit=1)
        logging.info(f"Got album metadata: {metadata}")
        
        if not metadata:
            return jsonify({
                "success": False,
                "error": "Album not found",
                "message": f"No album found for {album_name} by {artist_name}"
            }), 404
            
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
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "Failed to generate album poster",
            "details": str(e)
        }), 500

    rel_path = os.path.relpath(local_path, app.config['DOWNLOAD_DIR'])
    # Generate blurhash for the image with blurhash-python
    with open(local_path, 'rb') as image_file:
        hash = blurhash.encode(image_file, x_components=4, y_components=3)
    response_data = {
        "success": True,
        "message": 'Album poster generated successfully!',
        "data": {
            "filePath": rel_path,
            "blurhash": hash,
            "type": "album_poster",
            "albumName": metadata.name,
            "artistName": metadata.artist
        }
    }
    logging.info(f"Album poster generated successfully: {response_data}")
    return jsonify(**response_data), 200

@app.route('/generate_track_poster', methods=['POST', 'OPTIONS'])
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
        return jsonify({
            "success": False,
            "error": "Missing required parameters",
            "message": "track_name and artist_name are required"
        }), 400

    save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'tracks')
    try:
        # Get track metadata from Spotify
        track = sp.get_track(f"{track_name} - {artist_name}")
        logging.info(f"Spotify API response: {track}")
        
        if not track:
            logging.error(f"No track found for {track_name} by {artist_name}")
            return jsonify({
                "success": False,
                "error": "Track not found",
                "message": f"No track found for {track_name} by {artist_name}"
            }), 404

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
        
        # Generate blurhash for the image with blurhash-python
        with open(local_path, 'rb') as image_file:
            hash = blurhash.encode(image_file, x_components=4, y_components=3)
        
        response_data = {
            "success": True,
            "message": 'Track poster generated successfully!',
            "data": {
                "filePath": rel_path,
                "blurhash": hash,
                "type": "track_poster",
                "trackName": track.name,
                "artistName": track.artist
            }
        }
        return jsonify(**response_data), 200

    except Exception as e:
        logging.error(f"Track poster generation error: {str(e)}")
        logging.error("Traceback: ", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "Failed to generate track poster",
            "details": str(e)
        }), 500

# --------- File Serving ---------
@app.route('/get_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
def get_poster():
    """Serve generated poster files via Base64 with thumbhash"""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json() or {}
    filename = data.get('filename')
    if not filename:
        return jsonify({
            "success": False,
            "error": "Missing required parameters",
            "message": "filename is required"
        }), 400
    try:
        filepath = os.path.join(app.config['DOWNLOAD_DIR'], filename)
        try:
            with open(filepath, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Delete the file after reading it
            os.remove(filepath)
            logging.info(f"Successfully deleted file: {filepath}")
            
            return jsonify({
                "success": True,
                "message": "Image retrieved and file deleted successfully",
                "data": {
                    "image": encoded_string,
                    "filename": filename
                }
            }), 200
        except OSError as e:
            logging.error(f"Error deleting file {filepath}: {str(e)}")
            # Still return the image even if deletion fails, but include a warning
            return jsonify({
                "success": True,
                "message": "Image retrieved but file could not be deleted",
                "warning": f"Failed to delete file: {str(e)}",
                "data": {
                    "image": encoded_string,
                    "filename": filename
                }
            }), 200
    except FileNotFoundError:
        return jsonify({
            "success": False,
            "error": "File not found",
            "message": f"The file {filename} was not found"
        }), 404
    except Exception as e:
        logging.error(f"Error serving poster file: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "Failed to retrieve image",
            "details": str(e)
        }), 500

# --------- Protected Endpoint Example ---------
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(message="This is a protected route.")

# --------- Error Handlers ---------
@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "success": False,
        "error": "Not Found",
        "message": "The requested resource was not found"
    }), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({
        "success": False,
        "error": "Internal Server Error",
        "message": "An unexpected error occurred on the server"
    }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
