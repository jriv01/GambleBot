"""
Build & run a Discord bot.
"""

import asyncio
from itertools import cycle
import os

import discord
from discord.ext import commands, tasks
import dotenv

from cogs.casino.blackjack_cog import Blackjack
from cogs.casino.dice_cog import Dice
from cogs.economy_cog import Economy
from cogs.casino.horse_racing_cog import HorseRacingCog
from cogs.income_cog import Income
from cogs.pokemon.pokemon_cog import PokemonCog


dotenv.load_dotenv()

GUILD_ID = discord.Object(id=os.getenv("GUILD_ID"))

possible_status = cycle(["Poker", "Blackjack", "Roulette"])


class Client(commands.Bot):
    """Main client that joins cogs together"""

    async def on_ready(self):
        """Listen for when client is ready."""
        print(f"Logged on as {self.user}!")

        self.change_bot_status.start()

    @tasks.loop(seconds=260)
    async def change_bot_status(self):
        """Change the bot status every 30 seconds"""
        await self.change_presence(activity=discord.Game(next(possible_status)))


intents = discord.Intents.default()
intents.message_content = True

# Command prefix must still be included, even though they are "deprecated"
client = Client(command_prefix="h!", intents=intents)

@client.command()
async def sync(ctx: commands.Context):
    try:
        synced_commands = await client.tree.sync()
        res = f"Synced {len(synced_commands)} commands."
    except Exception as e:
        res = f"Error with syncing commands has occurred:\n {e}"
    print(res)
    await ctx.message.reply(content=res)


async def main():
    async with client:
        # Initialize cogs
        economy_cog = Economy(client, database=os.getenv("DATA_PATH"))
        blackjack_cog = Blackjack(client, economy_cog=economy_cog)
        dice_cog = Dice(client, economy_cog=economy_cog)
        horse_cog = HorseRacingCog(client, economy_cog=economy_cog)
        income_cog = Income(client, economy_cog=economy_cog)
        pokemon_cog = PokemonCog(client, os.getenv("DATA_PATH"))

        # Initialize client
        await client.add_cog(economy_cog)
        await client.add_cog(blackjack_cog)
        await client.add_cog(dice_cog)
        await client.add_cog(horse_cog)
        await client.add_cog(income_cog)
        await client.add_cog(pokemon_cog)
        await client.start(token=os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
