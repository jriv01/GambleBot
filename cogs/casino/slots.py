"""Cog that implements a slots machine."""

import asyncio
import random

import discord
from discord import Color, app_commands
from discord.ext import commands

from common.casino_cog import CasinoCog


class Symbol:
    """A slots symbol.

    Attributes:
        emoji: Emoji representation of this symbol.
        multiplier: How much to multiply a bet by.
        probability: Probability of hitting this symbol.
        color: discord.Color associated with this symbol.
    """

    def __init__(
        self,
        emoji: str,
        multiplier: float,
        probability: float,
        color: discord.Color,
    ):
        self.emoji = emoji
        self.multiplier = multiplier
        self.probability = probability
        self.color = color

    def __str__(self) -> str:
        return self.emoji

    def get_payout(self, bet: int) -> int:
        """Get payout from hitting this symbol."""
        return int(bet * self.multiplier)


class SlotsCog(CasinoCog):
    """A cog that implements slots functionality."""

    # List of all possible symbols
    symbols = [
        Symbol(
            emoji=":skull_crossbones:",
            multiplier=0.0,
            probability=0.30,
            color=Color.dark_gray(),
        ),
        Symbol(
            emoji=":fish:",
            multiplier=0.25,
            probability=0.20,
            color=Color.dark_blue(),
        ),
        Symbol(
            emoji=":billed_cap:",
            multiplier=0.5,
            probability=0.14,
            color=Color.blue(),
        ),
        Symbol(
            emoji=":coconut:",
            multiplier=0.75,
            probability=0.10,
            color=Color.orange(),
        ),
        Symbol(
            emoji=":moai:",
            multiplier=1.0,
            probability=0.10,
            color=Color.light_gray(),
        ),
        Symbol(
            emoji=":muscle:",
            multiplier=1.25,
            probability=0.075,
            color=Color.yellow(),
        ),
        Symbol(emoji=":100:", multiplier=2, probability=0.05, color=Color.red()),
        Symbol(
            emoji=":money_bag:",
            multiplier=10,
            probability=0.025,
            color=Color.yellow(),
        ),
        Symbol(
            emoji=":gem:",
            multiplier=100.0,
            probability=0.01,
            color=Color.blue(),
        ),
    ]

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.num_symbols = 7
        self.active_sessions = set()

    @app_commands.command(name="slots", description="...")
    async def slots(self, interaction: discord.Interaction, bet: int) -> None:
        """Slash command for playing slots.

        Args:
            interaction: Discord interaction to handle.
            bet: Amount user wishes to bet.
        """
        # Validate bet
        if not await self.validate_bet(interaction, bet):
            return

        # Check if user is already spinning the wheel
        user = interaction.user
        guild = interaction.guild
        token = (user.id, guild.id)
        if token in self.active_sessions:
            await interaction.response.send_message(
                "You are already spinning the wheel!", ephemeral=True
            )
            return
        self.active_sessions.add(token)

        # Pay bet
        await self.economy.withdraw(user, bet)

        # Pick random symbols to start with
        active_symbols = random.choices(
            self.symbols,
            [sym.probability for sym in self.symbols],
            k=self.num_symbols,
        )

        # Send initial embed
        embed = discord.Embed(title="Slots")
        embed.add_field(
            name="",
            value=self.get_slots_display(active_symbols),
        )
        await interaction.response.send_message("", embed=embed)
        message = await interaction.original_response()

        # Run the slots
        payout_symbol = await self.run_slots(active_symbols, message)
        payout = payout_symbol.get_payout(bet)
        multiplier = payout_symbol.multiplier

        # Display final results
        embed = discord.Embed(title="Slots", color=payout_symbol.color)
        embed.add_field(name="Payout:", value=payout, inline=False)
        embed.add_field(
            name="Multiplier:",
            value=f"{payout_symbol} x{multiplier}",
            inline=False,
        )
        embed.add_field(
            name="", value=self.get_slots_display(active_symbols), inline=False
        )
        await message.edit(embed=embed)

        # Make payout
        await self.economy.deposit(user, payout)

        # Remove user from active session pool
        self.active_sessions.discard(token)

    async def run_slots(
        self, active_symbols: list[Symbol], message: discord.Message
    ) -> Symbol:
        """Run a session of slots.

        Args:
            active_symbols: Symbols currently visible in wheel.
            message: Discord message to edit.

        Returns
            The symbol that was landed on.
        """
        # Variables for cycling through symbols
        start_sleep_time = 0.20
        cycles = 15
        for i in range(1, cycles + 1):
            # Pick a random symbol
            random_symbol = random.choices(
                self.symbols, [sym.probability for sym in self.symbols], k=1
            )[0]

            # Add new leftmost symbol & remove rightmost symbol
            active_symbols.pop()
            active_symbols.insert(0, random_symbol)

            # Get the current payout symbol
            current_symbol = active_symbols[self.num_symbols // 2]

            # Create embed & send message
            embed = discord.Embed(title="Slots", color=current_symbol.color)
            embed.add_field(
                name="",
                value=self.get_slots_display(active_symbols),
            )
            await message.edit(embed=embed)

            # Exponential increase in sleep time
            sleep_time = start_sleep_time * 2 ** (2 * i / cycles)
            await asyncio.sleep(sleep_time)

        # Return the payout symbol
        return active_symbols[self.num_symbols // 2]

    def get_slots_display(self, active_symbols: list[Symbol]) -> str:
        """Get string representation of slots symbols.

        Args:
            active_symbols: List of symbols to represent.

        Returns:
            String representation of current slots state.
        """
        # Build the upper border
        upper_sqs = (
            ":blue_square:" * (self.num_symbols - 1)
            + ":arrow_down_small:"
            + ":blue_square:" * (self.num_symbols - 1)
            + "\n"
        )
        # Build lower border
        lower_sqs = (
            ":blue_square:" * (self.num_symbols - 1)
            + ":arrow_up_small:"
            + ":blue_square:" * (self.num_symbols - 1)
        )
        # Build slot layout with symbols
        return (
            upper_sqs
            + ":black_medium_square:".join(map(str, active_symbols))
            + "\n"
            + lower_sqs
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SlotsCog(bot))
