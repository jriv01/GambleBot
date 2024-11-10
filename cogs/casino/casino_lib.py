"""Casino library."""

import enum
import random


class GameState(enum.Enum):
    """Represents the state of a casino game."""

    NO_GAME = 0
    GAME_PENDING = 1
    GAME_STARTED = 2


class Card:
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
    def __init__(self, num_decks: int = 1):

        self.cards = []
        for _ in range(num_decks):
            for suit in Card.ALL_SUITS:
                for rank in Card.ALL_RANKS:
                    self.cards.append(Card(suit, rank))

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw_card(self) -> Card:
        return self.cards.pop()
