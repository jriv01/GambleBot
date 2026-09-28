"""Utilities for loading the bot's custom emojis.

Emoji images live in assets/emojis/. They're uploaded as the bot's own
application emojis, so they work in every server without being added to
each one.
"""

import logging
from pathlib import Path

import discord

EMOJI_DIR = Path(__file__).parents[1] / "assets" / "emojis"


async def load_emojis(client: discord.Client, files: dict[str, Path]) -> dict[str, str]:
    """Get the bot's custom emojis, uploading any it doesn't have yet.

    Args:
        client: Bot whose application emojis to load.
        files: Image file for each emoji, by emoji name.

    Returns:
        The emojis that were found or uploaded, by name. Any that couldn't be
        loaded are left out, so callers should fall back to a default.
    """
    try:
        existing = await client.fetch_application_emojis()
    except discord.HTTPException:
        logging.exception("Couldn't fetch emojis, using defaults instead")
        return {}

    emojis = {emoji.name: str(emoji) for emoji in existing}
    for name, path in files.items():
        if name not in emojis:
            emojis[name] = await upload_emoji(client, name, path)
    return {name: emoji for name, emoji in emojis.items() if emoji}


async def upload_emoji(client: discord.Client, name: str, path: Path) -> str | None:
    """Upload an image as one of the bot's application emojis.

    Args:
        client: Bot to upload the emoji to.
        name: Name for the emoji.
        path: Image file to upload.

    Returns:
        The emoji, or None if it couldn't be uploaded.
    """
    try:
        emoji = await client.create_application_emoji(
            name=name, image=path.read_bytes()
        )
    except (discord.HTTPException, OSError):
        logging.exception("Couldn't upload emoji %s, using default", name)
        return None
    logging.info("Uploaded application emoji: %s", name)
    return str(emoji)
