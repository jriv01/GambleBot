"""Cog that implements income via message counts."""

from threading import Lock

import discord
from discord.ext import commands, tasks

from cogs.economy_cog import Economy


class Income(commands.Cog):
    """A cog that implements income functionality.

    Attributes:
        bot: Discord bot client.
        economy: A discord.commands.Cog instance that manages player funds.
        lock: Lock for managing message counts.
        pending_counts: Number of messages to cash in for each user.
    """

    def __init__(self, bot: commands.Bot, economy_cog: Economy):
        self.bot = bot
        self.economy = economy_cog
        self.lock = Lock()
        self.pending_counts = {}

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")
        # Task loop
        self.direct_deposit.start()

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

    @tasks.loop(seconds=600)
    async def direct_deposit(self) -> None:
        """Deposit into user funds every 10 minutes"""
        # Deposit according to number of user messages
        with self.lock:
            for user, count in self.pending_counts.items():
                await self.economy.deposit(user, count * 5)
            self.pending_counts = {}
