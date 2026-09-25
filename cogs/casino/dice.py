"""Cog that implements dice rolls."""

import random

import discord
from discord import app_commands
from discord.ext import commands

from common.casino_cog import BaseCasinoCog


class Dice(BaseCasinoCog):
    """A cog that implements dice functionality."""

    @app_commands.command(name="dice", description="Roll 4 or higher to win!")
    async def dice(self, interaction: discord.Interaction, bet: int):
        """Slash command for rolling dice.

        Args:
            interaction: Discord interaction to handle.
            bet: The amount user wishes to bet.
        """
        if not await self.validate_bet(interaction, bet):
            return

        user = interaction.user

        # Roll a random number 1 - 6
        dice_roll = random.randint(1, 6)
        if dice_roll >= 4:  # If 4 or higher, player wins
            await interaction.response.send_message(
                f":game_die: {user.mention} rolled a {dice_roll} and won {bet}!"
            )
            await self.economy.deposit(user, bet)
        else:  # If 3 or lower, player lose
            await interaction.response.send_message(
                f":game_die: {user.mention} rolled a {dice_roll} and lost {bet}!"
            )
            await self.economy.withdraw(user, bet)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dice(bot))
