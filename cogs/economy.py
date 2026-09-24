"""Cog that implements an economy."""

import os

import discord
from discord import app_commands
from discord.ext import commands

from common.base_cog import BaseCog
from common.database_utilities import SqliteDatabase

DEFAULT_BALANCE = 1500


class Economy(BaseCog):
    """A cog that implements economy functionality.

    Attributes:
        database: A SqliteDatabase instance to query on.
    """

    def __init__(self, bot: commands.Bot, database_path: str):
        super().__init__(bot)
        self.database = SqliteDatabase(database_path)

    @app_commands.command(name="funds", description="Check your funds.")
    async def funds(self, interaction: discord.Interaction) -> None:
        """Command to get a users funds."""
        user = interaction.user
        funds = await self._fetch_funds(user)
        await interaction.response.send_message(f"You have {funds} gold.")

    @app_commands.command(name="pay", description="Send money to another user.")
    async def pay(
        self, interaction: discord.Interaction, member: discord.User, value: int
    ) -> None:
        """Command to transfer funds from one user to another.

        Args:
            interaction: Discord interaction to handle.
            member: Discord user to send money to.
            value: Amount to send.
        """
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
        """Check if user has enough funds.

        Args:
            user: Discord user to validate funds for.
            value: Amount to check for.
        """
        funds = await self._fetch_funds(user)
        return funds >= value

    async def withdraw(self, user: discord.User, value: int) -> bool:
        """Withdraw funds from a user's balance.

        Args:
            user: User to withdraw funds from.
            value: Amount to withdraw.

        Returns:
            Whether withdrawal was successful.
        """
        # Validate requested value
        if value < 0:
            return False
        has_funds = await self.validate_funds(user, value)
        if not has_funds:
            return False

        # Withdraw funds
        await self._update_funds(user, -value)
        return True

    async def deposit(self, user: discord.User, value: int) -> bool:
        """Deposit funds into a user's balance.

        Args:
            user: User to deposit funds into.
            value: Amount to deposit.

        Returns:
            Whether deposit was successful.
        """
        # Validate requested value
        if value < 0:
            return False

        # Deposit funds
        await self._update_funds(user, value)
        return True

    async def _update_funds(self, user: discord.User, delta: int) -> None:
        """Update a user's balance.

        Args:
            user: User to update balance for.
            delta: Change in the user's balance.
        """
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
        """Get a user's balance.

        Args:
            user: User to fetch balance for.

        Returns:
            The user's balance.
        """
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


async def setup(bot):
    data_path = os.getenv("DATA_PATH")
    await bot.add_cog(Economy(bot, database_path=data_path))
