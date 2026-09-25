"""Provides functionality for creating, executing, and managing a session of blackjack."""

import asyncio

import discord
from discord.ext import commands

from lib.casino.blackjack_lib import BlackjackEngine, BlackjackHand
from lib.casino.casino_lib import GameSession, GameState, Player


class BlackjackSession(GameSession):
    """A guild session for blackjack.

    Attributes:
        message_delay: The time to wait between sending messages.
    """

    def __init__(self, bot: commands.Bot, text_channel: discord.TextChannel):
        super().__init__(bot, text_channel)
        self.message_delay = 2  # Seconds

    async def play_game(self) -> tuple[list[Player], list[Player], list[Player]]:
        """Play a game of blackjack.

        Returns:
            A tuple of 3 lists, in the format ([WINNING PLAYERS],
                [LOSING PLAYERS], [TIED PLAYERS])
        """
        self.game_state = GameState.GAME_IN_PROGRESS
        await self.text_channel.send("Blackjack starting!")

        engine = BlackjackEngine(self.players)
        engine.initialize_game()

        await self.send_pending_message("Dealing cards")

        # Play each players turn
        for player in self.players:
            await self.player_turn(player, engine)
            await asyncio.sleep(self.message_delay)

        # Play the dealer turn
        await self.dealer_turn(engine)

        return engine.get_results()

    async def player_turn(self, player: Player, engine: BlackjackEngine) -> None:
        """Go through a players turn of blackjack.

        Args:
            player: A player whose turn to play.
            engine: Blackjack engine driving the game.
        """
        dealer_card = engine.dealer_hand.hand[0]
        hand_display = self.get_hand_display(player.hand)
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
            f"You drew a hand of... {hand_display}\nFor a value of"
            f" {player.hand.value}."
        )
        message_content += (
            "\n\nWould you like to HIT or STAND?" if player.hand.value != 21 else ""
        )
        message_content += "\n" + "=" * 30
        await self.text_channel.send(message_content)

        # Play until player busts or stands
        while player.hand.value < 21 and action not in ("STAND", "S"):
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
            new_card = engine.hit(player.hand)
            hand_display = self.get_hand_display(player.hand)

            # Show player outcome and options
            message_content = "=" * 30 + "\n"
            message_content += f"[ CURRENT TURN: {player.mention} ]\n\n"
            message_content += f"You drew {new_card.emoji} {new_card}\n\n"
            message_content += "The dealer is currently showing...\n\t"
            message_content += (
                f"{dealer_card.emoji} {dealer_card} for a value of"
                f" {dealer_card.get_value()}\n\n"
            )
            if player.hand.value < 21:
                message_content += (
                    f"You currently have a hand of... {hand_display}\n"
                    f"For a value of {player.hand.value}.\n\n"
                )
                message_content += "Would you like to HIT or STAND?"
            elif player.hand.is_busted():
                message_content += "You busted!"
            message_content += "\n" + "=" * 30

            await self.text_channel.send(message_content.strip())

    async def dealer_turn(self, engine: BlackjackEngine) -> None:
        """Go through the dealer's turn of blackjack.

        Play a full dealers turn, until the dealer can no longer draw cards.
        The dealers hand is mutated as cards are drawn.

        Args:
            engine: Blackjack engine driving the game.
        """
        # Show dealers full hand and value
        dealer_display = self.get_hand_display(engine.dealer_hand)
        await self.send_pending_message("Revealing dealer hand")
        message_content = "=" * 30 + "\n"
        message_content += (
            f"Dealer has drawn...{dealer_display}\nFor a value of"
            f" {engine.dealer_hand.value}."
        )
        message_content += "\n" + "=" * 30
        message = await self.text_channel.send(message_content)
        await asyncio.sleep(self.message_delay)

        # Determine if there's at least one player beating the dealer

        # Play the dealer's turn
        while engine.should_dealer_hit():
            # Draw a new card
            new_card = engine.hit(engine.dealer_hand)
            dealer_display = self.get_hand_display(engine.dealer_hand)

            # Show the outcome
            message_content = "=" * 30 + "\n"
            message_content += f"Dealer drew {new_card.emoji} {new_card}."
            message_content += (
                f"\n\nDealer currently has a hand of... {dealer_display}\n"
                f"For a value of {engine.dealer_hand.value}."
            )
            message_content += "\n" + "=" * 30
            await message.edit(content=message_content)
            await asyncio.sleep(self.message_delay)

    async def send_pending_message(self, content: str) -> None:
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

    def get_hand_display(self, hand: BlackjackHand) -> str:
        """Get string representation of blackjack hand.

        Args:
            hand: A blackjack hand.

        Returns:
            String representation of a blackjack hand.
        """
        ret = ""
        for card in hand.hand:
            ret += f"\n\t{card.emoji} {card}"
        return ret
