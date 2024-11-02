"""
Build & run a Discord bot.
"""
import asyncio
from itertools import cycle
import os

import discord
from discord.ext import commands, tasks
import dotenv

from cogs.blackjack_cog import Blackjack


dotenv.load_dotenv()

GUILD_ID = discord.Object(id=os.getenv("GUILD_ID"))

possible_status = cycle(["Poker", "Blackjack", "Horse Racing", "Florjon"])


class Client(commands.Bot):
    """Main client that joins cogs together"""
    async def on_ready(self):
        """Listen for when client is ready."""
        print(f"Logged on as {self.user}!")

        self.change_bot_status.start()

        try:
            synced_commands = await self.tree.sync(guild=GUILD_ID)
            print(f"Synced {len(synced_commands)} commands")
        except Exception as e:
            print("Error with syncing commands has occurred:\n", e)


    async def on_message(self, message: discord.Message):
        """Listen for messages."""
        # Ignore bots own messages
        if message.author == self.user:
            return

        if message.content.startswith("hello"):
            await message.channel.send(f"Hi there {message.author}!")

    @tasks.loop(seconds=30)
    async def change_bot_status(self):
        """Change the bot status every 30 seconds"""
        await self.change_presence(activity=discord.Game(next(possible_status)))


intents = discord.Intents.default()
intents.message_content = True

# Command prefix must still be included, even though they are "deprecated"
client = Client(command_prefix="!", intents=intents)

async def main():
    async with client:
        await client.add_cog(Blackjack(client), guild=GUILD_ID)
        await client.start(token=os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
