"""Blackjack library.

Implements classes for driving a game of blackjack.
"""

from typing import Optional

from lib.casino.casino_lib import Card, Deck, Player


class BlackjackHand:
    """A hand of cards in blackjack."""

    def __init__(self, hand: Optional[list[Card]] = None):
        self.hand = hand or []

    @property
    def value(self) -> int:
        """Get integer value of a blackjack hand."""
        # Get number of aces & all non-ace cards
        num_aces = len([card for card in self.hand if card.rank == "Ace"])

        # Get total of all cards, assuming high-aces
        total = 0
        for card in self.hand:
            total += card.get_value(high_aces=True)

        # Adjust ace values for maximum total score
        while num_aces > 0 and total > 21:
            total -= 10
            num_aces -= 1

        return total

    def is_busted(self) -> bool:
        return self.value > 21

    def add_card(self, card: Card) -> None:
        """Add card to hand."""
        self.hand.append(card)


class BlackjackEngine:
    """Engine driving the blackjack logic and state."""

    def __init__(self, players: set[Player]):
        self.players = players
        self.deck = Deck(num_decks=2)

        self.dealer_hand = BlackjackHand()

    def initialize_game(self) -> None:
        """Set up a game of blackjack"""
        self.deck.shuffle()

        for player in self.players:
            player.hand = BlackjackHand([self.deck.draw_card(), self.deck.draw_card()])

        self.dealer_hand.add_card(self.deck.draw_card())
        self.dealer_hand.add_card(self.deck.draw_card())

    def lost_to_dealer(self, hand: BlackjackHand) -> bool:
        """Determine if a hand loses to the dealer."""
        return not self.dealer_hand.is_busted() and hand.value < self.dealer_hand.value

    def beat_dealer(self, hand: BlackjackHand) -> bool:
        """Determine if a hand beats the dealer"""
        return not hand.is_busted() and (
            self.dealer_hand.is_busted() or hand.value > self.dealer_hand.value
        )

    def hit(self, hand: BlackjackHand) -> Card:
        """Add a card to a Blackjack hand."""
        new_card = self.deck.draw_card()
        hand.add_card(new_card)
        return new_card

    def should_dealer_hit(self) -> bool:
        """Determine if a dealer should hit."""
        if all(player.hand.is_busted() for player in self.players):
            return False

        return self.dealer_hand.value < 17

    def get_results(self) -> tuple[list[Player], list[Player], list[Player]]:
        """Get game results.

        Returns:
            A tuple of format (winners, losers, draws)
        """
        winners, losers, draws = [], [], []

        for player in self.players:
            if player.hand.is_busted() or self.lost_to_dealer(player.hand):
                losers.append(player)
            elif self.beat_dealer(player.hand):
                winners.append(player)
            else:
                draws.append(player)

        return winners, losers, draws
