"""Cog that implements blackjack."""

import asyncio
import threading

import discord
from discord import app_commands
from discord.ext import commands

from common.casino_cog import CasinoCog
from lib.casino.blackjack_lib import BlackjackSession
from lib.casino.casino_lib import GameState


class Blackjack(CasinoCog):
    """A cog that implements blackjack functionality.

    Attributes:
        pending_game_delay: Amount of time to wait before starting a game.
        guild_sessions: Map of guild ids to horse racing sessions.
        session_lock: Lock to acquire when handling sessions.
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.pending_game_delay = 15
        self.guild_sessions = {}
        self.session_lock = threading.Lock()

    @app_commands.command(
        name="blackjack", description="Start or join a game of Blackjack!"
    )
    async def blackjack(self, interaction: discord.Interaction, bet: int) -> None:
        """Slash command for beginning or joining a blackjack game.

        Args:
            interaction: Discord interaction to handle.
            bet: Amount user wishes to bet.
        """
        if not await self.validate_bet(interaction, bet):
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
                # Create new session
                self.guild_sessions[guild.id] = BlackjackSession(
                    self.bot, interaction.channel
                )

                # Add player & pay bet
                self.guild_sessions[guild.id].add_player(user, bet)
                await self.economy.withdraw(user, bet)

                # Send message
                await interaction.response.send_message(
                    f"{user.mention} has opened a Blackjack session with a bet"
                    f" of {bet}!\n\nUse /blackjack to join!"
                )
            elif current_session.game_state == GameState.GAME_PENDING:
                # Check if user is already part of session
                if user in current_session:
                    await interaction.response.send_message(
                        "You are already part of this table!", ephemeral=True
                    )
                else:
                    # Add new player to session
                    current_session.add_player(user, bet)
                    await self.economy.withdraw(user, bet)
                    await interaction.response.send_message(
                        f"{user.mention} has joined the table with a bet of" f" {bet}!"
                    )
                return
            else:
                await interaction.response.send_message(
                    "Game has already started! Wait until next round to join!",
                    ephemeral=True,
                )
                return

        # Initialize session & allow time for joining
        current_session = self.guild_sessions[guild.id]
        await asyncio.sleep(self.pending_game_delay)
        await interaction.channel.send("Blackjack starting in 5 seconds!")
        await asyncio.sleep(5)

        # Play the game & show results
        winners, losers, ties = await current_session.play_game()
        await self.display_results(interaction.channel, winners, losers, ties)

        # Update balances based on results
        for player in winners:
            await self.economy.deposit(player.user, player.bet * 2)
        for player in ties:
            await self.economy.deposit(player.user, player.bet)

        # Destroy the session
        del self.guild_sessions[guild.id]

    async def display_results(
        self,
        channel: discord.TextChannel,
        winners: list,
        losers: list,
        ties: list,
    ) -> None:
        """Display results of a blackjack session.

        Args:
            channel: Discord channel to send message in.
            winners: List of winning players.
            losers: List of losing players.
            ties: List of players who tied.
        """
        # Generate text for each potential outcome
        winner_text = ""
        loser_text = ""
        tie_text = ""
        for player in winners:
            winner_text += f"{player.mention} won and cashed out {player.bet*2} gold!\n"
        for player in losers:
            loser_text += f"{player.mention} lost their bet of {player.bet} gold.\n"
        for player in ties:
            tie_text += f"{player.mention} tied and cashed out {player.bet} gold.\n"

        # Build & send the game result embed
        embed = discord.Embed(title="GAME RESULTS")
        if winners:
            embed.add_field(name="WINNERS", value=winner_text, inline=False)
        if losers:
            embed.add_field(name="LOSERS", value=loser_text, inline=False)
        if ties:
            embed.add_field(name="TIES", value=tie_text, inline=False)
        await channel.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Blackjack(bot))
