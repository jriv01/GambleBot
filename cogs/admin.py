"""Cog implementing administrative commands.

Commands can only be executed by an owner of the bot.
"""

import logging
from typing import Literal, Optional

from discord.ext import commands


class AdminCog(commands.Cog):
    """
    Cog implementing administrative commands.

    Attributes:
        bot: A discord bot client.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(  # pylint: disable=invalid-overridden-method
        self, ctx: commands.Context
    ) -> bool:
        """Checks to perform prior to every admin command."""
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="sync")
    async def sync(
        self,
        ctx: commands.Context,
        spec: Optional[Literal["guild", "global"]] = "global",
    ) -> None:
        """Sync application commands globally or to the current guild."""
        async with ctx.typing():
            if spec == "guild":
                if ctx.guild is None:
                    await ctx.reply("Cannot sync to 'guild' inside Direct Messages.")
                    return

                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                res = f"Synced {len(synced)} command(s) to **{ctx.guild.name}**."
            else:
                synced = await self.bot.tree.sync()
                res = f"Synced {len(synced)} command(s) globally."

        logging.info("[%s] %s", ctx.author, res)
        await ctx.reply(res)

    @commands.command(name="reload")
    async def reload_extension(self, ctx: commands.Context, cog_name: str) -> None:
        """Reload a specific extension."""
        target = cog_name if cog_name.startswith("cogs.") else f"cogs.{cog_name}"

        try:
            await self.bot.reload_extension(target)
            await ctx.send(f"Successfully reloaded `{target}`")
        except Exception as e:  # pylint: disable=broad-exception-caught
            await ctx.send(f"Failed to reload `{target}`:\n```py\n{e}\n```")

    @commands.command(name="reloadall", aliases=["reload_all"])
    async def reload_all(self, ctx: commands.Context) -> None:
        """Reload all currently loaded extensions."""
        for ext in list(self.bot.extensions.keys()):
            await self.reload_extension(ctx, ext)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
