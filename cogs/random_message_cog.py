"""Cog that implements random message pull functionality."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
import random

import discord
from discord import app_commands
from discord.ext import commands


class RandomMessageCog(commands.Cog):
    """A cog that implements random message pull functionality.

    Attributes:
        bot: A discord bot client
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")

    @app_commands.command(
        name="random_message",
        description="Get a random message from this server!",
    )
    async def random_message(
        self,
        interaction: discord.Interaction,
        num_messages: int = 1,
        user: discord.Member = None,
    ):
        """Get a random message from any time in the server's history.

        Args:
            interaction: Discord interaction to handle.
            num_messages: Number of random messages to pull.
            user: Specific user to pull messages for, defaults to None.
        """

        # Check if we're looking for bot messages
        if user.bot:
            await interaction.response.send_message(
                f"Humans only! {user.name} is a bot.", ephemeral=True
            )
            return

        # Defer the interaction as command may run for extended time
        await interaction.response.defer()

        # Number of messages must be positive
        num_messages = max(1, num_messages)

        # Get creation time of the server
        creation_time = self.get_guild_creation_datetime(interaction.guild)

        # Get random messages
        outputs = []
        response_length = 0
        truncated = False
        for _ in range(num_messages):
            # TODO: What if no messages can be found?
            # Search for a random message
            message = None
            while not message:
                # Get a random date to search for messages around
                random_date = self.get_random_date_between(
                    creation_time, datetime.now(timezone.utc)
                )

                # Get a random message around that date
                message = await self.get_random_message_around(
                    random_date, interaction.guild, user
                )

            # Format the random message
            output = (
                f"{message.jump_url}\n{message.created_at.strftime('%m/%d/%y')},"
                f" {message.author.name} said:\n\n{message.content}"
            )

            # If response exceeds character limit, break
            if response_length + len(output) + len(outputs) * 26 > 1900:
                truncated = True
                break

            # Add random message to output
            outputs.append(output)
            response_length += len(output)

        # Format final output
        final_output = "\n========================\n".join(outputs)
        final_output += (
            "\n\n***[ Response has been trunctated to"
            f" {len(outputs)} random messages. ]***"
            if truncated
            else ""
        )

        # Send final output
        await interaction.followup.send(content=final_output)

    @lru_cache(maxsize=5)
    def get_guild_creation_datetime(self, guild: discord.Guild) -> datetime:
        """Get the datetime that a guild was created at.

        Args:
            guild: The guild to check

        Returns:
            The datetime the guild was created at.
        """
        return guild.created_at

    async def get_random_message_around(
        self,
        date: datetime,
        guild: discord.Guild,
        member: discord.Member | None,
    ) -> discord.Message | None:
        """Get a random message around a date.

        Args:
            date: datetime to search around.
            guild: Discord guild to search in.
            member: Discord member to search for.

        Returns:
            A random message, or None if one is not found.
        """
        # List of all potential messages.
        all_messages: list[discord.Message] = []

        # Check every text channel that bot has read permission for.
        for text_channel in guild.text_channels:
            if not text_channel.permissions_for(guild.me).read_message_history:
                continue

            # Get up to 101 messages aroudn the date
            async for message in text_channel.history(limit=101, around=date):
                # Must not be a bot, must match the member if provided, and
                # must have content
                if (
                    not message.author.bot
                    and (not member or message.author.id == member.id)
                    and message.content
                ):
                    all_messages.append(message)

        # If a message was not found, return None
        if not all_messages:
            return None

        # Return a random message
        return random.choice(all_messages)

    def get_random_date_between(
        self, start_datetime: datetime, end_datetime: datetime
    ) -> datetime:
        """Get a random datetime between two dates.

        Args:
            start_datetime: The start of the interval.
            end_datetime: The end of the interval.

        Returns:
            A random datetime in provided interval.
        """
        # Get time between the two datetimes in seconds
        delta = end_datetime - start_datetime
        seconds_delta = (delta.days * 24 * 60 * 60) + delta.seconds

        # Return a random datetime past the start of the interval.
        random_second = random.randrange(seconds_delta)
        return start_datetime + timedelta(seconds=random_second)
