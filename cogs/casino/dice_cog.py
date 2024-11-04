"""
Cog that implements dice rolls.
"""

import random

import discord
from discord import app_commands
from discord.ext import commands

from cogs.economy_cog import Economy


class Dice(commands.Cog):
    """A cog that implements dice functionality"""

    def __init__(self, bot: commands.Bot, economy_cog: Economy):
        self.bot = bot
        self.economy = economy_cog

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")

    @app_commands.command(
        name="dice", description="Roll 4 or higher to win"
    )
    async def dice(self, interaction: discord.Interaction, bet: int):
        """Slash command for beginning or joining a blackjack game."""
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

        dice_roll = random.randint(1, 6)
        if dice_roll >= 4:
            await interaction.response.send_message(
                f"{user.mention} rolled a {dice_roll} and won {bet}!"
            )
            await self.economy.deposit(user, bet)
        else:
            await interaction.response.send_message(
                f"{user.mention} rolled a {dice_roll} and lost {bet}!"
            )
            await self.economy.withdraw(user, bet)