from flask import Flask, request, jsonify, send_from_directory
import os
import dotenv
from BeatPrints import lyrics, poster, spotify

dotenv.load_dotenv()

app = Flask(__name__)

# Spotify credentials
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Initialize components
ly = lyrics.Lyrics()
ps = poster.Poster("/app/downloads")  # Store posters here
sp = spotify.Spotify(CLIENT_ID, CLIENT_SECRET)

DOWNLOAD_DIR = "/app/downloads"

@app.route('/generate_poster', methods=['GET'])
def generate_poster():
    track_name = request.args.get('track_name')
    artist_name = request.args.get('artist_name')

    if not track_name or not artist_name:
        return jsonify({"error": "Please provide both track_name and artist_name"}), 400

    search = sp.get_track(f"{track_name} - {artist_name}", limit=1)
    
    if not search:
        return jsonify({"error": "Track not found"}), 404

    metadata = search[0]
    lyrics_text = ly.get_lyrics(metadata)
    highlighted_lyrics = (
        lyrics_text if ly.check_instrumental(metadata) else ly.select_lines(lyrics_text, "5-9")
    )

    # Generate poster
    poster_filename = ps.track(metadata, highlighted_lyrics)

    return jsonify({
        "message": "Poster generated successfully!",
        "poster_url": f"http://{request.host}/get_poster/{poster_filename}"
    })

@app.route('/get_poster/<filename>')
def get_poster(filename):
    return send_from_directory(DOWNLOAD_DIR, filename)

@app.route('/hello', methods=['GET'])
def greet_user():
    return jsonify({"message": "Welcome!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
