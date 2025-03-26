# Flask Album & Track Poster Generator

This is a simple Flask-based API that generates posters for albums and tracks using Spotify metadata and lyrics.

## Features
- Generate album posters with customizable themes.
- Generate track posters with lyrics.
- Uses Spotify API to fetch metadata.
- API key authentication for secure access.
- Caching for improved performance.
- Swagger documentation for easy API usage.

## Installation
### Prerequisites
- Python 3.8+
- pip

### Setup
1. Clone this repository:
   ```bash
   git clone <repo_url>
   cd <repo_folder>
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   Create a `.env` file in the project directory and add the following:
   ```ini
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

## Running the Application
Start the Flask server with:
```bash
python app.py
```

The app will run on `http://localhost:5000`

## API Usage
### 1. Generate an API Key
Send a POST request to get an API key:
```bash
curl -X POST "http://localhost:5000/get_api_key" -H "Content-Type: application/json" -d '{"username": "your_name"}'
```
### 2. Generate an Album Poster
```bash
curl -X GET "http://localhost:5000/generate_album_poster?album_name=Thriller&artist_name=Michael+Jackson&theme=Dark" -H "X-API-KEY: your_api_key"
```
### 3. Generate a Track Poster
```bash
curl -X POST "http://localhost:5000/generate_poster?track_name=Billie+Jean&artist_name=Michael+Jackson" -H "X-API-KEY: your_api_key"
```
### 4. Get a Poster File
```bash
curl -X GET "http://localhost:5000/get_poster/albums/thriller_poster.jpg" -H "X-API-KEY: your_api_key" --output thriller_poster.jpg
```

## Error Handling
- `400 Bad Request`: Missing required parameters.
- `404 Not Found`: Album/Track not found.
- `500 Internal Server Error`: Unexpected errors.

## License
This project is licensed under the MIT License.

