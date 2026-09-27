"""Horse racing library.

Implements classes for driving a game of horse racing.
"""

import random
from typing import Optional

from lib.casino.casino_lib import Player


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
            track_length: Length of the track.
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


class HorseRacingEngine:
    """Engine driving the horse racing logic and state."""

    def __init__(self, players: set[Player]):
        self.players = players
        self.track_length = 30
        self.num_horses = 6
        self.horses: list[Horse] = []
        self.winning_horse: Optional[Horse] = None

    def initialize_game(self) -> None:
        """Set up a game of horse racing."""
        self.horses = [Horse(i + 1, self.track_length) for i in range(6)]
        self.winning_horse = None

    def step(self) -> None:
        """Advance a random horse and check if it has won the race."""
        horse = random.choice(self.horses)
        horse.advance(random.randint(4, 6))
        self.winning_horse = horse if horse.finished() else None

    def get_results(self) -> tuple[list[Player], list[Player], list[Player]]:
        """Get game results.

        Returns:
            A tuple of format (winners, losers, draws)
        """
        winners, losers = [], []
        if not self.winning_horse:
            return [], list(self.players), []

        for player in self.players:
            if player.horse == self.winning_horse.number:
                winners.append(player)
            else:
                losers.append(player)

        # Horse racing doesn't typically have ties/draws
        return winners, losers, []
