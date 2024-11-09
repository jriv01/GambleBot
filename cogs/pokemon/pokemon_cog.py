"""
Cog that implements pokemon functionality.
"""

import random
import sqlite3
import time
import threading
from typing import Callable

import discord
from discord.ext import commands, tasks

NUM_POKEMON = 1025


class WildPokemon:
    """A Pokemon that is available for capture."""

    def __init__(
        self, pokedex_number: str, pokemon_name: str, cleanup_function: Callable
    ):
        # Set attributes
        self.pokedex_number = pokedex_number
        self.pokemon_name = pokemon_name
        self.cleanup_function = cleanup_function

        # Time this Pokemon will be available for capture
        self.available_time = 10  # Minutes

        self.caught_lock = threading.Lock()
        self.caught = False

        # Cleanup this instance after timeout
        t = threading.Thread(target=self.expire, daemon=True)
        t.start()

    async def handle_message(
        self, message: discord.Message, database: str
    ) -> None:
        """Handle incoming message & check if pokemon is caught.

        Args:
            message: Discord message to parse
            database: DB file to connect and interact with
        """
        # Return if not caught
        content = " ".join(message.content.strip().lower().split())
        if content != f"catch {self.pokemon_name}".lower():
            return

        # Connect to database & check if this pokemon is owned already
        connection = sqlite3.connect(database)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT num_owned FROM `Pokemon.UserCollections` WHERE"
            " pokemon_name = ?",
            (self.pokemon_name,),
        )
        res = cursor.fetchone()

        # Add entry if not owned
        if not res:
            cursor.execute(
                "INSERT INTO `Pokemon.UserCollections` "
                "(user_id, user_name, pokemon_name, pokedex_number, num_owned) "
                "VALUES (?,?,?,?,?)",
                (
                    message.author.id,
                    message.author.name,
                    self.pokemon_name,
                    self.pokedex_number,
                    1,
                ),
            )
        else:  # Update entry otherwise
            cursor.execute(
                "UPDATE `Pokemon.UserCollections` "
                "SET num_owned = ? "
                "WHERE user_id = ? AND pokemon_name = ?",
                (res[0] + 1, message.author.id, self.pokemon_name),
            )

        connection.commit()
        connection.close()

        # Send message & cleanup
        await message.channel.send(
            content=(
                f"{message.author.mention} caught"
                f" {self.pokemon_name} (#{self.pokedex_number})!"
            )
        )
        with self.caught_lock:
            self.caught = True  # Tell timeout thread to not cleanup

        self.cleanup_function()

    def expire(self):
        """Timeout after amount of time"""
        # Sleep for timeout duration
        time.sleep(self.available_time * 60)

        # Cleanup if this pokemon was not caught already
        with self.caught_lock:
            if not self.caught:
                self.cleanup_function()


class PokemonCog(commands.Cog):
    """A cog that implements pokemon functionality"""

    def __init__(self, bot: commands.Bot, database: str):
        self.bot = bot
        self.database = database
        self.wild_pokemon = {}  # Mapping from guild to available pokemon

    @commands.Cog.listener()
    async def on_ready(self):
        """Listen for when cog is ready."""
        print(f"{__name__} is online!")
        self.spawn_pokemon.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for incoming messages."""
        # Ignore bot's own messages
        if message.author == self.bot.user:
            return

        # Get the guild the message came from & see if a pokemon is available
        guild_id = message.guild.id
        if guild_id in self.wild_pokemon:
            # Pass message to that guild session
            await self.wild_pokemon[guild_id].handle_message(
                message, self.database
            )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Action to take when a new guild is joined."""
        # Add empty channel registry to database
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO `Pokemon.GuildRegistrations` (guild_id, channel_id)"
            " VALUES (?,?)",
            (guild.id, None),
        )
        connection.commit()
        connection.close()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Action to take when a guild is left."""
        # Remove guild's entry from database
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM `Pokemon.GuildRegistrations` WHERE guild_id = ?",
            (guild.id,),
        )
        connection.commit()
        connection.close()

    @tasks.loop(seconds=60)
    async def spawn_pokemon(self):
        """Periodically spawn a pokemon in all registered guilds."""
        # Get a random pokemon
        dex_number, pokemon_name, icon_url = self.get_random_pokemon()

        # Build a Pokemon embed
        embed = discord.Embed(
            title=f"A wild {pokemon_name} (#{dex_number}) has appeared!"
        )
        embed.add_field(
            name=f'Type "CATCH {pokemon_name}" to catch it!',
            value="",
            inline=False,
        )
        embed.set_image(url=icon_url)

        # Get all registered guilds
        registerations = self.get_registered_guilds()
        for registeration in registerations:
            # Check if the guild is configured
            guild_id, channel_id = registeration
            if channel_id:
                # Create capturable pokemon
                self.wild_pokemon[guild_id] = WildPokemon(
                    dex_number,
                    pokemon_name,
                    self.get_cleanup_function(guild_id),
                )

                # Send spawn message
                await channel.send(embed=embed)
                channel: discord.TextChannel = self.bot.get_channel(channel_id)

        # Spawn the next pokemon at a random interval
        self.spawn_pokemon.change_interval(
            seconds=random.randint(3 * 60 * 60, 5 * 60 * 60)
        )

    @commands.command()
    async def pokemon_register(self, ctx: commands.Context):
        """Configure the spawn channel for a guild."""
        guild = ctx.guild
        channel = ctx.channel

        # Set the new spawn channel for this guild
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE `Pokemon.GuildRegistrations` SET channel_id = ? WHERE"
            " guild_id = ?",
            (channel.id, guild.id),
        )
        connection.commit()
        connection.close()

    def get_random_pokemon(self) -> tuple[str, str, str]:
        """Get a random pokemon's information."""
        # Get a random 4 digit pokedex number
        dex_number = str(random.randint(1, NUM_POKEMON)).zfill(4)

        # Fetch random pokemon from database
        # TODO - Is this really needed?
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT pokemon_name, icon_url FROM `Pokemon.Pokedex` WHERE"
            " pokedex_number = ?",
            (dex_number,),
        )
        pokemon_name, icon_url = cursor.fetchone()
        connection.close()

        return dex_number, pokemon_name, icon_url

    def get_registered_guilds(self) -> list[int]:
        """Get all registered guilds."""
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM `Pokemon.GuildRegistrations`")
        rows = cursor.fetchall()
        connection.close()
        return rows

    def get_cleanup_function(self, guild_id: int) -> Callable:
        """Generate a function to cleanup existing wild pokemon when timed out or captured."""

        def cleanup_function():
            del self.wild_pokemon[guild_id]

        return cleanup_function
