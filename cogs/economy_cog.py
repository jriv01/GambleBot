"""
Cog that implements an economy.
"""

import asyncio
import os
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands


class Economy(commands.Cog):
    """A cog that implements economy functionality"""

    def __init__(self, bot: commands.Bot, data_path=None):
        self.bot = bot
        self.database = os.path.join(data_path, "economy.db")

        self.DEFAULT_BALANCE = 500

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")

    @app_commands.command(name="funds", description="Check your funds.")
    async def funds(self, interaction: discord.Interaction):
        """Command to get a users funds."""
        user = interaction.user
        funds = await self._fetch_funds(user)
        await interaction.response.send_message(f"You have {funds} gold.")

    @app_commands.command(name="pay", description="Send money to another user.")
    async def pay(self, interaction: discord.Interaction, member: discord.User, value: int):
        has_funds = await self.validate_funds(interaction.user, value)
        if not has_funds:
            await interaction.response.send_message("You do not have enough funds for that!")
            return
        
        await self.withdraw(interaction.user, value)
        await self.deposit(member, value)

        await interaction.response.send_message(f"{interaction.user.mention} sent {member.mention} {value} gold.")

    async def validate_funds(self, user, value):
        """Check if user has enough funds."""
        funds = await self._fetch_funds(user)
        return funds >= value

    async def withdraw(self, user, value):
        if value < 0:
            return False

        has_funds = await self.validate_funds(user, value)
        if not has_funds:
            return False

        await self._update_funds(user, -value)
        return True

    async def deposit(self, user, value):
        if value < 0:
            return False

        await self._update_funds(user, value)
        return True

    async def _update_funds(self, user, delta):
        current_funds = await self._fetch_funds(user)
        new_funds = current_funds + delta

        # Make connection to database
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()

        # Set user funds
        cursor.execute(
            "UPDATE Bank SET balance = ? WHERE user_id = ?", (new_funds, user.id)
        )
        connection.commit()
        connection.close()

    async def _fetch_funds(self, user) -> int:
        # Make connection to database
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()

        # Get user funds
        cursor.execute("SELECT balance FROM Bank WHERE user_id = ?", (user.id,))
        result = cursor.fetchone()

        # Insert user is they don't already exist
        if result is None:
            cursor.execute(
                "INSERT INTO Bank (user_id, balance) VALUES (?,?)",
                (user.id, self.DEFAULT_BALANCE),
            )
            balance = self.DEFAULT_BALANCE
        else:
            balance = result[0]

        # Commit & close
        connection.commit()
        connection.close()
        return balance
