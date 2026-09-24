"""Casino library containing definitions for common or non-specific casino
elements.
"""

import dataclasses
import enum
import random
from abc import ABC, abstractmethod

import discord
from discord.ext import commands


class Player:
    """A player

    Attributes:
        user: A discord user.
        bet: The amount the user bet.
    """

    def __init__(self, user: discord.User, bet: int, **kwargs):
        self.user = user
        self.bet = bet
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def mention(self):
        """Discord @ mention"""
        return self.user.mention


class GameState(enum.Enum):
    """Represents the state of a casino game."""

    NO_GAME = 0
    GAME_PENDING = 1
    GAME_IN_PROGRESS = 2
    GAME_COMPLETED = 3


class GameSession(ABC):

    def __init__(self, bot: commands.Bot, text_channel: discord.TextChannel):
        self.bot = bot
        self.text_channel = text_channel
        self.players = set()
        self.game_state = GameState.GAME_PENDING

    def __contains__(self, user: discord.User) -> bool:
        return any(user.id == player.user.id for player in self.players)

    def add_player(self, user: discord.User, bet: int, **kwargs) -> bool:
        if user in self:
            return False
        self.players.add(Player(user, bet, **kwargs))
        return True

    @abstractmethod
    async def play_game(self) -> tuple[list[Player], list[Player], list[Player]]:
        pass


class Card:
    """A playing card.

    Attributes:
        suit: The suit of the card.
        rank: The rank of the card.
        emoji: Emoji representation of the suit.
    """

    ALL_RANKS = [
        "Ace",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "Jack",
        "Queen",
        "King",
    ]

    ALL_SUITS = ["Clubs", "Diamonds", "Hearts", "Spades"]

    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.emoji = f":{suit.lower()}:"

    def get_value(self, high_aces=True) -> int:
        """Get the value of this card.

        Args:
            high_aces: Whether to evaluate aces as 11 or 1.

        Returns:
            The value of the card.
        """
        if self.rank == "Ace":
            return 11 if high_aces else 1
        elif not self.rank.isdigit():
            return 10
        return int(self.rank)

    def __repr__(self):
        return f"{self.rank} of {self.suit}"

    def __str__(self):
        return f"{self.rank} of {self.suit}"


class Deck:
    """A deck of cards.

    Attributes:
        cards: A list of Card instances.
    """

    def __init__(self, num_decks: int = 1):
        """Initialize a deck instance.

        Args:
            num_decks: Number of decks to use.
        """
        # Build deck
        self.cards = []
        for _ in range(num_decks):
            for suit in Card.ALL_SUITS:
                for rank in Card.ALL_RANKS:
                    self.cards.append(Card(suit, rank))

    def shuffle(self) -> None:
        """Shuffle the deck of cards."""
        random.shuffle(self.cards)

    def draw_card(self) -> Card:
        """Draw a Card from the top of the deck.

        Returns:
            The Card at the top of the stack.
        """
        return self.cards.pop()
