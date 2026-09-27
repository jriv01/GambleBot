"""Slots library.

Implements the reels and payout rules for a 3-reel slot machine. Every row
is its own payline, so playing more rows places more bets at once.
"""

import random

NUM_REELS = 3
MAX_ROWS = 10

# Cherries also pay when they start a payline, without filling it
LEADING_TWO_CHERRIES_MULTIPLIER = 2
LEADING_CHERRY_MULTIPLIER = 0.5


class Symbol:
    """A slots symbol.

    Attributes:
        name: Short name of this symbol, used to look up its custom emoji.
        emoji: Default emoji representation of this symbol.
        weight: Relative chance of this symbol landing on a reel.
        three_of_a_kind_multiplier: How much to multiply a bet by when this
            symbol fills the payline.
    """

    def __init__(
        self, name: str, emoji: str, weight: int, three_of_a_kind_multiplier: float
    ):
        """Initialize a Symbol instance.

        Args:
            name: Short name of this symbol.
            emoji: Default emoji representation of this symbol.
            weight: Relative chance of this symbol landing on a reel.
            three_of_a_kind_multiplier: Bet multiplier for filling a payline.
        """
        self.name = name
        self.emoji = emoji
        self.weight = weight
        self.three_of_a_kind_multiplier = three_of_a_kind_multiplier


CHERRY = Symbol(name="cherry", emoji="🍒", weight=14, three_of_a_kind_multiplier=5)
BANANA = Symbol(name="banana", emoji="🍌", weight=11, three_of_a_kind_multiplier=9)
RASPBERRY = Symbol(
    name="raspberry", emoji="🍓", weight=8, three_of_a_kind_multiplier=20
)
BAR = Symbol(name="bar", emoji="🅱️", weight=5, three_of_a_kind_multiplier=40)
SEVEN = Symbol(name="seven", emoji="7️⃣", weight=2, three_of_a_kind_multiplier=250)

SYMBOLS = [CHERRY, BANANA, RASPBERRY, BAR, SEVEN]
JACKPOT_SYMBOL = SEVEN


class SpinResult:
    """The outcome of one spin.

    Attributes:
        bet: Amount bet on each row.
        reels: Symbols per reel, from left to right, each from top to bottom.
        payouts: Amount paid out for each row, from top to bottom.
    """

    def __init__(self, bet: int, reels: list[list[Symbol]]):
        """Initialize a SpinResult instance.

        Args:
            bet: Amount bet on each row.
            reels: Symbols per reel, as returned by spin().
        """
        self.bet = bet
        self.reels = reels
        self.payouts = [int(bet * get_multiplier(payline)) for payline in self.paylines]

    @property
    def paylines(self) -> list[list[Symbol]]:
        """Symbols on each row, from top to bottom, each from left to right."""
        return [list(row) for row in zip(*self.reels)]

    @property
    def num_rows(self) -> int:
        """Number of rows played."""
        return len(self.reels[0])

    @property
    def total_bet(self) -> int:
        """Amount bet across every row."""
        return self.bet * self.num_rows

    @property
    def total_payout(self) -> int:
        """Amount paid out across every row."""
        return sum(self.payouts)

    @property
    def net(self) -> int:
        """Amount the player gained, negative if they lost gold."""
        return self.total_payout - self.total_bet

    @property
    def is_jackpot(self) -> bool:
        """Whether any row is filled with the jackpot symbol."""
        return any(
            is_three_of_a_kind(payline, JACKPOT_SYMBOL) for payline in self.paylines
        )


def play(bet: int, num_rows: int) -> SpinResult:
    """Spin the reels and work out what each row pays.

    Args:
        bet: Amount bet on each row.
        num_rows: Number of rows to play.

    Returns:
        The outcome of the spin.
    """
    return SpinResult(bet, spin(num_rows))


def spin(num_rows: int) -> list[list[Symbol]]:
    """Spin every reel.

    Args:
        num_rows: Number of rows being played.

    Returns:
        One list of visible symbols per reel, from left to right.
    """
    return [spin_reel(num_rows) for _ in range(NUM_REELS)]


def spin_reel(num_rows: int) -> list[Symbol]:
    """Spin a single reel.

    Args:
        num_rows: Number of rows being played.

    Returns:
        The symbols visible on the reel, from top to bottom.
    """
    weights = [symbol.weight for symbol in SYMBOLS]
    return random.choices(SYMBOLS, weights, k=num_rows)


def get_multiplier(payline: list[Symbol]) -> float:
    """Get how much to multiply a bet by for a payline.

    Args:
        payline: The payline symbols, from left to right.

    Returns:
        The bet multiplier, 0 if the payline doesn't win.
    """
    first_symbol = payline[0]
    if is_three_of_a_kind(payline, first_symbol):
        return first_symbol.three_of_a_kind_multiplier
    if payline[:2] == [CHERRY, CHERRY]:
        return LEADING_TWO_CHERRIES_MULTIPLIER
    if first_symbol is CHERRY:
        return LEADING_CHERRY_MULTIPLIER
    return 0


def is_three_of_a_kind(payline: list[Symbol], symbol: Symbol) -> bool:
    """Check whether a payline is filled with one symbol.

    Args:
        payline: The payline symbols, from left to right.
        symbol: Symbol to check for.

    Returns:
        True if every symbol on the payline is the given symbol.
    """
    return all(payline_symbol is symbol for payline_symbol in payline)
