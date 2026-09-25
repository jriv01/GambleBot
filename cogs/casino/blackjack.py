"""Cog that implements blackjack."""

import discord
from discord import app_commands
from discord.ext import commands

from common.casino_cog import MultiplayerCasinoCog
from lib.casino.blackjack_lib import BlackjackSession


class Blackjack(MultiplayerCasinoCog):
    """A cog that implements blackjack functionality.

    Attributes:
        pending_game_delay: Amount of time to wait before starting a game.
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(bot, pending_game_delay=15)

    @app_commands.command(
        name="blackjack", description="Start or join a game of Blackjack!"
    )
    async def blackjack(self, interaction: discord.Interaction, bet: int) -> None:
        """Slash command for beginning or joining a blackjack game.

        Args:
            interaction: Discord interaction to handle.
            bet: Amount user wishes to bet.
        """
        if not await self.validate_bet(interaction, bet):
            return

        await self.handle_session_entry(
            interaction,
            bet,
            BlackjackSession,
            game_name="Blackjack",
            game_command="/blackjack",
            player_kwargs={"hand": []},
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Blackjack(bot))
