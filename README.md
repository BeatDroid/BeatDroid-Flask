# 🎵 BeatPrints API

BeatPrints is a Flask-based API that allows users to generate **album posters** and **track posters** using metadata from Spotify and lyrics from external sources. It also includes authentication using JWT tokens and rate-limiting for secure and efficient usage.

---

## 🚀 Features

- **Authentication**: Secure login using device IDs with JWT tokens that never expire.
- **Poster Generation**:
  - Generate **album posters** with customizable themes.
  - Generate **track posters** with lyrics.
- **Rate Limiting**: Prevent abuse with configurable request limits.
- **Caching**: Redis-based caching for faster responses.
- **File Serving**: Download generated posters directly.
- **API Documentation**: Swagger integration for interactive API exploration.

---

## 🛠️ Setup Instructions

### **1. Clone the Repository**
```bash
git clone https://github.com/<your-username>/BeatPrints.git
cd BeatPrints
```

### **2. Create and Activate a Virtual Environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

### **3. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **4. Configure Environment Variables**
Copy `.env.example` to `.env` and set the following values:
```bash
cp .env.example .env
```

---

## 🔧 Environment Variables

Populate your `.env` file with:

```
FLASK_ENV=development
JWT_SECRET_KEY=your_jwt_secret
REDIS_URL=redis://localhost:6379/0
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
DOWNLOAD_DIR=/tmp/beatprints_downloads
```  

- `FLASK_ENV`: `development` or `production`  
- `JWT_SECRET_KEY`: Secret for signing JWT tokens  
- `REDIS_URL`: Redis connection URI for rate limiting and caching  
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`: Spotify API credentials  
- `DOWNLOAD_DIR`: Directory to store generated posters

---

## 🏃 Running Locally

```bash
# Activate virtualenv if not already
source venv/bin/activate

# Start Redis (if not already running)
redis-server &

# Run the Flask app
env FLASK_APP=app.py flask run --host=0.0.0.0 --port=5000
```

The API will be available at `http://localhost:5000/api/v1/`.

---

## 📖 API Endpoints

### 1. Authentication

#### **POST** `/api/v1/auth/login`
Request:
```json
{ "username": "user1", "password": "pass123" }
```
Response:
```json
{ "access_token": "<JWT_TOKEN>" }
```

### 2. Generate Album Poster

#### **POST** `/api/v1/generate_album_poster`
Headers:
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```
Body:
```json
{
  "album_name": "Abbey Road",
  "artist_name": "The Beatles",
  "theme": "Dark",
  "indexing": true,
  "accent": false
}
```
Response:
```json
{
  "message": "Album poster generated!",
  "url": "http://localhost:5000/api/v1/get_poster/albums/filename.png"
}
```

### 3. Generate Track Poster

#### **POST** `/api/v1/generate_track_poster`
Headers and body similar to album, using `track_name` and `artist_name`.

### 4. Download Poster

#### **GET** `/api/v1/get_poster/<path>`
Headers:
```
Authorization: Bearer <JWT_TOKEN>
```
Responds with the image file as an attachment.

---

## 📜 Swagger UI

Visit `http://localhost:5000/apidocs` to explore the API interactively.

---

## 📄 License

[MIT License](LICENSE)

