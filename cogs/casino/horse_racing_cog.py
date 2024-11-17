"""
Cog that implements creation and management of horse racing sessions.
"""

import asyncio
import threading

import discord
from discord import app_commands
from discord.ext import commands

from cogs.casino.casino_lib import GameState
from cogs.casino.horse_racing_lib import HorseRacingSession
from cogs.economy_cog import Economy


class HorseRacingCog(commands.Cog):
    """A cog that implements horse racing functionality"""

    def __init__(self, bot: commands.Bot, economy_cog: Economy):
        self.bot = bot
        self.economy = economy_cog
        self.players = set()
        self.pending_game_delay = 10
        self.do_sticky = False

        self.guild_sessions: dict[int, HorseRacingSession] = {}
        self.session_lock = threading.Lock()

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for incoming messages."""
        # Ignore self
        if message.author == self.bot.user:
            return

        # Ignore guilds without a horse racing session
        guild = message.guild
        if guild.id not in self.guild_sessions:
            return

        # Ignore channels without a horse racing session
        session = self.guild_sessions[guild.id]
        if session.channel.id != message.channel.id:
            return

        # Tell session to avoid scrolling
        session.do_sticky = True

    @app_commands.command(name="horse_race", description="Enter a horse race")
    async def horse_race(
        self, interaction: discord.Interaction, bet: int, horse: int
    ):
        """Slash command for beginning or joining a blackjack game."""
        # Validate bet
        # All bets must be non-negative & not greater than the users funds
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

        # Validate horse
        if not 1 <= horse <= 6:
            await interaction.response.send_message(
                f"{horse} is not a valid horse number. You can bet on horses 1"
                " - 6.",
                ephemeral=True,
            )
            return

        # Interaction variables
        user = interaction.user
        guild = interaction.guild

        # Check if session is in progress for this guild
        # Use lock to prevent creating multiple sessions
        with self.session_lock:
            # Check if session exists
            current_session = self.guild_sessions.get(guild.id, None)
            if not current_session:
                # Create new session & send message
                self.guild_sessions[guild.id] = HorseRacingSession(
                    interaction.channel
                )
                self.guild_sessions[guild.id].add_player(user, bet, horse)
                await interaction.response.send_message(
                    f"{user.mention} has opened a horse racing session with"
                    f" a bet of {bet} on horse #{horse}!\n\nUse /horse_race"
                    " to join!"
                )
            elif current_session.game_state == GameState.GAME_PENDING:
                # Check if user is already part of session
                if user in current_session:
                    await interaction.response.send_message(
                        "You are already part of this race!", ephemeral=True
                    )
                else:
                    # Add new player to session
                    current_session.add_player(user, bet, horse)
                    await interaction.response.send_message(
                        f"{user.mention} has joined the race with a bet of"
                        f" {bet} on horse #{horse}!"
                    )
                return
            else:
                await interaction.response.send_message(
                    "Game has already started! Wait until next round to join!",
                    ephemeral=True,
                )
                return

        current_session = self.guild_sessions[guild.id]

        # Sleep & give players time to join game
        await asyncio.sleep(self.pending_game_delay)
        await interaction.channel.send("Game starting in 5 seconds!")
        await asyncio.sleep(5)

        # Play the game & show results
        winners, losers = await current_session.start_race()
        await self.display_results(interaction.channel, winners, losers)

        # Update balances based on results
        for player in winners:
            await self.economy.deposit(player.user, player.bet)
        for player in losers:
            await self.economy.withdraw(player.user, player.bet)

        # Destroy the session
        del self.guild_sessions[guild.id]

    async def display_results(
        self, channel: discord.TextChannel, winners: list, losers: list
    ) -> None:
        """Display results of a horse racing session."""
        # Generate text for each potential outcome
        winning_text = ""
        losing_text = ""

        for player in winners:
            winning_text += (
                f"{player.mention} won and cashed out {player.bet*2} gold!\n"
            )
        for player in losers:
            losing_text += (
                f"{player.mention} lost their bet of {player.bet} gold.\n"
            )

        # Build & send the game result embed
        embed = discord.Embed(title="GAME RESULTS")
        if winners:
            embed.add_field(name="WINNERS", value=winning_text, inline=False)
        if losers:
            embed.add_field(name="LOSERS", value=losing_text, inline=False)
        await channel.send(embed=embed)
