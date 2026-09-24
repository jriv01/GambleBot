import discord
from discord.ext import commands

from common.base_cog import BaseCog


class CasinoCog(BaseCog):

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)

    async def validate_bet(self, interaction: discord.Interaction, bet: int) -> bool:
        """Validate that a player bet is non-negative and available."""
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

        return True
