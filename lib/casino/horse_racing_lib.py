"""Horse racing library.

Implements functions & classes for using executing a horse racing session &
display excecution to users.
"""

import asyncio
import random

import discord
from discord.ext import commands

from lib.casino.casino_lib import GameSession, GameState, Player


class Horse:
    """A race horse.

    Attributes:
        number: Number assigned to this horse.
        track_length: Length of the track.
        position: Position on the track, starts at the track length.
    """

    def __init__(self, number: int, track_length: int):
        """Initialize a Horse instance.

        Args:
            number: Number assigned to this horse.
            tack_length: Length of the track.
        """
        self.number = number
        self.track_length = track_length
        self.position = track_length

    def advance(self, advancement: int) -> None:
        """Move horse down the track by specified amount.

        Args:
            advancement: Number of positions to advance by.
        """
        self.position -= advancement
        self.position = max(self.position, 0)

    def finished(self) -> bool:
        """Whether the horse reached the end of the track.

        Returns:
            If the horse is at the end of the track.
        """
        return self.position == 0

    def __str__(self):
        return (
            "-" * self.position
            + ":racehorse:"
            + "-" * (self.track_length - self.position)
        )


class HorseRacingSession(GameSession):
    """A guild session for a horse race.

    Attributes:
        channel: Channel to send messages in.
        track_length: Length of the track.
        do_sticky: Whether to move message to bottom of the channel.
    """

    def __init__(self, bot: commands.Bot, text_channel: discord.TextChannel):
        super().__init__(bot, text_channel)
        self.track_length = 30
        self.do_sticky = False

    async def play_game(self) -> tuple[list[Player], list[Player], list[Player]]:
        """Run the horse race".

        Returns:
            A tuple of 3 lists, in the format ([WINNING PLAYERS],
                [LOSING PLAYERS], [TIED PLAYERS])
        """
        # Initialize horses & run the race
        self.game_state = GameState.GAME_IN_PROGRESS
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

        return winning_players, losing_players, []

    async def do_race(self, horses: list[Horse]) -> Horse:
        """Run the race & return winning Horse.

        Args:
            horses: List of horses that will race.

        Returns:
            The winning horse.
        """
        # Send initial message
        message = await self.text_channel.send(self.get_display(horses))

        # Keep running until one horse has won
        winning_horse = None
        while not winning_horse:
            # Pick a random horse to advance by a random amount, [1,3]
            horse = random.choice(horses)
            horse.advance(random.randint(4, 6))

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
        """Build the string representing the horse race.

        Args:
            horses: List of horses in the session.

        Returns:
            String representation of the horse positions.
        """
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
