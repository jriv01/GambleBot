import logging
import sys
import traceback
from itertools import cycle
from pathlib import Path

import discord
from discord.ext import commands, tasks

possible_status = cycle(["Poker", "Blackjack", "Roulette"])


class Client(commands.Bot):
    """Main client that joins cogs together"""

    async def on_ready(self):
        """Listen for when client is ready."""
        print(f"Logged on as {self.user}!")

        self.change_bot_status.start()

    async def setup_hook(self):
        self.tree.on_error = self.on_app_command_error
        await self.load_extensions()

    @tasks.loop(seconds=180)
    async def change_bot_status(self):
        """Change the bot status every 3 minutes"""
        await self.change_presence(activity=discord.Game(next(possible_status)))

    async def load_extensions(self):
        """Load all extensions found in cogs directory."""
        for path in Path("./cogs").rglob("*.py"):
            if path.name.startswith(("_", ".")):
                continue
            extension = ".".join(path.with_suffix("").parts)
            try:
                await self.load_extension(extension)
                logging.info("Loaded extension: %s", extension)
            except commands.ExtensionError as e:
                logging.error("Failed to load extension: %s", extension)
                traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)

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
