"""
Cog that implements horse racing.
"""

import random
import asyncio

from enum import Enum

import discord
from discord import app_commands
from discord.ext import commands

from cogs.economy_cog import Economy


class GameState(Enum):
    """State of a horse race."""

    NO_GAME = 0
    GAME_PENDING = 1
    GAME_STARTED = 2


class Horse:
    """A race horse."""

    def __init__(self, number: int, track_length: int):
        self.position = track_length
        self.track_length = track_length
        self.number = number

    def advance(self, advancement: int):
        """Move horse down the track by specified amount."""
        self.position -= advancement
        self.position = max(self.position, 0)

    def finished(self) -> bool:
        """Whether the horse reached the end of the track."""
        return self.position == 0

    def __str__(self):
        return (
            "-" * self.position
            + ":racehorse:"
            + "-" * (self.track_length - self.position)
        )


class Player:
    """User that bet on the game."""

    def __init__(self, user, bet, horse):
        self.user = user
        self.bet = bet
        self.horse = horse

    @property
    def mention(self):
        """Discord @ mention"""
        return self.user.mention


class HorseRacing(commands.Cog):
    """A cog that implements horse racing functionality"""

    def __init__(self, bot: commands.Bot, economy_cog: Economy):
        self.bot = bot
        self.economy = economy_cog
        self.players = set()
        self.game_state = GameState.NO_GAME
        self.text_channel: discord.TextChannel = None
        self.pending_game_delay = 10
        self.do_sticky = False
        self.track_length = 30

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for incoming messages."""
        if message.author == self.bot.user:
            return
        if not self.text_channel or message.channel.id != self.text_channel.id:
            return
        self.do_sticky = True

    @app_commands.command(name="horse_race", description="Enter a horse race")
    async def horse_race(self, interaction: discord.Interaction, bet: int, horse: int):
        """Slash command for beginning or joining a blackjack game."""
        # Validate bet
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
        if not (1 <= horse <= 6):
            await interaction.response.send_message(
                f"{horse} is not a valid horse number. You can bet on horses 1 - 6.",
                ephemeral=True,
            )
            return

        # Get command caller
        user = interaction.user

        # Check current state of the cog
        match self.game_state:
            case GameState.NO_GAME:  # No game exists
                # Open a new game with initial bet
                self.game_state = GameState.GAME_PENDING
                self.text_channel = interaction.channel
                self.players.add(Player(user, bet, horse))
                await interaction.response.send_message(
                    f"{user.mention} has opened a horse racing session with a bet of {bet} on horse #{horse}!\n\n"
                    "Use /horse_race to join!"
                )

                # Sleep & give players time to join game
                await asyncio.sleep(self.pending_game_delay)
                await interaction.channel.send("Game starting in 5 seconds!")
                await asyncio.sleep(5)

                # Start the game
                self.game_state = GameState.GAME_STARTED
                await self.start_race()
            case GameState.GAME_PENDING:  # A game exists, but hasn't started
                # Check if the player is already betting
                if user in self.players:
                    await interaction.response.send_message(
                        "You are already part of this race!", ephemeral=True
                    )
                    return

                # Add new player to table
                self.players.add(Player(user, bet, horse))
                await interaction.response.send_message(
                    f"{user.mention} has joined the race with a bet of {bet} on horse #{horse}!"
                )
            case GameState.GAME_STARTED:  # A game exists and has already started
                await interaction.response.send_message(
                    "Game has already started! Wait until next round to join!",
                    ephemeral=True,
                )
            case _:  # Default case
                raise RuntimeError("Invalid GameState for Horse Racing cog.")

    async def start_race(self):
        """Run the horse race"""
        # Initialize horses & run the race
        horses = [Horse(i + 1, self.track_length) for i in range(6)]
        winning_horse = await self.do_race(horses)

        # Sort winning and losing players
        winning_players = []
        losing_players = []
        for player in self.players:
            if player.horse == winning_horse.number:
                winning_players.append(player)
            else:
                losing_players.append(player)

        # Build & show game summary
        embed = discord.Embed(title="GAME RESULTS")
        if winning_players:
            text = ""
            for player in winning_players:
                text += f"{player.mention} won and cashed out {player.bet*2} gold!\n"
            embed.add_field(name="WINNERS", value=text, inline=False)
        if losing_players:
            text = ""
            for player in losing_players:
                text += f"{player.mention} lost their bet of {player.bet} gold.\n"
            embed.add_field(name="LOSERS", value=text, inline=False)

        await self.text_channel.send(embed=embed)

        # Update balances
        for player in winning_players:
            await self.economy.deposit(player.user, player.bet)

        for player in losing_players:
            await self.economy.withdraw(player.user, player.bet)

        # Reset game state
        self.game_state = GameState.NO_GAME
        self.players = set()
        self.text_channel = None

    async def do_race(self, horses: list[Horse]) -> Horse:
        """Run the race & return winning Horse."""
        # Send initial message
        message = await self.text_channel.send(self.get_display(horses))

        # Keep running until one horse has won
        winning_horse = None
        while not winning_horse:
            # Pick a random horse to advance by a random amount, [1,3]
            horse = random.choice(horses)
            horse.advance(random.randint(2, 4))

            # Check if the chosen horse has won
            if horse.finished():
                winning_horse = horse

            # Check whether to resend the message
            # Avoids the editted messages scrolling up
            display = self.get_display(horses)
            if self.do_sticky:
                # Delete & replace the message
                await message.delete()
                message = await self.text_channel.send(display, silent=True)
                self.do_sticky = False
            else:
                await message.edit(content=display)
            await asyncio.sleep(1)

        return winning_horse

    def get_display(self, horses: list[Horse]) -> str:
        """Build the string representing the horse race."""
        # Mapping for horse numbers
        emoji_mapping = {
            0: ":one:",
            1: ":two:",
            2: ":three:",
            3: ":four:",
            4: ":five:",
            5: ":six:",
        }

        # Check if theres any winners
        exists_winner = any([horse.position == 0 for horse in horses])

        # Border
        ret = "=" * (self.track_length + 6) + "\n"

        # Add each horse to the string
        for i, horse in enumerate(horses):
            # Check if a horse has won & show winning horse
            if exists_winner:
                ret += ":trophy:" if horse.position == 0 else ":x:"
            else:
                ret += ":black_large_square:"
            # Add horse track
            ret += " "
            ret += emoji_mapping[i] + " | "
            ret += str(horse)
            ret += "\n"

        # Border
        ret += "=" * (self.track_length + 6)

        return ret.strip()
