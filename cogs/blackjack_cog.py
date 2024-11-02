"""
Cog that implements blackjack.
"""

import asyncio
from enum import Enum

import discord
from discord import app_commands
from discord.ext import commands

from cogs.deck import Deck, Card


class GameState(Enum):
    """State of a blackjack game."""

    NO_GAME = 0
    GAME_PENDING = 1
    GAME_STARTED = 2


class Player:
    """A blackjack player"""

    def __init__(self, user: discord.User, bet: int, hand: list[Card] = None):
        self.user = user
        self.bet = bet
        self.hand = hand

    @property
    def mention(self):
        """Discord @ mention"""
        return self.user.mention


class Blackjack(commands.Cog):
    """A cog that implements blackjack functionality"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.game_state = GameState.NO_GAME
        self.table = set()  # Set of players in the game
        self.text_channel: discord.TextChannel = None

        self.pending_game_delay = 10  # seconds
        self.message_delay = 2 # seconds, add artificial delay between messages

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")

    @app_commands.command(
        name="blackjack", description="Start or join a game of Blackjack!"
    )
    async def blackjack(self, interaction: discord.Interaction, bet: int = 0):
        """Slash command for beginning or joining a blackjack game."""
        # TODO - Bet validation

        # Get command caller
        user = interaction.user

        # Check current state of the cog
        match self.game_state:
            case GameState.NO_GAME:  # No game exists
                # Open a new game with initial bet
                self.game_state = GameState.GAME_PENDING
                self.text_channel = interaction.channel
                self.table.add(Player(user, bet))
                await interaction.response.send_message(
                    f"{user.mention} has opened a Blackjack session with a bet of {bet}!\n\n"
                    "Use /blackjack to join!"
                )

                # Sleep & give players time to join game
                await asyncio.sleep(self.pending_game_delay)
                await interaction.channel.send("Game starting in 5 seconds!")
                await asyncio.sleep(5)

                # Start the game
                self.game_state = GameState.GAME_STARTED
                await self.play_game()
            case GameState.GAME_PENDING:  # A game exists, but hasn't started
                # Check if the player is already betting
                if user in self.table:
                    await interaction.response.send_message(
                        "You are already part of this table!", ephemeral=True
                    )
                    return

                # Add new player to table
                self.table.add(Player(user, bet))
                await interaction.response.send_message(
                    f"{user.mention} has joined the table with a bet of {bet}!"
                )
            case GameState.GAME_STARTED:  # A game exists and has already started
                await interaction.response.send_message(
                    "Game has already started! Wait until next round to join!",
                    ephemeral=True,
                )
            case _:  # Default case
                raise RuntimeError("Invalid GameState for Blackjack cog.")

    async def play_game(self) -> None:
        """Play a game of blackjack."""
        await self.send_message("Game starting!")

        # Initialize the deck
        deck = Deck(num_decks=2)
        deck.shuffle()

        # Draw cards for each player
        for player in self.table:
            # Draw two cards
            hand = [deck.draw_card(), deck.draw_card()]
            hand_value = self.get_hand_value(hand)
            hand_display = self.get_hand_display(hand)
            player.hand = hand

            # Show player their cards
            await self.send_message(
                f"{player.mention} has drawn...{hand_display}\nFor a value of {hand_value}."
            )
            await asyncio.sleep(self.message_delay)

        # Get & show dealer hand
        dealer_hand = [deck.draw_card(), deck.draw_card()]
        await self.send_message(
            f"Dealer is showing...\n\t{dealer_hand[-1]}\n"
            f"For a value of {dealer_hand[-1].get_value()}."
        )

        # Play each players turn
        for player in self.table:
            await self.player_turn(player, deck)
            await asyncio.sleep(self.message_delay)

        # Play the dealer turn
        await self.dealer_turn(dealer_hand, deck)
        dealer_value = self.get_hand_value(dealer_hand)

        # Get winners, losers, and ties
        winners, losers, ties = [], [], []
        for player in self.table:
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

        # Build & show game summary
        embed = discord.Embed(title="GAME RESULTS")
        if winners:
            text = ""
            for player in winners:
                text += f"{player.mention} won and cashed out {player.bet*2}!\n"
            embed.add_field(name="WINNERS", value=text, inline=False)
        if losers:
            text = ""
            for player in losers:
                text += f"{player.mention} lost their bet of {player.bet}.\n"
            embed.add_field(name="LOSERS", value=text, inline=False)
        if ties:
            text = ""
            for player in ties:
                text += f"{player.mention} tied and cashed out {player.bet}.\n"
            embed.add_field(name="TIES", value=text, inline=False)

        await self.send_message(embed=embed)

        # Reset game state
        self.game_state = GameState.NO_GAME
        self.table = set()
        self.text_channel = None

    async def player_turn(
        self,
        player: Player,
        deck: Deck,
    ) -> None:
        """Go through a players turn of blackjack."""

        # Get starting hand
        hand = player.hand
        hand_value = self.get_hand_value(hand)
        hand_display = self.get_hand_display(hand)
        action = ""

        # Show player current hand & options
        message = (
            f"{player.mention}\n\nYou currently have a hand of... {hand_display}\n"
            f"For a value of {hand_value}."
        )
        message += "\n\nWould you like to HIT or STAND?" if hand_value != 21 else ""
        await self.send_message(message)

        # Play until player busts or stands
        while hand_value < 21 and action != "STAND":
            try:
                response = await self.bot.wait_for(
                    "message",
                    check=(lambda message: message.author.id == player.user.id),
                    timeout=10,
                )
            except asyncio.TimeoutError:
                await self.send_message(
                    f"{player.mention} took too long to reply! Their turn is over."
                )
                break

            # Parse player response
            action = response.content.strip().upper()
            if action != "HIT":
                continue

            # If player hit, then draw card
            new_card = deck.draw_card()
            hand.append(new_card)
            hand_value = self.get_hand_value(hand)
            hand_display = self.get_hand_display(hand)

            # Show player outcome and options
            message = f"{player.mention}\n\nYou drew {new_card}."
            if hand_value < 21:
                message += (
                    f"\n\nYou currently have a hand of... {hand_display}\n"
                    f"For a value of {hand_value}."
                )
                message += "\n\nWould you like to HIT or STAND?"
            elif hand_value > 21:
                message += "\n\nYou busted!"

            await self.send_message(message)

    async def dealer_turn(
        self, hand: list[Card], deck: Deck
    ) -> None:
        """Go through the dealer's turn of blackjack.

        Play a full dealers turn, until the dealer can no longer draw cards.
        The dealers hand is mutated as cards are drawn.
        """
        # Show dealers full hand and value
        dealer_display = self.get_hand_display(hand)
        dealer_value = self.get_hand_value(hand)
        await self.send_message(
            f"Revealing dealer hand! Dealer has drawn...{dealer_display}\nFor a value of {dealer_value}."
        )
        await asyncio.sleep(self.message_delay)

        # Determine if there's at least one player beating the dealer
        must_draw = False
        for player in self.table:
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
            message = f"Dealer drew {new_card}."
            message += (
                f"\n\nDealer currently has a hand of... {dealer_display}\n"
                f"For a value of {dealer_value}."
            )
            await self.send_message(message)
            await asyncio.sleep(self.message_delay)

    async def send_message(self, content: str = None, embed: discord.Embed = None) -> None:
        """Send a message to the channel hosting blackjack game."""
        if not self.text_channel:
            print("WARNING: Tried to send message but text channel not set.")

        if content: 
            content += "\n" + "-" * 33
        await self.text_channel.send(content=content, embed=embed)

    def get_hand_display(self, hand: list[Card]) -> str:
        """Get string representation of blackjack hand."""
        return "\n\t" + "\n\t".join(map(str, hand))

    def get_hand_value(self, hand: list[Card]) -> int:
        """Get integer value of a blackjack hand."""
        num_aces = len([card for card in hand if card.face == "Ace"])
        non_aces = [card for card in hand if card.face != "Ace"]
        total = 0
        for card in non_aces:
            total += card.get_value()

        ace_total = 0
        if num_aces > 0:
            for i in range(num_aces + 1):
                ace_total = 11 * (num_aces - i) + 1 * i
                if total + ace_total < 22:
                    break

        return total + ace_total
