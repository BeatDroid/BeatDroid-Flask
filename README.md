# 🎵 BeatPrints API 🎨

Welcome to **BeatPrints** – the easiest way to generate beautiful, custom posters for your favorite albums and tracks, powered by Spotify and lyrics magic!  
Whether you're a developer, music lover, or just want to make your wall look cooler, this API is for you. 🚀

---

## ✨ Features

- 🔒 **JWT Authentication** for device-based access
- 🎶 **Spotify Integration** for album & track data
- 📝 **Lyrics Fetching** for tracks
- 🖼️ **Poster Generation** for albums and tracks (with themes & custom covers)
- ⚡ **Redis Caching** for blazing fast repeated requests
- 📦 **Download & Base64 Serving** of posters
- 🐍 **Noob-friendly Flask API** – easy to run, easy to use!

---

## 🚀 Quickstart

### 1. **Clone the Repo**

```sh
git clone https://github.com/MA3V1N/beatdroid-flask.git
cd beatdroid-flask
```

### 2. **Install Requirements**

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. **Set Up Environment Variables**

Create a `.env` file in the root directory:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
JWT_SECRET_KEY=your_super_secret_key
REDIS_URL=redis://localhost:6379/1
DOWNLOAD_DIR=/tmp/beatprints_downloads
```

### 4. **Run the Server**

```sh
python app.py
```

Server will be live at:  
`http://127.0.0.1:5000`

---

## 🔑 Authentication

Before using the API, **register your device** to get a JWT token:

```http
POST /auth/login
Content-Type: application/json

{
  "device_id": "your_unique_device_id"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Device authenticated successfully",
  "data": {
    "access_token": "your_jwt_token",
    "device_id": "your_unique_device_id",
    "is_new_device": false
  }
}
```

Use this token in the `Authorization: Bearer ...` header for all protected endpoints.

---

## 🎨 Generate Album Poster

```http
POST /generate_album_poster
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "album_name": "Blonde",
  "artist_name": "Frank Ocean",
  "theme": "Light",         // Optional: Light, Dark, Catppuccin, etc.
  "indexing": false,        // Optional
  "accent": false,          // Optional
  "custom_cover": null      // Optional: URL or base64 image
}
```

**Response:**
```json
{
  "success": true,
  "message": "Album poster generated successfully!",
  "data": {
    "filePath": "albums/blonde_frank_ocean.png",
    "thumbhash": "LKO2?U%2Tw=w]~RBVZRi};RPxuwH",
    "type": "album_poster"
  }
}
```

---

## 🎵 Generate Track Poster

```http
POST /generate_track_poster
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "track_name": "Demons",
  "artist_name": "Coldplay",
  "theme": "Dark"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Track poster generated successfully!",
  "data": {
    "filePath": "tracks/demons_coldplay.png",
    "thumbhash": "LKO2?U%2Tw=w]~RBVZRi};RPxuwH",
    "type": "track_poster"
  }
}
```

---

## 🖼️ Download Poster as Base64

```http
POST /get_poster
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "filename": "albums/blonde_frank_ocean.png"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Image retrieved successfully",
  "data": {
    "image": "<base64-encoded-image>",
    "thumbhash": "LKO2?U%2Tw=w]~RBVZRi};RPxuwH",
    "filename": "albums/blonde_frank_ocean.png"
  }
}
```

---

## 🛡️ Protected Example

```http
GET /protected
Authorization: Bearer <your_token>
```

---

## 🧑‍💻 For Developers

- **Poster themes:** Light, Dark, Catppuccin, Gruvbox, Nord, RosePine, Everforest
- **Caching:** Redis is used for both metadata and poster responses
- **Rate limiting:** 10,000 requests/hour per IP (configurable)
- **Swagger docs:** Available if you want to explore interactively

---

## 🐞 Troubleshooting

- **401 Unauthorized?**  
  Make sure your JWT token is valid and sent in the `Authorization` header.

- **500 Internal Server Error?**  
  Check your `.env` values, Spotify credentials, and Redis server.

- **Poster not found?**  
  Double-check your album/track names and spelling.

---

## ❤️ Contributing

PRs are welcome!  
If you have ideas for new features, themes, or bug fixes, open an issue or submit a pull request.

---

## 📜 License

MIT License

---

**Made with 🎧 and ☕ by [MA3V1N](https://github.com/MA3V1N)**

---

