"""Cog that implements income via message counts."""

from threading import Lock

import discord
from discord.ext import commands, tasks

from common.base_cog import BaseCog


class Income(BaseCog):
    """A cog that implements income functionality.

    Attributes:
        bot: Discord bot client.
        economy: A discord.commands.Cog instance that manages player funds.
        lock: Lock for managing message counts.
        pending_counts: Number of messages to cash in for each user.
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.lock = Lock()
        self.pending_counts = {}

    async def cog_load(self) -> None:
        self.direct_deposit.start()

    async def cog_unload(self) -> None:
        self.direct_deposit.stop()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for incoming messages."""
        if message.author == self.bot.user:
            return

        # Add 1 message count to this user
        user = message.author
        with self.lock:
            if user not in self.pending_counts:
                self.pending_counts[user] = 0
            self.pending_counts[user] += 1

    @tasks.loop(seconds=300)
    async def direct_deposit(self) -> None:
        """Deposit into user funds every 5 minutes"""
        # Deposit according to number of user messages
        with self.lock:
            for user, count in self.pending_counts.items():
                await self.economy.deposit(user, count * 50)
            self.pending_counts = {}


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Income(bot))
