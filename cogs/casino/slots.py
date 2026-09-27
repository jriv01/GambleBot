"""Cog that implements a 3-reel slot machine."""

import asyncio
import logging
from collections.abc import Coroutine
from itertools import zip_longest
from pathlib import Path
from typing import Any

import discord
from discord import Color, app_commands
from discord.ext import commands

from common.casino_cog import BaseCasinoCog
from common.emoji_utilities import EMOJI_DIR
from lib.casino import slots_lib
from lib.casino.slots_lib import SpinResult, Symbol

# Seconds between reels stopping, and before the last reel stops
REEL_STOP_DELAY = 0.5
LAST_REEL_DELAY = 0.8

# Seconds the "Spin again" button stays active
SPIN_AGAIN_TIMEOUT = 60.0

# Custom emojis for the spinning reel and each symbol. Art: "slots" (resized
# to 128px) and "slotsitem1" to "slotsitem5" by Kurai on emoji.gg
# (https://emoji.gg/user/1132975955959369738).
SPINNING_EMOJI_NAME = "slots_spinning"

# Discord text isn't monospaced, so the paytable pads numbers with figure
# spaces, which are as wide as a digit
FIGURE_SPACE = " "
PAYTABLE_COLUMN_GAP = " " * 2


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


class SlotMachineView(discord.ui.LayoutView):
    """A slot machine drawn as a card, using Discord's Components V2 layout.

    Attributes:
        container: Card holding the machine's title, reels and status.
        spin_again_button: Button to spin again. It's disabled unless the
            spin has finished, and always shown so the card never changes
            height.
    """

    def __init__(
        self,
        reels_text: str,
        status: str,
        color: discord.Color,
        result: SpinResult,
        emojis: dict[str, str],
        timeout: float | None = None,
    ):
        """Initialize a SlotMachineView instance.

        Args:
            reels_text: The reels, as drawn by get_reels_text().
            status: Lines shown under the reels.
            color: Color of the card's accent bar.
            result: Outcome of the spin being shown.
            emojis: Custom emojis by name.
            timeout: Seconds until view stops accepting interaction.
        """
        super().__init__(timeout=timeout)
        bet_text = get_bet_text(result.bet, result.num_rows)
        self.spin_again_button = discord.ui.Button(
            label=f"Spin again ({bet_text})",
            emoji="🔁",
            style=discord.ButtonStyle.primary,
            disabled=True,
        )
        self.container = discord.ui.Container(
            discord.ui.TextDisplay(f"## 🎰 Slots\n{get_paytable_text(emojis)}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(reels_text),
            discord.ui.Separator(),
            discord.ui.TextDisplay(status),
            discord.ui.ActionRow(self.spin_again_button),
            accent_color=color,
        )
        self.add_item(self.container)


class SpinAgainView(SlotMachineView):
    """Finished slot machine with a button to spin again with the same bet.

    Attributes:
        cog: Slots cog that runs the spin.
        player: User who owns this slot machine.
        result: Outcome of the spin being shown.
        message: Discord message the view is attached to, set once shown.
    """

    def __init__(self, cog: SlotsCog, player: discord.User, result: SpinResult):
        """Initialize a SpinAgainView instance.

        Args:
            cog: Slots cog that runs the spin.
            player: User who owns this slot machine.
            result: Outcome of the spin to show.
        """
        reels = [render_reel(reel, cog.emojis) for reel in result.reels]
        super().__init__(
            reels_text=get_reels_text(reels, result.payouts),
            status=get_result_text(result),
            color=get_result_color(result),
            result=result,
            emojis=cog.emojis,
            timeout=SPIN_AGAIN_TIMEOUT,
        )
        self.cog = cog
        self.player = player
        self.result = result
        self.message: discord.Message | None = None
        self.spin_again_button.disabled = False
        self.spin_again_button.callback = self.spin_again_callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only let the original player press the button."""
        if interaction.user.id == self.player.id:
            return True

        await interaction.response.send_message(
            "This isn't your slot machine! Use /slots to play.", ephemeral=True
        )
        return False

    async def spin_again_callback(self, interaction: discord.Interaction) -> None:
        """Callback for "Spin again" button interaction."""
        # A double-click or a spin in another channel is only a short wait,
        # so keep this button usable
        if await self.cog.reject_if_spinning(interaction):
            return

        # The new spin attaches its own view, so retire this one
        self.stop()
        spun = await self.cog.play_spin(
            interaction, self.result.bet, self.result.num_rows
        )

        # The player can't afford this bet anymore
        if not spun:
            await self.disable_button()

    async def on_timeout(self) -> None:
        """Grey out the button after timeout."""
        await self.disable_button()

    async def disable_button(self) -> None:
        """Grey out the button, keeping the rest of the machine on screen."""
        self.spin_again_button.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass  # The message was deleted, so there's nothing to update


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


def create_spinning_view(
    result: SpinResult, stopped_reels: int, emojis: dict[str, str]
) -> SlotMachineView:
    """Create a slot machine whose reels are still spinning.

    Args:
        result: Outcome the reels will stop on.
        stopped_reels: Number of reels, from the left, that have stopped.
        emojis: Custom emojis by name.

    Returns:
        Slot machine showing the stopped reels and spinning ones on the rest.
    """
    stopped = [render_reel(reel, emojis) for reel in result.reels[:stopped_reels]]
    spinning = [
        get_spinning_reel(result.num_rows, emojis)
        for _ in range(slots_lib.NUM_REELS - stopped_reels)
    ]
    view = SlotMachineView(
        reels_text=get_reels_text(stopped + spinning),
        status=get_spinning_text(result),
        color=Color.blurple(),
        result=result,
        emojis=emojis,
    )
    # Its button is always disabled, so stop discord.py from tracking it
    view.stop()
    return view


def get_emoji_name(symbol: Symbol) -> str:
    """Get the name of a symbol's custom emoji."""
    return f"slots_{symbol.name}"


def get_emoji(symbol: Symbol, emojis: dict[str, str]) -> str:
    """Get a symbol's custom emoji, or its default one if it has none.

    Args:
        symbol: Symbol to draw.
        emojis: Custom emojis by name.

    Returns:
        The emoji to display.
    """
    return emojis.get(get_emoji_name(symbol), symbol.emoji)


def render_reel(reel: list[Symbol], emojis: dict[str, str]) -> list[str]:
    """Get the emojis to display for a reel, from top to bottom."""
    return [get_emoji(symbol, emojis) for symbol in reel]


def get_spinning_reel(num_rows: int, emojis: dict[str, str]) -> list[str]:
    """Get the emojis to display for a spinning reel.

    Args:
        num_rows: Number of rows being played.
        emojis: Custom emojis by name.

    Returns:
        The spinning reel emoji on every row, or random symbols if the bot
        doesn't have that emoji, from top to bottom.
    """
    spinning_emoji = emojis.get(SPINNING_EMOJI_NAME)
    if spinning_emoji is None:
        return render_reel(slots_lib.spin_reel(num_rows), emojis)
    return [spinning_emoji] * num_rows


def get_reels_text(reels: list[list[str]], payouts: list[int] | None = None) -> str:
    """Get the text that draws the reels.

    Args:
        reels: Emojis to display per reel.
        payouts: Amount paid out for each row, or None while spinning.

    Returns:
        One heading-sized line per row, with arrows marking each payline
        and, once the reels stop, what that row paid.
    """
    lines = []
    for row_index, row in enumerate(zip(*reels)):
        line = f"## ▶️ {''.join(row)} ◀️"
        if payouts is not None:
            line += f" {get_row_result_text(payouts[row_index])}"
        lines.append(line)
    return "\n".join(lines)


def get_row_result_text(payout: int) -> str:
    """Get the short result shown at the end of a row."""
    if payout == 0:
        return "—"
    return f"+{payout}"


def get_bet_text(bet: int, num_rows: int) -> str:
    """Get a short description of a bet, like "100 gold x 3 rows"."""
    if num_rows == 1:
        return f"{bet} gold"
    return f"{bet} gold x {num_rows} rows"


def get_spinning_text(result: SpinResult) -> str:
    """Get the status lines while spinning, laid out like the result's."""
    return f"Paid {result.total_bet} · Won …\n## Spinning..."


def get_result_text(result: SpinResult) -> str:
    """Get the status lines for a finished spin.

    Args:
        result: Outcome of the spin.

    Returns:
        What the user paid and won in total, then their net gain or loss in
        large text.
    """
    return f"Paid {result.total_bet} · Won {result.total_payout}\n## Net {result.net:+}"


def get_result_color(result: SpinResult) -> discord.Color:
    """Get the accent color for a spin's net gain or loss, or a jackpot."""
    if result.is_jackpot:
        return Color.gold()
    if result.net > 0:
        return Color.green()
    if result.net < 0:
        return Color.red()
    return Color.dark_gray()


def format_multiplier(multiplier: float) -> str:
    """Format a bet multiplier, like "250x" or "0.5x"."""
    return f"{multiplier:g}x"


def get_paytable_text(emojis: dict[str, str]) -> str:
    """Get a small-print summary of what each payline pays.

    Laid out in two columns: three of a kind on the left, cherry wins on the
    right, with the left column's multipliers padded to line up the right.

    Args:
        emojis: Custom emojis by name.

    Returns:
        One small-print line per row of the paytable.
    """
    left_symbols = [
        symbol
        for symbol in reversed(slots_lib.SYMBOLS)
        if symbol is not slots_lib.CHERRY
    ]
    width = max(
        len(format_multiplier(symbol.three_of_a_kind_multiplier))
        for symbol in left_symbols
    )
    left_column = []
    for symbol in left_symbols:
        emoji = get_emoji(symbol, emojis)
        multiplier = format_multiplier(symbol.three_of_a_kind_multiplier)
        left_column.append(f"{emoji * 3} {multiplier.rjust(width, FIGURE_SPACE)}")

    cherry = get_emoji(slots_lib.CHERRY, emojis)
    right_column = [
        f"{cherry * 3} "
        + format_multiplier(slots_lib.CHERRY.three_of_a_kind_multiplier),
        f"{cherry * 2} " + format_multiplier(slots_lib.LEADING_TWO_CHERRIES_MULTIPLIER),
        f"{cherry} " + format_multiplier(slots_lib.LEADING_CHERRY_MULTIPLIER),
    ]

    lines = [
        f"-# {left}{PAYTABLE_COLUMN_GAP}{right}".rstrip()
        for left, right in zip_longest(left_column, right_column, fillvalue="")
    ]
    return "\n".join(lines)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SlotsCog(bot))
