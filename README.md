### BeatDroid Flask API

BeatDroid is a Flask-based API that generates posters for albums and tracks using metadata from Spotify and lyrics data. It provides a simple and scalable solution for creating aesthetically pleasing posters with customizable themes.

## Features

- 🎵 **Generate Album Posters** - Create posters for albums with customizable themes and styling options.
- 🎤 **Generate Track Posters** - Create posters with lyrics for individual tracks.
- 🔑 **API Key Authentication** - Secure access to API endpoints.
- ⚡ **Caching for Performance** - Store generated posters for quick retrieval.
- 📄 **Swagger API Documentation** - Built-in documentation for easy integration.

---

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/MA3V1N/beatdroid-flask.git
   cd beatdroid-flask
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up environment variables:**
   Create a `.env` file in the project directory and add the following:
   ```ini
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

---

## Running the Application

Start the Flask server with:
```bash
python app.py
```
The API will be accessible at `http://localhost:5000`

---

## API Usage

### 1️⃣ Generate an API Key
```bash
curl -X POST "http://localhost:5000/get_api_key" -H "Content-Type: application/json" -d '{"username": "your_name"}'
```

### 2️⃣ Generate an Album Poster
```bash
curl -X GET "http://localhost:5000/generate_album_poster?album_name=Thriller&artist_name=Michael+Jackson&theme=Dark" -H "X-API-KEY: your_api_key"
```

### 3️⃣ Generate a Track Poster
```bash
curl -X POST "http://localhost:5000/generate_poster?track_name=Billie+Jean&artist_name=Michael+Jackson" -H "X-API-KEY: your_api_key"
```

### 4️⃣ Retrieve a Poster File
```bash
curl -X GET "http://localhost:5000/get_poster/albums/thriller_poster.jpg" -H "X-API-KEY: your_api_key" --output thriller_poster.jpg
```

---

## Error Handling

| Status Code | Meaning |
|------------|---------|
| 400 | Bad Request - Missing or incorrect parameters. |
| 404 | Not Found - Album or track not found. |
| 500 | Internal Server Error - Unexpected errors. |

---

## Contributing

We welcome contributions! Feel free to fork the repo, submit pull requests, or open issues.

---

## License

This project is licensed under the MIT License.

🚀 **Happy Coding!** 🎶

