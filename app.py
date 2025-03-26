from flask import Flask, request, jsonify, send_from_directory
import os
import dotenv
import functools
import secrets
from poster import Poster
from BeatPrints import lyrics, spotify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flasgger import Swagger
import logging

# Load environment variables
dotenv.load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Validate environment variables
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise EnvironmentError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in the environment variables.")

# In-memory API key storage (use a database in production)
api_keys = {}

# Directory setup
DOWNLOAD_DIR = "./downloads"
try:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(DOWNLOAD_DIR, "tracks"), exist_ok=True)
    os.makedirs(os.path.join(DOWNLOAD_DIR, "albums"), exist_ok=True)
    logging.info(f"Download directory created at {os.path.abspath(DOWNLOAD_DIR)}")
except OSError as e:
    logging.error(f"Failed to create download directory {DOWNLOAD_DIR}: {e}")
    raise

# Initialize components
ly = lyrics.Lyrics()
ps = Poster(DOWNLOAD_DIR)
sp = spotify.Spotify(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

# Rate Limiting
limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])

# Caching
app.config["CACHE_TYPE"] = "simple"
cache = Cache(app)

# Initialize Swagger for API documentation
swagger = Swagger(app)

# Middleware to require API key
def require_api_key(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if not api_key or api_key not in api_keys:
            return jsonify({"error": "Unauthorized access"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Endpoint to generate an API key
@app.route('/get_api_key', methods=['POST'])
def get_api_key():
    username = request.json.get("username")
    if not username:
        return jsonify({"error": "Username is required"}), 400
    
    api_key = secrets.token_hex(16)
    api_keys[api_key] = username
    return jsonify({"message": "API key generated successfully!", "api_key": api_key})

# Album Poster Generation Endpoint
@app.route('/generate_album_poster', methods=['POST'])
def generate_album_poster():
    """
    Generate a poster for an album with a customizable theme and optional parameters.
    ---
    parameters:
      - name: album_name
        in: query
        type: string
        required: true
        description: The name of the album
      - name: artist_name
        in: query
        type: string
        required: true
        description: The name of the artist
      - name: theme
        in: query
        type: string
        required: false
        default: Light
        description: The theme for the poster (e.g., Light, Dark)
      - name: indexing
        in: query
        type: boolean
        required: false
        default: False
        description: Whether to include track indexing on the poster
      - name: accent
        in: query
        type: boolean
        required: false
        default: False
        description: Whether to include an accent color from the album cover
      - name: custom_cover
        in: query
        type: string
        required: false
        description: URL or path to a custom cover image
    responses:
      200:
        description: Album poster generated successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Album poster generated successfully!"
            poster_url:
              type: string
              example: "http://localhost:5000/get_poster/albums/album_poster_file.jpg"
      400:
        description: Invalid input (missing album_name or artist_name)
      404:
        description: Album not found
      500:
        description: Server error during poster generation
    """
    # Extract query parameters
    album_name = request.args.get('album_name')
    artist_name = request.args.get('artist_name')
    theme = request.args.get('theme', 'Light')  # Default to 'Light'
    indexing = request.args.get('indexing', 'False').lower() == 'true'
    accent = request.args.get('accent', 'False').lower() == 'true'
    custom_cover = request.args.get('custom_cover')

    # Validate required parameters
    if not album_name or not artist_name:
        return jsonify({"error": "Please provide both album_name and artist_name"}), 400

    # Create a unique cache key based on all parameters
    cache_key = f"album_poster_{album_name}_{artist_name}_{theme}_{indexing}_{accent}_{custom_cover}"
    cached_poster = cache.get(cache_key)
    if cached_poster:
        logging.info(f"Serving cached album poster: {cached_poster}")
        return jsonify({"message": "Album poster retrieved from cache!", "poster_url": cached_poster})

    # Fetch album metadata using Spotify API
    try:
        albums = sp.get_album(f"{album_name} - {artist_name}", limit=1, shuffle=False)
        if not albums:
            return jsonify({"error": "Album not found"}), 404
        metadata = albums[0]  # Use the first (most relevant) album
    except Exception as e:
        logging.error(f"Error fetching album metadata: {str(e)}")
        return jsonify({"error": "Failed to fetch album metadata", "details": str(e)}), 500

    # Generate and save the album poster
    try:
        save_dir = os.path.join(DOWNLOAD_DIR, "albums")
        poster_path = ps.album(metadata, save_dir=save_dir, theme=theme, indexing=indexing, accent=accent, custom_cover=custom_cover)
        
        # Generate the poster URL
        poster_rel_path = os.path.relpath(poster_path, DOWNLOAD_DIR)
        poster_url = f"http://{request.host}/get_poster/{poster_rel_path}"
        
        # Cache the result for 1 hour
        cache.set(cache_key, poster_url, timeout=3600)
        
        logging.info(f"Generated album poster URL: {poster_url}")
        return jsonify({"message": "Album poster generated successfully!", "poster_url": poster_url})
    except Exception as e:
        logging.error(f"Error generating album poster: {str(e)}")
        return jsonify({"error": "Failed to generate album poster", "details": str(e)}), 500

# Track Poster Generation Endpoint
@app.route('/generate_track_poster', methods=['POST'])
def generate_track_poster():
    """
    Generate a poster for a track with a customizable theme.
    ---
    parameters:
      - name: track_name
        in: query
        type: string
        required: true
        description: The name of the track
      - name: artist_name
        in: query
        type: string
        required: true
        description: The name of the artist
      - name: theme
        in: query
        type: string
        required: false
        default: Light
        description: The theme for the poster (e.g., Light, Dark)
    responses:
      200:
        description: Poster generated successfully
      400:
        description: Invalid input
      404:
        description: Track or lyrics not found
      500:
        description: Server error
    """
    track_name = request.args.get('track_name')
    artist_name = request.args.get('artist_name')
    theme = request.args.get('theme', 'Light')
    
    if not track_name or not artist_name:
        return jsonify({"error": "Please provide both track_name and artist_name"}), 400

    cache_key = f"poster_{track_name}_{artist_name}_{theme}"
    cached_poster = cache.get(cache_key)
    if cached_poster:
        return jsonify({"message": "Poster retrieved from cache!", "poster_url": cached_poster})
    
    search = sp.get_track(f"{track_name} - {artist_name}", limit=1)
    if not search:
        return jsonify({"error": "Track not found"}), 404

    metadata = search[0]
    lyrics_text = ly.get_lyrics(metadata)
    
    if lyrics_text is None:
        return jsonify({"error": "Lyrics not found"}), 404

    highlighted_lyrics = (
        lyrics_text if ly.check_instrumental(metadata) else ly.select_lines(lyrics_text, "5-9")
    )
    
    try:
        save_dir = os.path.join(DOWNLOAD_DIR, "tracks")
        poster_path = ps.track(metadata, highlighted_lyrics, save_dir=save_dir, theme=theme)
        poster_rel_path = os.path.relpath(poster_path, DOWNLOAD_DIR)
        poster_url = f"http://{request.host}/get_poster/{poster_rel_path}"
        
        cache.set(cache_key, poster_url, timeout=3600)
        logging.info(f"Poster URL: {poster_url}")
        return jsonify({"message": "Poster generated successfully!", "poster_url": poster_url})
    except Exception as e:
        logging.error(f"Error generating poster: {str(e)}")
        return jsonify({"error": "Failed to generate poster", "details": str(e)}), 500

# Serve Poster Files
@app.route('/get_poster/<path:filename>')
@require_api_key
def get_poster(filename):
    try:
        return send_from_directory(DOWNLOAD_DIR, filename)
    except FileNotFoundError:
        return jsonify({"error": "Poster file not found"}), 404

# Simple Greeting Endpoint
@app.route('/hello', methods=['GET'])
def greet_user():
    return jsonify({"message": "Welcome!"})

# Error Handlers
@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad Request", "message": str(error)}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found", "message": str(error)}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)