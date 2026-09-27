"""Cog that implements income via message counts."""

from collections import defaultdict

import discord
from discord.ext import commands, tasks

from common.base_cog import BaseCog


class Income(BaseCog):
    """A cog that implements income functionality.

    Attributes:
        pending_counts: Number of messages to cash in for each user.
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.pending_counts = defaultdict(int)

    async def cog_load(self) -> None:
        self.direct_deposit.start()

    async def cog_unload(self) -> None:
        self.direct_deposit.stop()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for incoming messages."""
        if message.author.bot:
            return
        self.pending_counts[message.author] += 1

    @tasks.loop(seconds=300)
    async def direct_deposit(self) -> None:
        """Deposit into user funds every 5 minutes"""
        to_deposit = self.pending_counts
        self.pending_counts = defaultdict(int)
        for user, count in to_deposit.items():
            await self.economy.deposit(user, count * 50)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Income(bot))
