"""Base cog implementations for singleplayer and multiple casino games."""

import asyncio
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands

from common import emoji_utilities
from common.base_cog import BaseCog
from lib.casino.casino_lib import GameSession, GameState, Player

# Shown when a player bets more than they have. Art: "cat_laughing" by
# kitsune on emoji.gg (https://emoji.gg/emoji/50009-cat-laughing).
BROKIE_EMOJI_NAME = "cat_laughing"
BROKIE_FALLBACK_EMOJI = "😹🫵"


class BaseCasinoCog(BaseCog):
    """Base cog class providing common logic for Casino cogs.

    Attributes:
        emojis: Custom emojis by name, loaded from get_emoji_files().
    """

    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.emojis: dict[str, str] = {}

    async def cog_load(self) -> None:
        self.emojis = await emoji_utilities.load_emojis(
            self.bot, self.get_emoji_files()
        )

    def get_emoji_files(self) -> dict[str, Path]:
        """Get the image file for each custom emoji this cog uses, by name."""
        brokie_file = emoji_utilities.EMOJI_DIR / f"{BROKIE_EMOJI_NAME}.png"
        return {BROKIE_EMOJI_NAME: brokie_file}

    def get_not_enough_funds_message(self) -> str:
        """Get the message for a bet the player can't afford."""
        emoji = self.emojis.get(BROKIE_EMOJI_NAME, BROKIE_FALLBACK_EMOJI)
        return f"You can't do that, brokie {emoji}"

    async def validate_bet(self, interaction: discord.Interaction, bet: int) -> bool:
        """Validate that a player bet is non-negative and available.

        Args:
            interaction: Discord interaction to handle.
            bet: The amount to bet.

        Returns:
            True if the bet is valid, False otherwise.
        """
        if bet < 0:
            await self.send_bet_error(interaction, "Bets must be at least 0 gold.")
            return False

        has_funds = await self.economy.validate_funds(interaction.user, bet)
        if not has_funds:
            await self.send_bet_error(
                interaction, self.get_not_enough_funds_message()
            )
            return False

        return True

    async def send_bet_error(
        self, interaction: discord.Interaction, message: str
    ) -> None:
        """Tell the player why their bet was refused, visible only to them.

        Works whether or not the interaction has already been responded to.

        Args:
            interaction: Discord interaction to handle.
            message: Reason the bet was refused.
        """
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


class MultiplayerCasinoCog(BaseCasinoCog):
    """Cog providing common logic for multiplayer Casino cogs."""

    def __init__(self, bot: commands.Bot, pending_game_delay: int):
        super().__init__(bot)
        self.pending_game_delay = pending_game_delay
        self.guild_sessions: dict[int, Any] = {}

    def register_session(
        self, guild: discord.Guild, session: type[GameSession]
    ) -> None:
        """Register an active game session for a guild.

        Args:
            guild: The guild to register the session in.
            session: The session instance to register.
        """
        self.guild_sessions[guild.id] = session

    def get_session(self, guild: discord.Guild) -> GameSession | None:
        """Get the active game session for a guild.

        Args:
            guild: The guild to retrieve the session for.

        Returns:
            The active GameSession, or None if no session exists.
        """
        return self.guild_sessions.get(guild.id, None)

    def destroy_session(self, guild: discord.Guild) -> None:
        """Remove and clean up the active session for a guild.

        Args:
            guild: The guild whose session should be removed.
        """
        self.guild_sessions.pop(guild.id)

    async def handle_session_entry(
        self,
        interaction: discord.Interaction,
        bet: int,
        session_cls: type[GameSession],
        game_name: str,
        game_command: str,
        player_kwargs: dict | None = None,
    ) -> None:
        """
        Handle player entry into a new or pending game session.

        Args:
            interaction: Discord interaction to respond to.
            bet: Amount bet by the player.
            session_cls: Game session class to instantiate.
            game_name: Name of the game being played.
            game_command: Slash command used to join the game.
            player_kwargs: Additional keyword arguments for player setup.
        """
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
                    "You are already part of this game!", ephemeral=True
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

    async def run_game_cycle(
        self, guild: discord.Guild, channel: discord.TextChannel
    ) -> None:
        """Execute and manage the game loop.

        Args:
            guild: The guild hosting the game.
            channel: Discord channel where the game output is posted.
        """
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
        winners: list[Player],
        losers: list[Player],
        ties: list[Player],
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
