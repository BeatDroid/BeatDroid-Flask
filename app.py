import os
import dotenv
import logging
import base64
import json
from BeatPrints.errors import NoLyricsAvailable
from flask import Flask, request, jsonify, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
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
import sentry_sdk
from sentry_sdk.integrations.serverless import serverless_function
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import traceback
from functools import wraps
from sqlalchemy import text

# Initialize Sentry only in production environment
if os.getenv('ENVIRONMENT') == 'production':
    # Configure Sentry with comprehensive integrations
    sentry_logging = LoggingIntegration(
        level=logging.INFO,  # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors and above as events
    )

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            FlaskIntegration(
                transaction_style="endpoint",
            ),
            SqlalchemyIntegration(),
            sentry_logging,
        ],
        # Add data like request headers and IP for users
        send_default_pii=True,
        # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions
        profiles_sample_rate=1.0,
        # Enable performance monitoring
        enable_tracing=True,
        # Set max breadcrumbs
        max_breadcrumbs=50,
        # Set environment
        environment=os.getenv("ENVIRONMENT", "development"),
        # Set release
        release=os.getenv("APP_VERSION", "1.0.0"),
    )
else:
    # Disable Sentry for non-production environments
    sentry_sdk.init(dsn="")

# Load environment variables
dotenv.load_dotenv()

# Configure logging with Sentry breadcrumbs
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)

# Custom decorator for Sentry transaction monitoring
def sentry_transaction(transaction_name=None):
    """Decorator to create Sentry transactions for better performance monitoring"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            name = transaction_name or f.__name__
            with sentry_sdk.start_transaction(op="http.server", name=name) as transaction:
                # Add custom tags
                sentry_sdk.set_tag("endpoint", name)
                sentry_sdk.set_tag("method", request.method)
                
                # Add user context if available
                try:
                    user_id = get_jwt_identity() if hasattr(request, 'headers') and 'Authorization' in request.headers else None
                    if user_id:
                        sentry_sdk.set_user({"id": user_id})
                except Exception:
                    pass  # JWT not required for all endpoints
                
                try:
                    result = f(*args, **kwargs)
                    # Set transaction status based on response
                    if hasattr(result, 'status_code'):
                        transaction.set_http_status(result.status_code)
                    return result
                except Exception as e:
                    # Capture exception and set transaction status
                    sentry_sdk.capture_exception(e)
                    transaction.set_http_status(500)
                    raise
        return decorated_function
    return decorator

# Custom error handler decorator
def handle_errors(f):
    """Decorator to handle errors consistently and report to Sentry"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.error(f"Validation error in {f.__name__}: {str(e)}")
            sentry_sdk.capture_exception(e)
            return jsonify({
                "success": False,
                "error": "Validation Error",
                "message": str(e)
            }), 400
        except FileNotFoundError as e:
            logger.error(f"File not found in {f.__name__}: {str(e)}")
            sentry_sdk.capture_exception(e)
            return jsonify({
                "success": False,
                "error": "File Not Found",
                "message": str(e)
            }), 404
        except NoLyricsAvailable as e:
            logger.warning(f"No lyrics available in {f.__name__}: {str(e)}")
            sentry_sdk.capture_message(f"No lyrics available: {str(e)}", level="warning")
            # This is handled gracefully, not an error
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            sentry_sdk.capture_exception(e)
            return jsonify({
                "success": False,
                "error": "Internal Server Error",
                "message": "An unexpected error occurred"
            }), 500
    return decorated_function

# Simple CORS headers without external dependency
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

app.after_request(add_cors_headers)

@app.before_request
def log_request_info():
    """Log details of every incoming request and add Sentry breadcrumbs"""
    # Add Sentry breadcrumb for request
    sentry_sdk.add_breadcrumb(
        message=f"{request.method} {request.url}",
        category="http.request",
        level="info",
        data={
            "method": request.method,
            "url": request.url,
            "user_agent": request.headers.get("User-Agent"),
            "remote_addr": request.remote_addr,
        }
    )
    
    logger.info(f"Request Method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request Headers: {dict(request.headers)}")
    
    if request.is_json:
        try:
            json_data = request.get_json()
            # Log non-sensitive data only
            safe_data = {k: v for k, v in json_data.items() if k not in ['password', 'token', 'secret']}
            logger.info(f"Request JSON Body: {safe_data}")
        except Exception as e:
            logger.warning(f"Failed to parse JSON body: {str(e)}")
    else:
        logger.info("Request Body: Not JSON or empty")

# Configuration
app.config.update({
    "JWT_SECRET_KEY": os.getenv("JWT_SECRET_KEY", "super-secret"),
    "SQLALCHEMY_DATABASE_URI": "sqlite:///devices.db",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "JWT_ACCESS_TOKEN_EXPIRES": False,  # Token never expires
    "RATELIMIT_STORAGE_URI": "memory://",  # Use in-memory storage for rate limiting
    "CACHE_TYPE": "simple",  # Use simple in-memory cache
    "DOWNLOAD_DIR": os.getenv("DOWNLOAD_DIR", "/tmp/beatprints_downloads"),
    'SQLALCHEMY_ECHO': False
})

# Ensure download directories exist
download_dir = app.config['DOWNLOAD_DIR']
try:
    os.makedirs(os.path.join(download_dir, 'albums'), exist_ok=True)
    os.makedirs(os.path.join(download_dir, 'tracks'), exist_ok=True)
    logger.info(f"Download directories created successfully: {download_dir}")
except Exception as e:
    logger.error(f"Failed to create download directories: {str(e)}")
    sentry_sdk.capture_exception(e)

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
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        sentry_sdk.capture_exception(e)

# Initialize business logic components with error handling
try:
    ly = lyrics.Lyrics()
    logger.info("Lyrics component initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Lyrics component: {str(e)}")
    sentry_sdk.capture_exception(e)
    raise

try:
    ps = Poster(app.config['DOWNLOAD_DIR'])
    logger.info("Poster component initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Poster component: {str(e)}")
    sentry_sdk.capture_exception(e)
    raise

try:
    sp = spotify.Spotify(
        os.getenv("SPOTIFY_CLIENT_ID"),
        os.getenv("SPOTIFY_CLIENT_SECRET")
    )
    logger.info("Spotify component initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Spotify component: {str(e)}")
    sentry_sdk.capture_exception(e)
    raise

# --------- Authentication ---------
@app.route('/auth/login', methods=['POST', 'OPTIONS'])
@sentry_transaction("auth_login")
@handle_errors
def login():
    """Authenticate and return JWT token based on device ID"""
    if request.method == 'OPTIONS':
        return '', 204

    with sentry_sdk.start_span(op="auth", description="Device authentication"):
        # Get the device ID from the request
        data = request.get_json() or {}
        device_id = data.get('device_id')

        # Add custom context to Sentry
        sentry_sdk.set_context("auth_request", {
            "device_id": device_id,
            "has_device_id": bool(device_id)
        })

        # Validate the device ID
        if not device_id:
            sentry_sdk.add_breadcrumb(
                message="Authentication failed - missing device_id",
                level="warning"
            )
            return jsonify({
                "success": False,
                "error": "Missing required parameters",
                "message": "device_id is required"
            }), 400

        with sentry_sdk.start_span(op="db.query", description="Check existing device"):
            # Check if the device ID already exists in the database
            device = Device.query.filter_by(device_id=device_id).first()

        if device:
            # If the device exists, return the existing token
            logger.info(f"Device {device_id} already exists. Returning existing token.")
            sentry_sdk.add_breadcrumb(
                message=f"Device {device_id} authenticated with existing token",
                level="info"
            )
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
            with sentry_sdk.start_span(op="auth", description="Create new device token"):
                # If the device does not exist, create a new token and store it
                access_token = create_access_token(identity=device_id)
                new_device = Device(device_id=device_id, token=access_token)
                
                with sentry_sdk.start_span(op="db.insert", description="Save new device"):
                    db.session.add(new_device)
                    db.session.commit()
                
                logger.info(f"New device {device_id} registered.")
                sentry_sdk.add_breadcrumb(
                    message=f"New device {device_id} registered successfully",
                    level="info"
                )
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
@sentry_transaction("generate_album_poster")
@handle_errors
def generate_album_endpoint():
    """Generate album poster synchronously and return download URL"""
    if request.method == 'OPTIONS':
        return '', 204
        
    with sentry_sdk.start_span(op="poster.album", description="Generate album poster"):
        data = request.get_json() or {}
        album_name = data.get('album_name')
        artist_name = data.get('artist_name')
        theme = data.get('theme', 'Light')
        indexing = data.get('indexing', False)
        accent = data.get('accent', False)
        custom_cover = data.get('custom_cover')

        # Add custom context to Sentry
        sentry_sdk.set_context("album_request", {
            "album_name": album_name,
            "artist_name": artist_name,
            "theme": theme,
            "indexing": indexing,
            "accent": accent,
            "has_custom_cover": bool(custom_cover)
        })

        if not album_name or not artist_name:
            sentry_sdk.add_breadcrumb(
                message="Album poster generation failed - missing required parameters",
                level="warning"
            )
            return jsonify({
                "success": False,
                "error": "Missing required parameters",
                "message": "album_name and artist_name are required"
            }), 400

        logger.info(f"Generating album poster for: {album_name} by {artist_name}")
        save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'albums')
        
        with sentry_sdk.start_span(op="spotify.api", description="Get album metadata"):
            logger.info("Calling sp.get_album from app.py")
            metadata = sp.get_album(f"{album_name} - {artist_name}", limit=1)
            logger.info(f"Got album metadata: {metadata}")
            
        if not metadata:
            sentry_sdk.add_breadcrumb(
                message=f"Album not found: {album_name} by {artist_name}",
                level="warning"
            )
            return jsonify({
                "success": False,
                "error": "Album not found",
                "message": f"No album found for {album_name} by {artist_name}"
            }), 404
            
        with sentry_sdk.start_span(op="poster.generate", description="Generate album poster"):
            local_path = ps.album(
                metadata,  # Pass the metadata directly
                save_dir=save_dir,
                theme=theme,
                indexing=indexing,
                accent=accent,
                custom_cover=custom_cover
            )

        with sentry_sdk.start_span(op="image.process", description="Generate blurhash"):
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
        
        logger.info(f"Album poster generated successfully: {response_data}")
        sentry_sdk.add_breadcrumb(
            message=f"Album poster generated: {metadata.name} by {metadata.artist}",
            level="info"
        )
        
        return jsonify(**response_data), 200

@app.route('/generate_track_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
@sentry_transaction("generate_track_poster")
@handle_errors
def generate_track_endpoint():
    """Generate track poster synchronously and return download URL"""
    if request.method == 'OPTIONS':
        return '', 204

    with sentry_sdk.start_span(op="poster.track", description="Generate track poster"):
        logger.info(f"Request JSON Body: {request.get_json()}")

        data = request.get_json() or {}
        track_name = data.get('track_name')
        artist_name = data.get('artist_name')
        theme = data.get('theme', 'Light')
        indexing = data.get('indexing', False)
        accent = data.get('accent', False)
        custom_cover = data.get('custom_cover')

        # Add custom context to Sentry
        sentry_sdk.set_context("track_request", {
            "track_name": track_name,
            "artist_name": artist_name,
            "theme": theme,
            "indexing": indexing,
            "accent": accent,
            "has_custom_cover": bool(custom_cover)
        })

        if not track_name or not artist_name:
            sentry_sdk.add_breadcrumb(
                message="Track poster generation failed - missing required parameters",
                level="warning"
            )
            return jsonify({
                "success": False,
                "error": "Missing required parameters",
                "message": "track_name and artist_name are required"
            }), 400

        logger.info(f"Generating track poster for: {track_name} by {artist_name}")
        save_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'tracks')
        
        with sentry_sdk.start_span(op="spotify.api", description="Get track metadata"):
            # Get track metadata from Spotify
            track = sp.get_track(f"{track_name} - {artist_name}")
            logger.info(f"Spotify API response: {track}")
            
        if not track:
            logger.error(f"No track found for {track_name} by {artist_name}")
            sentry_sdk.add_breadcrumb(
                message=f"Track not found: {track_name} by {artist_name}",
                level="warning"
            )
            return jsonify({
                "success": False,
                "error": "Track not found",
                "message": f"No track found for {track_name} by {artist_name}"
            }), 404

        with sentry_sdk.start_span(op="lyrics.fetch", description="Fetch track lyrics"):
            # Fetch lyrics using the lyrics component
            logger.info(f"Fetching lyrics for {track.name} by {track.artist}")
            try:
                lyrics_data = ly.get_lyrics(track)
                # Ensure lyrics is a non-empty list of strings
                if not lyrics_data or not isinstance(lyrics_data, list):
                    logger.warning(f"No lyrics found for {track.name} by {track.artist}")
                    lyrics_data = ["No lyrics available"]
                else:
                    # Filter out empty lines and ensure all items are strings
                    lyrics_data = [str(line).strip() for line in lyrics_data if line and str(line).strip()]
                    if not lyrics_data:  # If all lines were empty
                        lyrics_data = ["No lyrics available"]
            except NoLyricsAvailable:
                logger.warning(f"No lyrics available for {track.name} by {track.artist}")
                sentry_sdk.capture_message(f"No lyrics available for {track.name} by {track.artist}", level="warning")
                lyrics_data = ["No lyrics available"]
            
            logger.info(f"Processing lyrics: {len(lyrics_data)} lines")

        with sentry_sdk.start_span(op="poster.generate", description="Generate track poster"):
            # Generate the poster using track metadata and lyrics
            local_path = ps.track(
                track,
                lyrics=lyrics_data,
                save_dir=save_dir,
                theme=theme,
                accent=accent,
                custom_cover=custom_cover
            )

        with sentry_sdk.start_span(op="image.process", description="Generate blurhash"):
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
        
        logger.info(f"Track poster generated successfully for {track.name} by {track.artist}")
        sentry_sdk.add_breadcrumb(
            message=f"Track poster generated: {track.name} by {track.artist}",
            level="info"
        )
        
        return jsonify(**response_data), 200

# --------- File Serving ---------
@app.route('/get_poster', methods=['POST', 'OPTIONS'])
@jwt_required()
@sentry_transaction("get_poster")
@handle_errors
def get_poster():
    """Serve generated poster files via Base64 with thumbhash"""
    if request.method == 'OPTIONS':
        return '', 204
        
    with sentry_sdk.start_span(op="file.serve", description="Serve poster file"):
        data = request.get_json() or {}
        filename = data.get('filename')
        
        # Add custom context to Sentry
        sentry_sdk.set_context("file_request", {
            "filename": filename,
            "has_filename": bool(filename)
        })
        
        if not filename:
            sentry_sdk.add_breadcrumb(
                message="File serving failed - missing filename",
                level="warning"
            )
            return jsonify({
                "success": False,
                "error": "Missing required parameters",
                "message": "filename is required"
            }), 400

        filepath = os.path.join(app.config['DOWNLOAD_DIR'], filename)
        
        with sentry_sdk.start_span(op="file.read", description="Read poster file"):
            with open(filepath, 'rb') as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        with sentry_sdk.start_span(op="file.delete", description="Delete poster file"):
            try:
                # Delete the file after reading it
                os.remove(filepath)
                logger.info(f"Successfully deleted file: {filepath}")
                sentry_sdk.add_breadcrumb(
                    message=f"File deleted successfully: {filename}",
                    level="info"
                )
                
                return jsonify({
                    "success": True,
                    "message": "Image retrieved and file deleted successfully",
                    "data": {
                        "image": encoded_string,
                        "filename": filename
                    }
                }), 200
            except OSError as e:
                logger.error(f"Error deleting file {filepath}: {str(e)}")
                sentry_sdk.capture_exception(e)
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

# --------- Protected Endpoint Example ---------
@app.route('/protected', methods=['GET'])
@jwt_required()
@sentry_transaction("protected_endpoint")
def protected():
    user_id = get_jwt_identity()
    sentry_sdk.set_user({"id": user_id})
    sentry_sdk.add_breadcrumb(
        message=f"Protected endpoint accessed by user: {user_id}",
        level="info"
    )
    return jsonify(message="This is a protected route.")

# --------- Health Check Endpoint ---------
@app.route('/health', methods=['GET'])
@sentry_transaction("health_check")
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        with sentry_sdk.start_span(op="db.health", description="Database health check"):
            db.session.execute(text('SELECT 1'))
        
        # Check download directories
        with sentry_sdk.start_span(op="file.health", description="File system health check"):
            albums_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'albums')
            tracks_dir = os.path.join(app.config['DOWNLOAD_DIR'], 'tracks')
            
            if not os.path.exists(albums_dir) or not os.path.exists(tracks_dir):
                raise Exception("Download directories not accessible")
        
        return jsonify({
            "success": True,
            "status": "healthy",
            "message": "All systems operational"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        sentry_sdk.capture_exception(e)
        return jsonify({
            "success": False,
            "status": "unhealthy",
            "message": "System health check failed"
        }), 503

# --------- Error Handlers ---------
@app.errorhandler(400)
def bad_request(e):
    sentry_sdk.capture_exception(e)
    return jsonify({
        "success": False,
        "error": "Bad Request",
        "message": "The request was invalid or malformed"
    }), 400

@app.errorhandler(401)
def unauthorized(e):
    sentry_sdk.capture_exception(e)
    return jsonify({
        "success": False,
        "error": "Unauthorized",
        "message": "Authentication required"
    }), 401

@app.errorhandler(403)
def forbidden(e):
    sentry_sdk.capture_exception(e)
    return jsonify({
        "success": False,
        "error": "Forbidden",
        "message": "Access denied"
    }), 403

@app.errorhandler(404)
def not_found(e):
    sentry_sdk.capture_exception(e)
    return jsonify({
        "success": False,
        "error": "Not Found",
        "message": "The requested resource was not found"
    }), 404

@app.errorhandler(429)
def rate_limit_exceeded(e):
    sentry_sdk.capture_message(f"Rate limit exceeded: {str(e)}", level="warning")
    return jsonify({
        "success": False,
        "error": "Rate Limit Exceeded",
        "message": "Too many requests. Please try again later."
    }), 429

@app.errorhandler(500)
def server_error(e):
    sentry_sdk.capture_exception(e)
    return jsonify({
        "success": False,
        "error": "Internal Server Error",
        "message": "An unexpected error occurred on the server"
    }), 500

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Catch-all error handler for unexpected exceptions"""
    logger.error(f"Unexpected error: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    sentry_sdk.capture_exception(e)
    return jsonify({
        "success": False,
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }), 500

# Add cleanup handler for graceful shutdown
import atexit
import signal

def cleanup():
    """Cleanup function called on app shutdown"""
    logger.info("Application shutting down...")
    sentry_sdk.add_breadcrumb(
        message="Application shutdown initiated",
        level="info"
    )

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {sig}, shutting down gracefully...")
    cleanup()
    exit(0)

# Register cleanup handlers
atexit.register(cleanup)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting application on port {port}")
    sentry_sdk.add_breadcrumb(
        message=f"Application starting on port {port}",
        level="info"
    )
    app.run(host='0.0.0.0', port=port, debug=False)