"""
Cog that implements an economy.
"""

import discord
from discord import app_commands
from discord.ext import commands

from common.database_utilities import SqliteDatabase

DEFAULT_BALANCE = 1500


class Economy(commands.Cog):
    """A cog that implements economy functionality"""

    def __init__(self, bot: commands.Bot, database_directory: str):
        self.bot = bot
        self.database = SqliteDatabase(database_directory)

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
    async def pay(
        self, interaction: discord.Interaction, member: discord.User, value: int
    ):
        """Command to transfer funds from one user to another."""
        # Check if the user is sending money to themselves
        if interaction.user.id == member.id:
            await interaction.response.send_message(
                "Trying to send money to yourself, are you? Attempted fraud,"
                " perhaps..?"
            )
            return

        # Check if value being sent is non-negative
        if value < 0:
            await interaction.response.send_message(
                "Transactions must be non-negative.", ephemeral=True
            )
            return

        # Check if player has enough funds to make payment
        has_funds = await self.validate_funds(interaction.user, value)
        if not has_funds:
            await interaction.response.send_message(
                "You do not have enough funds for that!", ephemeral=True
            )
            return

        # Transfer money
        await self.withdraw(interaction.user, value)
        await self.deposit(member, value)
        await interaction.response.send_message(
            f"{interaction.user.mention} sent {member.mention} {value} gold."
        )

    async def validate_funds(self, user: discord.User, value: int) -> bool:
        """Check if user has enough funds."""
        funds = await self._fetch_funds(user)
        return funds >= value

    async def withdraw(self, user: discord.User, value: int) -> bool:
        """Withdraw funds from a user's balance."""
        # Validate requested value
        if value < 0:
            return False
        has_funds = await self.validate_funds(user, value)
        if not has_funds:
            return False

        # Withdraw funds
        await self._update_funds(user, -value)
        return True

    async def deposit(self, user: discord.User, value) -> bool:
        """Deposit funds into a user's balance."""
        # Validate requested value
        if value < 0:
            return False

        # Deposit funds
        await self._update_funds(user, value)
        return True

    async def _update_funds(self, user: discord.User, delta: int) -> None:
        """Update a user's balance"""
        # Get users current & new balance
        current_funds = await self._fetch_funds(user)
        new_funds = current_funds + delta

        # Update user funds
        self.database.execute_query(
            "UPDATE `Economy.UserBank` SET balance = ? WHERE user_id = ?",
            new_funds,
            user.id,
        )

    async def _fetch_funds(self, user: discord.User) -> int:
        """Get a user's balance"""
        # Get the user's funds
        result = self.database.execute_query(
            "SELECT balance FROM `Economy.UserBank` WHERE user_id = ?",
            user.id,
        )

        # Insert user is they don't already exist
        if not result:
            self.database.execute_query(
                "INSERT INTO `Economy.UserBank` (user_id, user_name,"
                " balance) VALUES (?,?,?)",
                user.id,
                user.name,
                DEFAULT_BALANCE,
            )
            balance = DEFAULT_BALANCE
        else:
            balance = result[0][0]

        return balance
