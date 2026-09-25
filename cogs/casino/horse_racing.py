"""Cog that implements horse racing."""

import discord
from discord import app_commands
from discord.ext import commands

from common.casino_cog import MultiplayerCasinoCog
from lib.casino.horse_racing_lib import HorseRacingSession


class HorseRacingCog(MultiplayerCasinoCog):
    """A cog that implements horse racing functionality.

    Attributes:
        pending_game_delay: Amount of time to wait before starting a game.
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(bot, pending_game_delay=10)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for incoming messages."""
        # Ignore self
        if message.author == self.bot.user:
            return

        # Ignore guilds without a horse racing session
        session = self.get_session(message.guild)
        if not session:
            return

        # Ignore channels without a horse racing session
        if session.text_channel.id != message.channel.id:
            return

        # Tell session to avoid scrolling
        session.do_sticky = True

    @app_commands.command(name="horse_race", description="Enter a horse race")
    async def horse_race(
        self, interaction: discord.Interaction, bet: int, horse: int
    ) -> None:
        """Slash command for beginning or joining a horse racing game.

        Args:
            interaction: Discord interaction to handle.
            bet: The amount to bet.
            horse: The horse to bet on.
        """
        if not await self.validate_bet(interaction, bet):
            return

        # Validate horse
        if not 1 <= horse <= 6:
            await interaction.response.send_message(
                f"{horse} is not a valid horse number. You can bet on horses 1 - 6.",
                ephemeral=True,
            )
            return

        await self.handle_session_entry(
            interaction,
            bet,
            HorseRacingSession,
            game_name="Horse Racing",
            game_command="/horse_race",
            player_kwargs={"horse": horse},
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HorseRacingCog(bot))
