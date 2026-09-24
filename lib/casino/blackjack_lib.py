"""Blackjack library.

Implements functions & classes for using executing a blackjack session &
display excecution to users.
"""

import asyncio

import discord
from discord.ext import commands

from lib.casino.casino_lib import Card, Deck, GameState


class Player:
    """A blackjack player

    Attributes:
        user: A discord user.
        bet: The amount the user bet.
        hand: The user's hand of cards.
    """

    def __init__(self, user: discord.User, bet: int, hand: list[Card] = None):
        self.user = user
        self.bet = bet
        self.hand = hand

    @property
    def mention(self):
        """Discord @ mention"""
        return self.user.mention


class BlackjackSession:
    """A guild session for blackjack.

    Attributes:
        bot: A discord bot client.
        game_state: The state of the session.
        players: Set of all players in the session.
        text_channel: The channel the session is taking place in.
        message_delay: The time to wait between sending messages.
    """

    def __init__(self, bot: commands.Bot, channel: discord.TextChannel):
        self.bot = bot
        self.game_state = GameState.GAME_PENDING
        self.players = set()  # Set of players in the game
        self.text_channel: discord.TextChannel = channel
        self.message_delay = 2  # Seconds

    def __contains__(self, user: discord.User) -> bool:
        """Check if a user is already in the session.

        Args:
            user: User to check for.

        Returns:
            Whether the user is already in the session.
        """
        return any(user.id == player.user.id for player in self.players)

    def add_player(self, user: discord.User, bet: int) -> bool:
        """Add a user to this session.

        Args:
            user: Discord user to add.
            bet: The amount the user bet.

        Returns:
            Whether or not the player was successfully added to the session.
        """
        # Check if the user can be added
        if user in self:
            return False

        # Add the user
        self.players.add(Player(user, bet))
        return True

    async def play_game(
        self,
    ) -> tuple[list[Player], list[Player], list[Player]]:
        """Play a game of blackjack.

        Returns:
            A tuple of 3 lists, in the format ([WINNING PLAYERS],
                [LOSING PLAYERS], [TIED PLAYERS])
        """
        self.game_state = GameState.GAME_STARTED
        await self.text_channel.send("Blackjack starting!")

        # Initialize the deck
        deck = Deck(num_decks=2)
        deck.shuffle()

        await self.send_pending_message("Dealing cards")

        # Draw cards for each player
        for player in self.players:
            hand = [deck.draw_card(), deck.draw_card()]
            player.hand = hand

        # Get dealer hand
        dealer_hand = [deck.draw_card(), deck.draw_card()]

        # Play each players turn
        for player in self.players:
            await self.player_turn(player, deck, dealer_hand[-1])
            await asyncio.sleep(self.message_delay)

        # Play the dealer turn
        await self.dealer_turn(dealer_hand, deck)
        dealer_value = self.get_hand_value(dealer_hand)

        # Get winners, losers, and ties
        winners, losers, ties = [], [], []
        for player in self.players:
            player_value = self.get_hand_value(player.hand)
            if (
                player_value > 21 or player_value < dealer_value < 22
            ):  # Busted or less than dealer
                losers.append(player)
            elif (
                player_value > dealer_value or dealer_value > 21
            ):  # More than dealer or dealer busted
                winners.append(player)
            else:  # Both busted or both same score
                ties.append(player)

        return winners, losers, ties

    async def player_turn(self, player: Player, deck: Deck, dealer_card: Card) -> None:
        """Go through a players turn of blackjack.

        Args:
            player: A player whose turn to play.
            deck: The deck of cards to play.
            dealer_card: Dealer card that is being shown.
        """
        # Get starting hand
        hand = player.hand
        hand_value = self.get_hand_value(hand)
        hand_display = self.get_hand_display(hand)
        action = ""

        # Show players hand & options
        message_content = "=" * 30 + "\n"
        message_content += f"[ CURRENT TURN: {player.mention} ]\n\n"
        message_content += "The dealer is currently showing...\n\t"
        message_content += (
            f"{dealer_card.emoji} {dealer_card} for a value of"
            f" {dealer_card.get_value()}\n\n"
        )
        message_content += (
            f"You drew a hand of... {hand_display}\nFor a value of" f" {hand_value}."
        )
        message_content += (
            "\n\nWould you like to HIT or STAND?" if hand_value != 21 else ""
        )
        message_content += "\n" + "=" * 30
        await self.text_channel.send(message_content)

        # Play until player busts or stands
        while hand_value < 21 and action not in ("STAND", "S"):
            try:
                response = await self.bot.wait_for(
                    "message",
                    check=(lambda message: message.author.id == player.user.id),
                    timeout=30,
                )
            except asyncio.TimeoutError:
                await self.text_channel.send(
                    f"{player.mention} took too long to reply! Their turn is" " over."
                )
                break

            # Parse player response
            action = response.content.strip().upper()
            if action not in ("HIT", "H"):
                continue

            # If player hit, then draw card
            new_card = deck.draw_card()
            hand.append(new_card)
            hand_value = self.get_hand_value(hand)
            hand_display = self.get_hand_display(hand)

            # Show player outcome and options
            message_content = "=" * 30 + "\n"
            message_content += f"[ CURRENT TURN: {player.mention} ]\n\n"
            message_content += f"You drew {new_card.emoji} {new_card}\n\n"
            message_content += "The dealer is currently showing...\n\t"
            message_content += (
                f"{dealer_card.emoji} {dealer_card} for a value of"
                f" {dealer_card.get_value()}\n\n"
            )
            if hand_value < 21:
                message_content += (
                    f"You currently have a hand of... {hand_display}\n"
                    f"For a value of {hand_value}.\n\n"
                )
                message_content += "Would you like to HIT or STAND?"
            elif hand_value > 21:
                message_content += "You busted!"
            message_content += "\n" + "=" * 30

            await self.text_channel.send(message_content.strip())

    async def dealer_turn(self, hand: list[Card], deck: Deck) -> None:
        """Go through the dealer's turn of blackjack.

        Play a full dealers turn, until the dealer can no longer draw cards.
        The dealers hand is mutated as cards are drawn.

        Args:
            hand: The dealer's hand.
            deck: The deck of cards.
        """
        # Show dealers full hand and value
        dealer_display = self.get_hand_display(hand)
        dealer_value = self.get_hand_value(hand)
        await self.send_pending_message("Revealing dealer hand")
        message_content = "=" * 30 + "\n"
        message_content += (
            f"Dealer has drawn...{dealer_display}\nFor a value of" f" {dealer_value}."
        )
        message_content += "\n" + "=" * 30
        message = await self.text_channel.send(message_content)
        await asyncio.sleep(self.message_delay)

        # Determine if there's at least one player beating the dealer
        must_draw = False
        for player in self.players:
            player_value = self.get_hand_value(player.hand)
            if dealer_value < player_value < 22:
                must_draw = True

        # Play the dealer's turn
        while must_draw and dealer_value < 17:
            # Draw a new card
            new_card = deck.draw_card()
            hand.append(new_card)
            dealer_display = self.get_hand_display(hand)
            dealer_value = self.get_hand_value(hand)

            # Show the outcome
            message_content = "=" * 30 + "\n"
            message_content += f"Dealer drew {new_card.emoji} {new_card}."
            message_content += (
                f"\n\nDealer currently has a hand of... {dealer_display}\n"
                f"For a value of {dealer_value}."
            )
            message_content += "\n" + "=" * 30
            await message.edit(content=message_content)
            await asyncio.sleep(self.message_delay)

    async def send_pending_message(self, content) -> None:
        """Send a message that gives the appearance of something loading.

        Args:
            content: Message content to send.
        """
        # Send initial message
        message = await self.text_channel.send(content)

        # Add dots periodically
        for _ in range(5):
            content += "."
            await message.edit(content=content)
            await asyncio.sleep(0.35)

    def get_hand_display(self, hand: list[Card]) -> str:
        """Get string representation of blackjack hand.

        Args:
            hand: A blackhack hand.

        Returns:
            String representation of a blackjack hand.
        """
        ret = ""
        for card in hand:
            ret += f"\n\t{card.emoji} {card}"
        return ret

    def get_hand_value(self, hand: list[Card]) -> int:
        """Get integer value of a blackjack hand.

        Args:
            hand: A blackhack hand.

        Returns:
            The value of the hand.
        """
        # Get number of aces & all non-ace cards
        num_aces = len([card for card in hand if card.rank == "Ace"])

        # Get total of all cards, assuming high-aces
        total = 0
        for card in hand:
            total += card.get_value(high_aces=True)

        # Adjust ace values for maximum total score
        while num_aces > 0 and total > 21:
            total -= 10
            num_aces -= 1

        return total
