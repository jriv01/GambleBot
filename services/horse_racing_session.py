"""Provides functionality for creating, executing, and managing a session of horse racing."""

import asyncio

import discord
from discord.ext import commands

from lib.casino.casino_lib import GameSession, GameState, Player
from lib.casino.horse_racing_lib import Horse, HorseRacingEngine


class HorseRacingSession(GameSession):
    """A guild session for a horse race.

    Attributes:
        channel: Channel to send messages in.
        track_length: Length of the track.
        do_sticky: Whether to move message to bottom of the channel.
    """

    def __init__(self, bot: commands.Bot, text_channel: discord.TextChannel):
        super().__init__(bot, text_channel)
        self.do_sticky = False

    async def play_game(self) -> tuple[list[Player], list[Player], list[Player]]:
        """Run the horse race.

        Returns:
            A tuple of 3 lists, in the format ([WINNING PLAYERS],
                [LOSING PLAYERS], [TIED PLAYERS])
        """
        # Initialize horses & run the race
        self.game_state = GameState.GAME_IN_PROGRESS
        engine = HorseRacingEngine(self.players)
        engine.initialize_game()
        await self.do_race(engine)
        return engine.get_results()

    async def do_race(self, engine: HorseRacingEngine) -> Horse:
        """Run the race & return winning Horse.

        Args:
            engine: Horse racing game engine

        Returns:
            The winning horse.
        """
        # Send initial message
        message = await self.text_channel.send(self.get_display(engine))

        # Keep running until one horse has won
        while not engine.winning_horse:
            engine.step()

            # Check whether to resend the message
            # Avoids the edited messages scrolling up
            display = self.get_display(engine)
            if self.do_sticky:
                # Delete & replace the message
                await message.delete()
                message = await self.text_channel.send(display, silent=True)
                self.do_sticky = False
            else:
                await message.edit(content=display)
            await asyncio.sleep(1)

    def get_display(self, engine: HorseRacingEngine) -> str:
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
        exists_winner = engine.winning_horse is not None

        # Border
        ret = "=" * (engine.track_length + 6) + "\n"

        # Add each horse to the string
        for i, horse in enumerate(engine.horses):
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
        ret += "=" * (engine.track_length + 6)

        return ret.strip()
