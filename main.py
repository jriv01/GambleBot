import os
from typing import Union

import discord
from discord.ext import commands
from discord import app_commands
import dotenv


dotenv.load_dotenv()
bot_token = os.getenv("DISCORD_TOKEN")

GUILD_ID = discord.Object(id=os.getenv("GUILD_ID"))


class Client(commands.Bot):
    async def on_ready(self):
        print(f"Logged on as {self.user}!")

        # Try syncing slash commands to server
        try:
            synced = await self.tree.sync(guild=GUILD_ID)
            print(f"Synced {len(synced)} commands to guild {GUILD_ID.id}")
        except Exception as e:
            print(e)

    async def on_message(self, message: discord.Message):
        # Ignore bots own messages
        if message.author == self.user:
            return

        if message.content.startswith("hello"):
            await message.channel.send(f"Hi there {message.author}!")

    async def on_reaction_add(
        self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]
    ):
        await reaction.message.channel.send("You reacted")


intents = discord.Intents.default()
intents.message_content = True

# Command prefix must still be included, even though they are "deprecated"
client = Client(command_prefix="!", intents=intents)

# Add slash command
@client.tree.command(name="hello", description="Say hello!", guild=GUILD_ID)
async def say_hello(interaction: discord.Interaction):
    await interaction.response.send_message("Hi there!")

@client.tree.command(name="printer", description="I will print whatever you give me!", guild=GUILD_ID)
async def printer(interaction: discord.Interaction, printer: str):
    await interaction.response.send_message(printer)


client.run(bot_token)
