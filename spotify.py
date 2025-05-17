"""
Module: spotify.py

Provides functionality related to interacting with the Spotify API.
"""

import logging
import spotipy
import random
import datetime
from typing import List, Optional
from dataclasses import dataclass
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.cache_handler import MemoryCacheHandler

# Log that local file is being used
logging.info("✅ Local spotify.py from BeatPrints directory is being imported!")

@dataclass
class TrackMetadata:
    """Data structure to store metadata for a track."""
    name: str
    artist: str
    album: str
    released: str
    duration: str
    image: str
    label: str
    id: str

@dataclass
class AlbumMetadata:
    """Data structure to store metadata for an album."""
    name: str
    artist: str
    released: str
    image: str
    label: str
    id: str
    tracks: List[str]

class Spotify:
    def __init__(self, client_id: str, client_secret: str) -> None:
        """Initialize Spotify client with credentials."""
        logging.info("Spotify class __init__ called")
        
        self.credentials_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
            cache_handler=MemoryCacheHandler(),
        )
        self.spotify = spotipy.Spotify(client_credentials_manager=self.credentials_manager)
        
        # Log token info
        token_info = self.credentials_manager.get_access_token()
        logging.info(f"Got Spotify access token, expires in: {token_info['expires_in']} seconds")

    def _ensure_token(self) -> None:
        """Ensure we have a valid token before making requests."""
        try:
            # This will automatically refresh if needed
            token_info = self.credentials_manager.get_access_token()
            logging.info("Token valid, expires in: %s seconds", token_info['expires_in'])
        except Exception as e:
            logging.error(f"Error refreshing token: {e}")
            raise

    def _format_released(self, release_date: str, precision: str) -> str:
        """Format the release date based on precision."""
        date_format = {
            "day": "%Y-%m-%d",
            "month": "%Y-%m",
            "year": "%Y"
        }.get(precision, "")
        return datetime.datetime.strptime(release_date, date_format).strftime("%B %d, %Y")

    def _format_duration(self, duration_ms: int) -> str:
        """Format duration from milliseconds to MM:SS."""
        minutes = duration_ms // 60000
        seconds = (duration_ms // 1000) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def get_track(self, query: str, limit: int = 1) -> Optional[TrackMetadata]:
        """
        Get track metadata from Spotify.

        Args:
            query (str): The search query for the track. Can be:
                - Simple format: "Track Name - Artist Name"
                - Advanced format: 'track:"Track Name" artist:"Artist Name"'

        Returns:
            Optional[TrackMetadata]: Track metadata if found, None otherwise
        """
        logging.info(f"get_track called with query: {query} and limit: {limit}")
        
        # Ensure token is valid before request
        self._ensure_token()
        
        if limit < 1:
            raise ValueError("Limit must be at least 1")

        # Format query if not already in advanced format
        if 'track:' not in query and 'artist:' not in query:
            if ' - ' in query:
                track_name, artist_name = [x.strip() for x in query.split(' - ', 1)]
                query = f'track:"{track_name}" artist:"{artist_name}"'
            logging.info(f"Formatted search query: {query}")

        result = self.spotify.search(q=query, type="track", limit=limit)
        logging.info(f"Raw Spotify response: {result}")
        
        if not result or "tracks" not in result:
            logging.error(f"Invalid response from Spotify API: {result}")
            return None
            
        if not result["tracks"]["items"]:
            logging.info(f"No tracks found for query: {query}")
            # Try a more lenient search without artist filter
            if 'artist:' in query:
                simple_query = query.split('artist:')[0].strip()
                logging.info(f"Retrying with simpler query: {simple_query}")
                return self.get_track(simple_query, limit)
            return None

        try:
            track = result["tracks"]["items"][0]
            album = self.spotify.album(track["album"]["id"])
            
            logging.info(f"Found track: {track['name']} by {track['artists'][0]['name']}")
            
            metadata = TrackMetadata(
                name=track["name"],
                artist=track["artists"][0]["name"],
                album=track["album"]["name"],
                released=self._format_released(
                    track["album"]["release_date"],
                    track["album"]["release_date_precision"]
                ),
                duration=self._format_duration(track["duration_ms"]),
                image=track["album"]["images"][0]["url"],
                label=album["label"] if len(album["label"]) < 35 else track["artists"][0]["name"],
                id=track["id"]
            )
            
            return metadata
            
        except Exception as e:
            logging.error(f"Error processing track data: {str(e)}")
            return None

    def get_album(self, query: str, limit: int = 1) -> Optional[AlbumMetadata]:
        """Get album metadata from Spotify."""
        logging.info(f"get_album called with query: {query} and limit: {limit}")
        
        # Ensure token is valid before request
        self._ensure_token()
        
        if limit < 1:
            raise ValueError("Limit must be at least 1")

        result = self.spotify.search(q=query, type="album", limit=limit)
        if not result or not result["albums"]["items"]:
            return None

        album = self.spotify.album(result["albums"]["items"][0]["id"])
        tracks = [track["name"] for track in album["tracks"]["items"]]

        metadata = AlbumMetadata(
            name=album["name"],
            artist=album["artists"][0]["name"],
            released=self._format_released(
                album["release_date"],
                album["release_date_precision"]
            ),
            image=album["images"][0]["url"],
            label=album["label"] if len(album["label"]) < 35 else album["artists"][0]["name"],
            id=album["id"],
            tracks=tracks
        )
        
        return metadata