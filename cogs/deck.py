import random

class Card:
    ALL_FACES = [
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

    def __init__(self, suit, face):
        self.suit = suit
        self.face = face

    def get_value(self, high_aces=True) -> int:
        if self.face == "Ace":
            return 11 if high_aces else 1
        elif not self.face.isdigit():
            return 10
        return int(self.face)

    def __repr__(self):
        return f"{self.face} of {self.suit}"

    def __str__(self):
        return f"{self.face} of {self.suit}"


class Deck:
    def __init__(self, num_decks: int = 1):

        self.cards = []
        for _ in range(num_decks):
            for suit in Card.ALL_SUITS:
                for face in Card.ALL_FACES:
                    self.cards.append(Card(suit, face))

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw_card(self) -> Card:
        return self.cards.pop(0)
