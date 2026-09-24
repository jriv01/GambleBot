import asyncio
from typing import Any

import discord
from discord.ext import commands

from common.base_cog import BaseCog
from lib.casino.casino_lib import GameSession, GameState


class BaseCasinoCog(BaseCog):

    async def validate_bet(self, interaction: discord.Interaction, bet: int) -> bool:
        """Validate that a player bet is non-negative and available."""
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

        return True


class MultiplayerCasinoCog(BaseCasinoCog):

    def __init__(self, bot: commands.Bot, pending_game_delay: int):
        super().__init__(bot)
        self.pending_game_delay = pending_game_delay
        self.guild_sessions: dict[int, Any] = {}

    def register_session(self, guild: discord.Guild, session: type[GameSession]):
        self.guild_sessions[guild.id] = session

    def get_session(self, guild: discord.Guild) -> GameSession:
        return self.guild_sessions.get(guild.id, None)

    def destroy_session(self, guild: discord.Guild):
        self.guild_sessions.pop(guild.id)

    async def handle_session_entry(
        self,
        interaction: discord.Interaction,
        bet: int,
        session_cls: type[GameSession],
        game_name: str,
        game_command: str,
        player_kwargs: dict | None = None,
    ):
        # Interaction variables
        user = interaction.user
        guild = interaction.guild

        player_kwargs = player_kwargs or {}

        # Check if session is in progress for this guild
        current_session = self.get_session(guild)
        if not current_session:
            # Create new session
            self.register_session(guild, session_cls(self.bot, interaction.channel))

            # Add player & pay bet
            self.get_session(guild).add_player(user, bet, **player_kwargs)
            await self.economy.withdraw(user, bet)

            # Send message
            await interaction.response.send_message(
                f"{user.mention} has started {game_name} with a bet of {bet}. Use {game_command} to join!"
            )
            asyncio.create_task(self.run_game_cycle(guild, interaction.channel))
        elif current_session.game_state == GameState.GAME_PENDING:
            # Check if user is already part of session
            if user in current_session:
                await interaction.response.send_message(
                    "You are already part of this race!", ephemeral=True
                )
            else:
                # Add new player to session
                current_session.add_player(user, bet, **player_kwargs)
                await self.economy.withdraw(user, bet)
                await interaction.response.send_message(
                    f"{user.mention} has joined {game_name} with a bet of {bet}. Use {game_command} to join!"
                )
            return
        else:
            await interaction.response.send_message(
                "Game has already started! Wait until next round to join!",
                ephemeral=True,
            )
            return

    async def run_game_cycle(self, guild: discord.Guild, channel: discord.TextChannel):
        # Sleep & give players time to join game
        current_session = self.get_session(guild)
        await asyncio.sleep(self.pending_game_delay - 5)
        await channel.send("Game starting in 5 seconds!")
        await asyncio.sleep(5)

        # Play the game & show results
        winners, losers, ties = await current_session.play_game()
        await self.display_results(channel, winners, losers, ties)

        # Update balances based on results
        for player in winners:
            await self.economy.deposit(player.user, player.bet * 2)
        for player in ties:
            await self.economy.deposit(player.user, player.bet)

        # Destroy the session
        self.destroy_session(guild)

    async def display_results(
        self,
        channel: discord.TextChannel,
        winners: list,
        losers: list,
        ties: list,
    ) -> None:
        """Display results of a session.

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
