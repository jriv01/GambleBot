"""Cog that implements dice rolls."""

import random

import discord
from discord import app_commands
from discord.ext import commands


class Dice(commands.Cog):
    """A cog that implements dice functionality.

    Attributes:
        bot: A discord bot client.
        economy_cog: A commands.Cog instance for managing player funds.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economy = None

    async def cog_load(self):
        self.economy = self.bot.get_cog("Economy")
        if not self.economy:
            raise RuntimeError("Dice cog requires Economy cog to be loaded first")

    @app_commands.command(name="dice", description="Roll 4 or higher to win!")
    async def dice(self, interaction: discord.Interaction, bet: int):
        """Slash command for rolling dice.

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Dice(bot))
