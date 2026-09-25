"""
Build & run a Discord bot.
"""

import asyncio
import logging
import os

import dotenv

from core.bot import Client


async def main():
    """Main function."""

    dotenv.load_dotenv()

    client = Client()

    logging.basicConfig(level=logging.INFO)

    async with client:
        await client.start(token=os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
