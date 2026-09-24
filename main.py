"""
Build & run a Discord bot.
"""

import asyncio
import logging
import os

import discord
import dotenv

from core.bot import Client


async def main():
    """Main function."""

    dotenv.load_dotenv()

    intents = discord.Intents.default()
    intents.message_content = True

    client = Client(command_prefix="h!", intents=intents)

    logging.basicConfig(level=logging.INFO)

    async with client:
        await client.start(token=os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
