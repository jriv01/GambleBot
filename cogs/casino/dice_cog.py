"""Cog that implements dice rolls."""

import random

import discord
from discord import app_commands
from discord.ext import commands

from cogs.economy_cog import Economy


class Dice(commands.Cog):
    """A cog that implements dice functionality.

    Attributes:
        bot: A discord bot client.
        economy_cog: A commands.Cog instance for managing player funds.
    """

    def __init__(self, bot: commands.Bot, economy_cog: Economy):
        self.bot = bot
        self.economy = economy_cog

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")

    @app_commands.command(name="dice", description="Roll 4 or higher to win!")
    async def dice(self, interaction: discord.Interaction, bet: int):
        """Slash command for beginning or joining a blackjack game.

        Args:
            interation: Discord interaction to handle.
            bet: The amount user wishes to bet.
        """
        # Validate bet
        if bet < 0:
            await interaction.response.send_message(
                "Bets must be at least 0 gold.", ephemeral=True
            )
            return
        has_funds = await self.economy.validate_funds(interaction.user, bet)
        if not has_funds:
            await interaction.response.send_message(
                "You do not have enough funds to make that bet!", ephemeral=True
            )
            return

        user = interaction.user

        # Roll a random number 1 - 6
        dice_roll = random.randint(1, 6)
        if dice_roll >= 4:  # If 4 or higher, player wins
            await interaction.response.send_message(
                f"{user.mention} rolled a {dice_roll} and won {bet}!"
            )
            await self.economy.deposit(user, bet)
        else:  # If 3 or lower, player lose
            await interaction.response.send_message(
                f"{user.mention} rolled a {dice_roll} and lost {bet}!"
            )
            await self.economy.withdraw(user, bet)
