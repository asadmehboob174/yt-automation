"""Shared configuration schemas for video factory."""
from pydantic import BaseModel
from typing import Optional
import json
from pathlib import Path


class YouTubeConfig(BaseModel):
    """YouTube channel configuration."""
    channel_id: str
    default_tags: list[str]
    thumbnail_style: str


class NicheConfig(BaseModel):
    """Configuration for a specific niche/channel."""
    channel_name: str
    style_suffix: str
    voice_id: str
    anchor_image: str
    background_music: str
    youtube: YouTubeConfig


def load_channels() -> dict[str, NicheConfig]:
    """Load all channel configurations from channels.json."""
    config_path = Path(__file__).parent / "channels.json"
    with open(config_path, "r") as f:
        data = json.load(f)
    return {k: NicheConfig(**v) for k, v in data.items()}


def get_channel(niche_id: str) -> NicheConfig:
    """Get configuration for a specific niche."""
    channels = load_channels()
    if niche_id not in channels:
        raise ValueError(f"Unknown niche: {niche_id}")
    return channels[niche_id]
