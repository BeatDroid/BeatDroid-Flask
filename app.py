from flask import Flask, request, jsonify
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
ps = poster.Poster("./")
sp = spotify.Spotify(CLIENT_ID, CLIENT_SECRET)

@app.route('/generate_poster', methods=['GET'])
def generate_poster():
    track_name = request.args.get('track_name')
    artist_name = request.args.get('artist_name')

    if not track_name or not artist_name:
        return jsonify({"error": "Please provide both track_name and artist_name"}), 400

    # Search for the track and fetch metadata
    search = sp.get_track(f"{track_name} - {artist_name}", limit=1)
    #search = sp.get_album(f"{track_name} - {artist_name}", limit=1)
    
    if not search:
        return jsonify({"error": "Track not found"}), 404

    # Pick the first result
    metadata = search[0]
    print(metadata)
        # Get lyrics and determine if the track is instrumental
    lyrics = ly.get_lyrics(metadata)


    # Use the placeholder for instrumental tracks; otherwise, select specific lines
    highlighted_lyrics = (
        lyrics if ly.check_instrumental(metadata) else ly.select_lines(lyrics, "5-9")
    )
    print(highlighted_lyrics)
    # Generate the track poster
    ps.track(metadata, highlighted_lyrics)

    return jsonify({"message": "Poster generated successfully NIGGGGGGGGGGA!"})

if __name__ == '__main__':
    app.run(debug=True)


