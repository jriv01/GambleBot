"""
Cog that implements pokemon functionality.
"""

import asyncio
import random
import sqlite3
import threading

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.paginator import Paginator

NUM_POKEMON = 1025


class WildPokemon:
    """A Pokemon that is available for capture."""

    def __init__(self, pokedex_number: str, pokemon_name: str):
        # Set attributes
        self.pokedex_number = pokedex_number
        self.pokemon_name = pokemon_name

        # Variables for determining if Pokemon can be caught
        self.caught_lock = threading.Lock()
        self.is_caught = False

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

        # Check if this pokemon has already been caught
        with self.caught_lock:
            if self.is_caught:
                return
            self.is_caught = True

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
        await message.reply(
            content=(
                f"{message.author.mention} caught"
                f" {self.pokemon_name} (#{self.pokedex_number})!"
            )
        )


class Pokedex(Paginator):
    """View for a player Pokedex"""

    def __init__(self, user: discord.User, message, pokemon_list):
        super().__init__(
            message=message,
            page_title="Pokédex",
            data=pokemon_list,
            data_formatter=self.format_pokemon,
            thumbnail_url=user.avatar.url,
            items_per_page=10,
        )

    def format_pokemon(self, pokemon: tuple[str, str]):
        """Format pokemon data into a string"""
        dex_number, name = pokemon
        return f"#{dex_number}: {name}"


class PokemonCog(commands.Cog):
    """A cog that implements pokemon functionality"""

    def __init__(self, bot: commands.Bot, database: str):
        self.bot = bot
        self.database = database

        # Mapping from guild to available pokemon
        self.wild_pokemon: dict[int, WildPokemon] = {}

        # Amount of time wild pokemon are available for
        self.capture_timeout = 10  # Minutes

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
            "INSERT INTO `Pokemon.GuildConfigurations` (guild_id, channel_id)"
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
            "DELETE FROM `Pokemon.GuildConfigurations` WHERE guild_id = ?",
            (guild.id,),
        )
        connection.commit()
        connection.close()

        # Remove wild pokemon from that guild, if it exists
        self.wild_pokemon.pop(guild.id, None)

    @app_commands.command(
        name="pokedex", description="See what Pokémon you've captured."
    )
    async def pokedex(self, interaction: discord.Interaction):
        """Get all pokemon that a user has captured."""
        # Fetch a user's collection of captured pokemon
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT pokedex_number, pokemon_name FROM `Pokemon.UserCollections`"
            " WHERE user_id = ? ORDER BY pokedex_number",
            (interaction.user.id,),
        )
        rows = cursor.fetchall()
        connection.commit()
        connection.close()

        # Check if the user has any pokemon
        if not rows:
            await interaction.response.send_message(
                "You haven't caught any Pokémon!", ephemeral=True
            )
            return

        # Build pokedex & display
        await interaction.response.send_message(
            embed=discord.Embed(title="Pokédex")
        )
        view = Pokedex(
            interaction.user, await interaction.original_response(), rows
        )
        await view.update_message()

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

        # Get all configured guilds
        configured_guilds = self.get_configured_guilds()
        for guild_id, channel_id in configured_guilds.items():
            # Create capturable pokemon
            self.wild_pokemon[guild_id] = WildPokemon(
                dex_number,
                pokemon_name,
            )

            # Send spawn message
            channel: discord.TextChannel = self.bot.get_channel(channel_id)
            await channel.send(embed=embed)

        # Allow time for pokemon to be caught
        await asyncio.sleep(60 * self.capture_timeout)

        for guild_id, pokemon in self.wild_pokemon.items():
            # If the pokemon was caught, do nothing
            if pokemon.is_caught:
                continue

            # Send message saying pokemon got away
            channel: discord.TextChannel = self.bot.get_channel(
                configured_guilds[guild_id]
            )
            await channel.send(content=f"{pokemon.pokemon_name} got away...")

        # Reset wild pokemon
        self.wild_pokemon: dict[int, WildPokemon] = {}

        # Spawn the next pokemon at a random interval
        self.spawn_pokemon.change_interval(
            seconds=random.randint(3 * 60 * 60, 5 * 60 * 60)
        )

    @commands.command()
    @commands.is_owner()
    async def force_spawn(self, ctx: commands.Context):
        """Force a pokemon to spawn.

        WARNING: Aborts any existing pokemon.
        """

        # Check if this guild already has a wild pokemon available.
        if ctx.guild.id in self.wild_pokemon:
            ctx.message.reply(
                content=(
                    "Forced spawn aborted a wild pokemon:"
                    f" {self.wild_pokemon[ctx.guild.id].pokemon_name}"
                )
            )

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
        await ctx.channel.send(embed=embed)

        # Create pokemon
        pokemon = WildPokemon(dex_number, pokemon_name)
        self.wild_pokemon[ctx.guild.id] = pokemon

        # Allow time for pokemon to be caught
        await asyncio.sleep(60 * self.capture_timeout)

        # Check if the pokemon was caught
        if not pokemon.is_caught:
            await ctx.channel.send(
                content=f"{pokemon.pokemon_name} got away..."
            )

        # Remove pokemon from memory
        self.wild_pokemon.pop(ctx.guild.id, None)

    @commands.command()
    async def pokemon_enable(self, ctx: commands.Context):
        """Configure the spawn channel for a guild."""
        guild = ctx.guild
        channel = ctx.channel

        # Set the new spawn channel for this guild
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE `Pokemon.GuildConfigurations` SET channel_id = ? WHERE"
            " guild_id = ?",
            (channel.id, guild.id),
        )
        connection.commit()
        connection.close()

        await ctx.message.reply(
            "Configured random pokemon spawns for this server to this channel."
        )

    @commands.command()
    async def pokemon_disable(self, ctx: commands.Context):
        """Unconfigure the spawn channel for a guild."""
        guild = ctx.guild

        # Unset spawn channel for this guild
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE `Pokemon.GuildConfigurations` SET channel_id = ? WHERE"
            " guild_id = ?",
            (None, guild.id),
        )
        connection.commit()
        connection.close()

        # Remove wild pokemon from that guild, if it exists
        self.wild_pokemon.pop(guild.id, None)

        await ctx.message.reply(
            "Unconfigured random pokemon spawns for this server."
        )

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

    def get_configured_guilds(self) -> dict[int, int]:
        """Get all configured guilds."""
        connection = sqlite3.connect(self.database)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM `Pokemon.GuildConfigurations` WHERE channel_id IS"
            " NOT NULL"
        )
        rows = cursor.fetchall()
        connection.close()
        return {row[0]: row[1] for row in rows}
