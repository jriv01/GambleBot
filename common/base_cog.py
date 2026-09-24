"""Base Cog"""

from discord.ext import commands


class BaseCog(commands.Cog):
    """Base cog providing common dependency resolution."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def economy(self):
        """Retrieve economy cog from the bot."""
        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog:
            raise RuntimeError("Economy cog not loaded.")
        return economy_cog
