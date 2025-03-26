import os
from pathlib import Path
from typing import Optional, Union

from PIL import Image, ImageDraw
from BeatPrints import image, write
from BeatPrints.consts import *
from BeatPrints.utils import filename, organize_tracks
from BeatPrints.errors import ThemeNotFoundError
from BeatPrints.spotify import TrackMetadata, AlbumMetadata
import logging
from BeatPrints.consts import THEMES
print(THEMES)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Poster:
    """A class for generating and saving posters containing track or album information."""

    def __init__(self, save_to: str):
        """
        Initializes the Poster instance.

        Args:
            save_to (str): Default path where posters will be saved.
        """
        self.save_to = Path(save_to).expanduser().resolve()
        try:
            os.makedirs(self.save_to, exist_ok=True)
            logging.info(f"🖼️ Poster object initialized. Posters will be saved to {self.save_to}")
        except OSError as e:
            logging.error(f"Failed to create directory {self.save_to}: {e}")
            raise

    def _add_common_text(self, draw: ImageDraw.ImageDraw, metadata: Union[TrackMetadata, AlbumMetadata], color: tuple):
        """Adds common text like title, artist, and label info."""
        write.heading(draw, C_HEADING, S_MAX_HEADING_WIDTH, metadata.name.upper(), color, write.font("Bold"), S_HEADING)
        write.text(draw, C_ARTIST, metadata.artist, color, write.font("Regular"), S_ARTIST, anchor="ls")
        write.text(draw, C_LABEL, f"{metadata.released}\n{metadata.label}", color, write.font("Regular"), S_LABEL, anchor="rt")

    def track(self, metadata: TrackMetadata, lyrics: str, save_dir: Optional[str] = None, accent: bool = False, theme: str = "Light", custom_cover: Optional[str] = None) -> str:
        """Generates a poster for a track."""
        if theme not in THEMES:
            raise ThemeNotFoundError(f"Theme '{theme}' not found.")

        color, template = image.get_theme(theme)
        cover = image.cover(metadata.image, custom_cover)
        scannable = image.scannable(metadata.id, theme)

        with Image.open(template) as poster:
            poster = poster.convert("RGB")
            draw = ImageDraw.Draw(poster)
            poster.paste(cover, C_COVER)
            poster.paste(scannable, C_SPOTIFY_CODE, scannable)
            image.draw_palette(draw, cover, accent)
            self._add_common_text(draw, metadata, color)
            write.text(draw, C_DURATION, metadata.duration, color, write.font("Regular"), S_DURATION, anchor="rs")
            write.text(draw, C_LYRICS, lyrics, color, write.font("Light"), S_LYRICS, anchor="lt")

            save_path = Path(save_dir or self.save_to).expanduser().resolve()
            try:
                save_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logging.error(f"Failed to create directory {save_path}: {e}")
                raise

            name = filename(metadata.name, metadata.artist)
            poster_path = save_path / name
            try:
                poster.save(poster_path)
                logging.info(f"✨ Poster for {metadata.name} by {metadata.artist} saved to {poster_path}")
            except Exception as e:
                logging.error(f"Failed to save poster to {poster_path}: {e}")
                raise

            return str(poster_path)

    def album(self, metadata: AlbumMetadata, save_dir: Optional[str] = None, indexing: bool = False, accent: bool = False, theme: str = "Light", custom_cover: Optional[str] = None) -> str:
        """Generates a poster for an album."""
        if theme not in THEMES:
            raise ThemeNotFoundError(f"Theme '{theme}' not found.")

        color, template = image.get_theme(theme)
        cover = image.cover(metadata.image, custom_cover)
        scannable = image.scannable(metadata.id, theme, is_album=True)

        with Image.open(template) as poster:
            poster = poster.convert("RGB")
            draw = ImageDraw.Draw(poster)
            poster.paste(cover, C_COVER)
            poster.paste(scannable, C_SPOTIFY_CODE, scannable)
            image.draw_palette(draw, cover, accent)
            self._add_common_text(draw, metadata, color)

            tracklist, track_widths = organize_tracks(metadata.tracks, indexing)
            x, y = C_TRACKS
            for track_column, column_width in zip(tracklist, track_widths):
                write.text(draw, (x, y), "\n".join(track_column), color, write.font("Light"), S_TRACKS, anchor="lt", spacing=2)
                x += column_width + S_SPACING

            save_path = Path(save_dir or self.save_to).expanduser().resolve()
            try:
                save_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logging.error(f"Failed to create directory {save_path}: {e}")
                raise

            name = filename(metadata.name, metadata.artist)
            poster_path = save_path / name
            try:
                poster.save(poster_path)
                logging.info(f"✨ Album poster for {metadata.name} by {metadata.artist} saved to {poster_path}")
            except Exception as e:
                logging.error(f"Failed to save poster to {poster_path}: {e}")
                raise

            return str(poster_path)

if __name__ == "__main__":
    logging.info("Local poster.py is being used")