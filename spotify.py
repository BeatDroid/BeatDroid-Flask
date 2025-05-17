# In BeatPrints/spotify.py, inside the get_track() method:
import requests
import base64
import logging
import os
import time

class Spotify:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = 0
        self.get_access_token()

    def get_access_token(self):
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode("utf-8")
        auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

        token_url = "https://accounts.spotify.com/api/token"
        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}

        result = requests.post(token_url, headers=headers, data=data)
        json_result = result.json()
        token = json_result.get("access_token")
        expires_in = json_result.get("expires_in", 3600)
        print("expires_in", expires_in)
        if not token:
            logging.error("Failed to get access token from Spotify API")
            raise Exception("Failed to get access token from Spotify API")
        logging.info(f"Spotify access token: {token}")
        logging.info(f"Token expires in: {expires_in} seconds")
        self.access_token = token
        self.token_expires_at = time.time() + expires_in - 60  # refresh 1 min before expiry

    def ensure_token(self):
        if not self.access_token or time.time() > self.token_expires_at:
            logging.info("Spotify token expired or missing, refreshing...")
            self.get_access_token()

    def get_track(self, query, limit=1):
        self.ensure_token()
        logging.info(f"get_track called with query: {query} and limit: {limit}")
        search_url = "https://api.spotify.com/v1/search"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {
            "q": query,
            "type": "track",
            "limit": limit
        }
        result = requests.get(search_url, headers=headers, params=params)
        if result.status_code == 401:
            # Token expired, refresh and retry once
            logging.info("Spotify token expired, refreshing and retrying...")
            self.get_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            result = requests.get(search_url, headers=headers, params=params)
        logging.info(f"Spotify API response status code: {result.status_code}")
        json_result = result.json()
        logging.info(f"Spotify API response: {json_result}")
        tracks = json_result.get("tracks", {}).get("items", [])
        return tracks

    def get_album(self, query, limit=1):
        self.ensure_token()
        logging.info(f"get_album called with query: {query} and limit: {limit}")
        search_url = "https://api.spotify.com/v1/search"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {
            "q": query,
            "type": "album",
            "limit": limit
        }
        result = requests.get(search_url, headers=headers, params=params)
        if result.status_code == 401:
            # Token expired, refresh and retry once
            logging.info("Spotify token expired, refreshing and retrying...")
            self.get_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            result = requests.get(search_url, headers=headers, params=params)
        logging.info(f"Spotify API response status code: {result.status_code}")
        json_result = result.json()
        logging.info(f"Spotify API response: {json_result}")
        albums = json_result.get("albums", {}).get("items", [])
        return albums