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
from cogs.dice_cog import Dice
from cogs.economy_cog import Economy
from cogs.horse_racing_cog import HorseRacing


dotenv.load_dotenv()

GUILD_ID = discord.Object(id=os.getenv("GUILD_ID"))

possible_status = cycle(["Florjon", "Carlos", "Kimberly"])


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

    @tasks.loop(seconds=260)
    async def change_bot_status(self):
        """Change the bot status every 30 seconds"""
        await self.change_presence(activity=discord.Game(next(possible_status)))


intents = discord.Intents.default()
intents.message_content = True

# Command prefix must still be included, even though they are "deprecated"
client = Client(command_prefix="h!", intents=intents)


async def main():
    async with client:
        # Initialize cogs
        economy_cog = Economy(client, data_path=os.getenv("DATA_PATH"))
        blackjack_cog = Blackjack(client, economy_cog=economy_cog)
        dice_cog = Dice(client, economy_cog=economy_cog)
        horse_cog = HorseRacing(client, economy_cog=economy_cog)

        # Initialize client
        await client.add_cog(economy_cog, guild=GUILD_ID)
        await client.add_cog(blackjack_cog, guild=GUILD_ID)
        await client.add_cog(dice_cog, guild=GUILD_ID)
        await client.add_cog(horse_cog, guild=GUILD_ID)
        await client.start(token=os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
