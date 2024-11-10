"""
Horse racing library.

Implements functions & classes for using executing a horse racing session &
display excecution to users.
"""

import asyncio
import random

import discord

from cogs.casino.casino_lib import GameState


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

    def __init__(self, user: discord.User, bet: int, horse: int):
        self.user = user
        self.bet = bet
        self.horse = horse

    @property
    def mention(self):
        """Discord @ mention"""
        return self.user.mention


class HorseRacingSession:
    """A guild session for a horse race."""

    def __init__(self, channel: discord.TextChannel):
        self.players = set()
        self.game_state = GameState.NO_GAME
        self.channel = channel
        self.do_sticky = False
        self.track_length = 30

    def __contains__(self, user: discord.User) -> bool:
        return any([user.id == player.user.id for player in self.players])

    async def start_race(self) -> tuple[list[Player], list[Player]]:
        """Run the horse race"""
        # Initialize horses & run the race
        self.game_state = GameState.GAME_STARTED
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

        return winning_players, losing_players

    async def do_race(self, horses: list[Horse]) -> Horse:
        """Run the race & return winning Horse."""
        # Send initial message
        message = await self.channel.send(self.get_display(horses))

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
                message = await self.channel.send(display, silent=True)
                self.do_sticky = False
            else:
                await message.edit(content=display)
            await asyncio.sleep(1)

        return winning_horse

    def add_player(self, user: discord.User, bet: int, horse: int) -> bool:
        """Add a user to this session."""
        # Check if the user can be added
        if user in self:
            return False

        # Add user
        self.players.add(Player(user, bet, horse))
        return True

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
