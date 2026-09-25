"""Cog that implements Pokémon functionality."""

import asyncio
import os
import random
import threading

import discord
from discord import app_commands
from discord.ext import commands, tasks

from common.base_cog import BaseCog
from common.database_utilities import AsyncSqliteDatabase
from common.paginator import Paginator
from core.bot import Client
from lib.pokemon.pokemon_api_wrapper import Pokemon, PokemonApiWrapper

NUM_POKEMON = 1025


class WildPokemon:
    """A Pokemon that is available for capture.

    Attributes:
        pokemon: Pokemon instance
        is_caught: Whether this pokemon has been caught or not
        caught_lock: Lock for managing is_caught
    """

    def __init__(self, pokemon: Pokemon):
        # Set attributes
        self.pokemon = pokemon

        # Variables for determining if Pokemon can be caught
        self.is_caught = False
        self.caught_lock = threading.Lock()

    @property
    def name(self):
        """Get name of wild pokemon."""
        return self.pokemon.name

    async def handle_message(
        self, message: discord.Message, database: AsyncSqliteDatabase
    ) -> None:
        """Handle incoming message & check if pokemon is caught.

        Args:
            message: Discord message to parse
            database: Database to interact with
        """
        # Return if not caught
        content = " ".join(message.content.strip().lower().split())
        if content != f"catch {self.pokemon.name}".lower():
            return

        # Check if this pokemon has already been caught
        with self.caught_lock:
            if self.is_caught:
                return
            self.is_caught = True

        # Connect to database & check if this pokemon is owned already
        res = await database.execute_query(
            "SELECT num_owned FROM `Pokemon.UserCollections` WHERE"
            " pokemon_name = ? AND language = ?",
            self.pokemon.name,
            self.pokemon.language,
        )

        # Add entry if not owned
        if not res:
            await database.execute_query(
                "INSERT INTO `Pokemon.UserCollections` (user_id, user_name,"
                " pokemon_name, language, pokedex_number, num_owned) VALUES"
                " (?,?,?,?,?,?)",
                message.author.id,
                message.author.name,
                self.pokemon.name,
                self.pokemon.language,
                self.pokemon.pokedex_number,
                1,
            )
        else:  # Update entry otherwise
            await database.execute_query(
                "UPDATE `Pokemon.UserCollections` SET num_owned = ? WHERE"
                " user_id = ? AND pokemon_name = ? AND language = ?",
                res[0][0] + 1,  # Get first row
                message.author.id,
                self.pokemon.name,
                self.pokemon.language,
            )

        # Send message & cleanup
        await message.reply(
            content=(
                f"{message.author.mention} caught"
                f" {self.pokemon.name} (#{self.pokemon.pokedex_number})!"
            )
        )


class Pokedex(Paginator):
    """View for a player Pokedex. Inherits from Paginator."""

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
        """Format pokemon data into a string.

        Args:
            pokemon: Tuple of 2 strings for pokedex id & name
        """
        dex_number, name = pokemon
        return f"#{dex_number.zfill(4)}: {name}"


class PokemonCog(BaseCog):
    """A cog that implements pokemon functionality.

    Attributes:
        database: A SqliteDatabase instance to query on.
        poke_api: Poke API V2 wrapper instance.
        wild_pokemon: Mapping of guild ids to wild pokemon.
        capture_timeout: Amount of time a wild pokemon can be captured for.
    """

    # Group for all pokemon related slash commands.
    group = app_commands.Group(name="pokemon", description="Pokemon related commands")

    def __init__(self, bot: Client):
        super().__init__(bot)

        # Pokemon API wrapper
        self.poke_api = PokemonApiWrapper()

        # Mapping from guild to available pokemon
        self.wild_pokemon: dict[int, WildPokemon] = {}

        # Amount of time wild pokemon are available for
        self.capture_timeout = 10  # Minutes

    async def cog_load(self):
        self.spawn_pokemon.start()

    async def cog_unload(self):
        self.spawn_pokemon.stop()

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
            await self.wild_pokemon[guild_id].handle_message(message, self.bot.db)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Action to take when a new guild is joined."""
        # Add empty channel registry to database
        await self.bot.db.execute_query(
            "INSERT INTO `Pokemon.GuildConfigurations` (guild_id, channel_id)"
            " VALUES (?,?)",
            guild.id,
            None,
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Action to take when a guild is left."""
        # Remove guild's entry from database
        await self.bot.db.execute_query(
            "DELETE FROM `Pokemon.GuildConfigurations` WHERE guild_id = ?",
            guild.id,
        )

        # Remove wild pokemon from that guild, if it exists
        self.wild_pokemon.pop(guild.id, None)

    @group.command(name="pokedex", description="See what Pokémon you've captured.")
    async def pokedex(
        self, interaction: discord.Interaction, language: str = "en"
    ) -> None:
        """Get all pokemon that a user has captured.

        Args:
            interaction: Discord interaction to handle.
            language: Which language to display Pokemon for.
        """
        # Ensure language is of expected format
        language = language.lower()[:2]

        # Fetch a user's collection of captured pokemon
        rows = await self.bot.db.execute_query(
            "SELECT pokedex_number, pokemon_name FROM `Pokemon.UserCollections`"
            " WHERE user_id = ? AND language = ? ORDER BY pokedex_number",
            interaction.user.id,
            language,
        )

        # Check if the user has any pokemon
        if not rows:
            await interaction.response.send_message(
                "You haven't caught any Pokémon!", ephemeral=True
            )
            return

        # Build pokedex & display
        await interaction.response.send_message(embed=discord.Embed(title="Pokédex"))
        view = Pokedex(interaction.user, await interaction.original_response(), rows)
        await view.update_message()

    @group.command(
        name="enable",
        description=("Set this channel for random Pokemon spawns in this server."),
    )
    async def enable(self, interaction: discord.Interaction) -> None:
        """Configure the spawn channel for a guild."""
        guild = interaction.guild
        channel = interaction.channel

        # Set the new spawn channel for this guild
        await self.bot.db.execute_query(
            "UPDATE `Pokemon.GuildConfigurations` SET channel_id = ? WHERE"
            " guild_id = ?",
            channel.id,
            guild.id,
        )

        await interaction.response.send_message(
            "Configured random pokemon spawns for this server to this channel."
        )

    @group.command(
        name="disable",
        description="Disable random Pokemon spawns for this server.",
    )
    async def disable(self, interaction: discord.Interaction) -> None:
        """Unconfigure the spawn channel for a guild."""
        guild = interaction.guild

        # Unset spawn channel for this guild
        await self.bot.db.execute_query(
            "UPDATE `Pokemon.GuildConfigurations` SET channel_id = ? WHERE"
            " guild_id = ?",
            None,
            guild.id,
        )

        # Remove wild pokemon from that guild, if it exists
        self.wild_pokemon.pop(guild.id, None)

        await interaction.response.send_message(
            "Unconfigured random pokemon spawns for this server."
        )

    @tasks.loop(seconds=60)
    async def spawn_pokemon(self):
        """Periodically spawn a pokemon in all registered guilds."""
        # Get a random pokemon
        pokemon = await self.poke_api.get_random_pokemon()
        pokemon_name = pokemon.name
        pokedex_number = pokemon.pokedex_number
        artwork_url = pokemon.artwork_url

        # Build a Pokemon embed
        embed = discord.Embed(
            title=f"A wild {pokemon_name} (#{pokedex_number}) has appeared!"
        )
        embed.add_field(
            name=f'Type "CATCH {pokemon.name}" to catch it!',
            value="",
            inline=False,
        )
        embed.set_image(url=artwork_url)

        # Get all configured guilds
        configured_guilds = await self.get_configured_guilds()
        for guild_id, channel_id in configured_guilds.items():
            # Create capturable pokemon
            self.wild_pokemon[guild_id] = WildPokemon(pokemon)

            # Send spawn message
            channel: discord.TextChannel = self.bot.get_channel(channel_id)
            await channel.send(embed=embed)

        # Allow time for pokemon to be caught
        await asyncio.sleep(60 * self.capture_timeout)

        # Clean up wild pokemon for each guild
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
    async def force_spawn(self, ctx: commands.Context) -> None:
        """Force a pokemon to spawn.

        WARNING: Aborts any existing pokemon.

        Args:
            ctx: Context command was called in.
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
        pokemon = await self.poke_api.get_random_pokemon()
        pokemon_name = pokemon.name
        pokedex_number = pokemon.pokedex_number
        artwork_url = pokemon.artwork_url

        # Build a Pokemon embed
        embed = discord.Embed(
            title=f"A wild {pokemon_name} (#{pokedex_number}) has appeared!"
        )
        embed.add_field(
            name=f'Type "CATCH {pokemon_name}" to catch it!',
            value="",
            inline=False,
        )
        embed.set_image(url=artwork_url)
        await ctx.channel.send(embed=embed)

        # Create pokemon
        wild_pokemon = WildPokemon(pokemon)
        self.wild_pokemon[ctx.guild.id] = wild_pokemon

        # Allow time for pokemon to be caught
        await asyncio.sleep(60 * self.capture_timeout)

        # Check if the pokemon was caught
        if not wild_pokemon.is_caught:
            await ctx.channel.send(content=f"{wild_pokemon.name} got away...")

        # Remove pokemon from memory
        self.wild_pokemon.pop(ctx.guild.id, None)

    async def get_configured_guilds(self) -> dict[int, int]:
        """Get all configured guilds.

        Returns:
            A map of guild ids to their registered channel ids.
        """
        rows = await self.bot.db.execute_query(
            "SELECT * FROM `Pokemon.GuildConfigurations` WHERE channel_id IS"
            " NOT NULL"
        )
        return {row[0]: row[1] for row in rows}


async def setup(bot: Client):
    await bot.add_cog(PokemonCog(bot))
