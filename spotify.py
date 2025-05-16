# In BeatPrints/spotify.py, inside the get_track() method:
import requests
import base64
import logging
import os
class Spotify:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self.get_access_token()

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
        return token

    def get_track(self, query, limit=1):
        logging.info(f"get_track called with query: {query} and limit: {limit}")  # Log input
        search_url = "https://api.spotify.com/v1/search"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }
        params = {
            "q": query,
            "type": "track",
            "limit": limit
        }
        logging.info(f"Sending request to: {search_url} with headers: {headers} and params: {params}")  # Log request details
        result = requests.get(search_url, headers=headers, params=params)
        print(result)
        logging.info(f"Spotify API response status code: {result.status_code}")  # Log status code
        json_result = result.json()
        logging.info(f"Spotify API response: {json_result}")  # Log full response
        tracks = json_result.get("tracks", {}).get("items", [])
        return tracks