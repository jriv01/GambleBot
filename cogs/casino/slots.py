"""Cog that implements a 3-reel slot machine."""

import asyncio
import logging
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from common.casino_cog import BaseCasinoCog
from common.emoji_utilities import EMOJI_DIR
from lib.casino import slots_lib
from lib.casino.slots_lib import SpinResult
from services.slots_card import (
    SPINNING_EMOJI_NAME,
    SpinAgainView,
    create_spinning_view,
    get_emoji_name,
)

# Seconds between reels stopping, and before the last reel stops
REEL_STOP_DELAY = 0.5
LAST_REEL_DELAY = 0.8


class SlotsCog(BaseCasinoCog):
    """A cog that implements slots functionality.

    Attributes:
        active_spins: IDs of users whose reels are currently spinning.
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.active_spins: set[int] = set()

    def get_emoji_files(self) -> dict[str, Path]:
        """Get the image file for each custom emoji, by emoji name.

        Any emoji that can't be loaded falls back to the symbol's default
        emoji, or to random symbols for the spinning reel.
        """
        files = super().get_emoji_files()
        files[SPINNING_EMOJI_NAME] = EMOJI_DIR / f"{SPINNING_EMOJI_NAME}.gif"
        for symbol in slots_lib.SYMBOLS:
            name = get_emoji_name(symbol)
            files[name] = EMOJI_DIR / f"{name}.png"
        return files

    @app_commands.command(name="slots", description="Spin a 3-reel slot machine!")
    @app_commands.describe(
        bet="Gold to bet on each row",
        rows="How many rows to play at once, each a separate bet",
    )
    async def slots(
        self,
        interaction: discord.Interaction,
        bet: app_commands.Range[int, 1],
        rows: app_commands.Range[int, 1, slots_lib.MAX_ROWS] = 1,
    ) -> None:
        """Slash command for playing slots.

        Args:
            interaction: Discord interaction to handle.
            bet: Amount user wishes to bet on each row.
            rows: Number of rows to play.
        """
        await self.play_spin(interaction, bet, rows)

    async def play_spin(
        self, interaction: discord.Interaction, bet: int, num_rows: int
    ) -> bool:
        """Play one spin, from the /slots command or the "Spin again" button.

        Args:
            interaction: Discord interaction to handle.
            bet: Amount user wishes to bet on each row.
            num_rows: Number of rows to play.

        Returns:
            Whether the reels were spun.
        """
        user = interaction.user
        if await self.reject_if_spinning(interaction):
            return False

        # Always free the user, even if the spin fails part way through
        self.active_spins.add(user.id)
        try:
            total_bet = bet * num_rows
            if not await self.validate_bet(interaction, total_bet):
                return False

            # Reply before the rest of the database work, since Discord only
            # waits 3 seconds for the first reply
            await interaction.response.defer()
            if not await self.take_bet(interaction, total_bet):
                return False

            # Pay out before animating, so a failed message edit can't lose
            # the player's winnings
            result = slots_lib.play(bet, num_rows)
            await self.economy.deposit(user, result.total_payout)
            await self.show_spin(interaction, result)
            return True
        finally:
            self.active_spins.discard(user.id)

    async def reject_if_spinning(self, interaction: discord.Interaction) -> bool:
        """Tell the user to wait if their reels are already spinning.

        Args:
            interaction: Discord interaction to handle.

        Returns:
            Whether the user's reels are already spinning.
        """
        if interaction.user.id not in self.active_spins:
            return False

        await interaction.response.send_message(
            "Your reels are already spinning!", ephemeral=True
        )
        return True

    async def take_bet(self, interaction: discord.Interaction, total_bet: int) -> bool:
        """Withdraw a validated bet, or tell the user they can't afford it.

        Only fails if the user's balance dropped since the bet was validated.

        Args:
            interaction: Deferred Discord interaction to handle.
            total_bet: Amount to bet across every row.

        Returns:
            Whether the bet was taken.
        """
        if await self.economy.withdraw(interaction.user, total_bet):
            return True

        # A deferred /slots command shows "thinking...", which would stay up
        if interaction.type is not discord.InteractionType.component:
            await interaction.delete_original_response()
        await self.send_bet_error(interaction, self.get_not_enough_funds_message())
        return False

    async def show_spin(
        self, interaction: discord.Interaction, result: SpinResult
    ) -> None:
        """Animate the reels stopping one at a time, then show the result.

        Every frame edits the interaction's own message: a new one for a
        /slots command, or the previous spin's for a "Spin again" press, so
        the channel doesn't fill up with slots. These edits also don't count
        against the channel's shared message rate limit.

        Args:
            interaction: Deferred Discord interaction to handle.
            result: Outcome of the spin.
        """
        try:
            await self.animate_reels(interaction, result)
        except discord.HTTPException:
            # The winnings are already paid, so skip ahead to the result
            logging.exception("Slots animation failed, showing the result")

        view = SpinAgainView(self, interaction.user, result)
        view.message = await interaction.edit_original_response(view=view)

    async def animate_reels(
        self, interaction: discord.Interaction, result: SpinResult
    ) -> None:
        """Show the reels spinning, then stopping from left to right.

        Args:
            interaction: Deferred Discord interaction to handle.
            result: Outcome the reels stop on.
        """
        for stopped_reels in range(slots_lib.NUM_REELS):
            is_last_reel = stopped_reels == slots_lib.NUM_REELS - 1
            delay = LAST_REEL_DELAY if is_last_reel else REEL_STOP_DELAY
            view = create_spinning_view(result, stopped_reels, self.emojis)
            await run_for_at_least(interaction.edit_original_response(view=view), delay)


async def run_for_at_least(coroutine: Coroutine[Any, Any, Any], seconds: float):
    """Await a coroutine, taking at least the given number of seconds.

    Args:
        coroutine: Coroutine to run.
        seconds: Minimum time to take.

    Returns:
        The coroutine's result.
    """
    result, _ = await asyncio.gather(coroutine, asyncio.sleep(seconds))
    return result


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SlotsCog(bot))
