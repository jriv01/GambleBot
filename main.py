"""
Build & run a Discord bot.
"""

import asyncio
from itertools import cycle
import logging
import os
import traceback
import sys


import discord
from discord.ext import commands, tasks
import dotenv

from cogs.casino.blackjack_cog import Blackjack
from cogs.casino.dice_cog import Dice
from cogs.casino.horse_racing_cog import HorseRacingCog
from cogs.casino.slots_cog import SlotsCog
from cogs.economy_cog import Economy
from cogs.income_cog import Income
from cogs.random_message_cog import RandomMessageCog
from cogs.pokemon.pokemon_cog import PokemonCog


class Client(commands.Bot):
    """Main client that joins cogs together"""

    async def on_ready(self):
        """Listen for when client is ready."""
        print(f"Logged on as {self.user}!")

        self.change_bot_status.start()

    async def setup_hook(self):
        self.tree.on_error = self.on_app_command_error

    @tasks.loop(seconds=180)
    async def change_bot_status(self):
        """Change the bot status every 3 minutes"""
        await self.change_presence(activity=discord.Game(next(possible_status)))

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """
        Handle errors in app commands

        Args:
            interaction: The discord interaction associated with the app command
            error: The error that occured
        """
        if isinstance(error, discord.app_commands.CommandInvokeError):
            error = error.original

        command_name = interaction.command.name if interaction.command else "Unknown"
        logging.error("Exception in slash command %s", command_name)
        traceback.print_exception(
            type(error), error, error.__traceback__, file=sys.stderr
        )

        message = f"Internal error occured processing `{command_name}`"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def on_error(self, event_method: str, /, *args, **kwargs) -> None:
        """
        Handle errors in event listeners

        Args:
            event_method: The event method the error occured in
            *args: The positional arguments passed to the event.
            **kwargs: The keyword arguments passed to the event.
        """
        logging.error("[Event Error] Failed in event `%s`", event_method)
        traceback.print_exc(file=sys.stderr)


dotenv.load_dotenv()
possible_status = cycle(["Poker", "Blackjack", "Roulette"])

# Create client
# Command prefix must still be included, even though they are "deprecated"
intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="h!", intents=intents)


@client.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Command to globally sync commands."""
    try:
        synced_commands = await client.tree.sync()
        res = f"Synced {len(synced_commands)} commands."
    except Exception as e:  # pylint: disable=broad-exception-caught
        res = f"Error with syncing commands has occurred:\n {e}"
    print(res)
    await ctx.message.reply(content=res)


async def main():
    """Main function."""
    async with client:
        # Initialize cogs
        economy_cog = Economy(client, database_path=os.getenv("DATA_PATH"))
        blackjack_cog = Blackjack(client, economy_cog=economy_cog)
        dice_cog = Dice(client, economy_cog=economy_cog)
        horse_cog = HorseRacingCog(client, economy_cog=economy_cog)
        slots_cog = SlotsCog(client, economy_cog=economy_cog)
        income_cog = Income(client, economy_cog=economy_cog)
        random_message_cog = RandomMessageCog(client)
        pokemon_cog = PokemonCog(client, os.getenv("DATA_PATH"))

        # Initialize client
        await client.add_cog(economy_cog)
        await client.add_cog(blackjack_cog)
        await client.add_cog(dice_cog)
        await client.add_cog(horse_cog)
        await client.add_cog(income_cog)
        await client.add_cog(random_message_cog)
        await client.add_cog(pokemon_cog)
        await client.add_cog(slots_cog)
        await client.start(token=os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
