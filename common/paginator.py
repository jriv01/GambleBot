"""
Implementation for a view that can display a set of information by dividing
it into cyclable pages. Pages are in the form of embeds in a discord message.
"""

from typing import Any, Callable
import discord


class Paginator(discord.ui.View):
    """View that implements multiple pages of data that can be cycled through.

    Attributes:
        message: Discord message to edit & manage.
        page_title: Title of the view.
        data: Data to display per page.
        data_formatter: Function to format rows of data, returns a string.
        thumbnail_url: Thumbnail to display in embed.
        items_per_page: Number of data items per page.
        current_page: Current page being displayed.
        max_pages: Max number of pages.
        prev_button: Button to go to previous page.
        next_button: Button to go to next page.
    """

    def __init__(
        self,
        message: discord.Message,
        page_title: str,
        data: list[Any],
        data_formatter: Callable[..., str],
        thumbnail_url: str = None,
        items_per_page: int = 10,
        timeout: float = 60.0,
    ):
        """
        Args:
            message: Discord message to edit & apply view to
            page_title: Embed title shared between each page
            data: List of data to display
            data_formatter: Function to format elements of data
            thumbnail_url: Embed image url
            items_per_page: Number of data items to display per page
            timeout: Seconds until view stops accepting interaction
        """
        super().__init__(timeout=timeout)
        self.message = message
        self.page_title = page_title
        self.data = data
        self.data_formatter = data_formatter
        self.thumbnail_url = thumbnail_url
        self.items_per_page = items_per_page
        self.current_page = 0
        self.max_pages = (len(self.data) - 1) // self.items_per_page

        # Create buttons
        self.prev_button = discord.ui.Button(
            label="<", style=discord.ButtonStyle.primary
        )
        self.next_button = discord.ui.Button(
            label=">", style=discord.ButtonStyle.primary
        )
        self.prev_button.callback = self.prev_callback
        self.next_button.callback = self.next_callback

        # Only use buttons if there is more than one page needed
        if self.max_pages > 0:
            self.add_item(self.prev_button)
            self.add_item(self.next_button)

    async def next_callback(self, interaction: discord.Interaction) -> None:
        """Callback for "next" button interaction."""
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message()

    async def prev_callback(self, interaction: discord.Interaction) -> None:
        """Callback for "previous" buttton interaction."""
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message()

    async def update_message(self) -> None:
        """Update buttons & message contents."""
        await self.update_buttons()
        await self.message.edit(embed=self.create_embed(), view=self)

    async def update_buttons(self) -> None:
        """Update style & functionality of buttons."""
        # Check if on first page
        if self.current_page == 0:
            self.prev_button.disabled = True
            self.prev_button.style = discord.ButtonStyle.gray
        else:
            self.prev_button.disabled = False
            self.prev_button.style = discord.ButtonStyle.primary

        # Check if on last page
        if self.current_page == self.max_pages:
            self.next_button.disabled = True
            self.next_button.style = discord.ButtonStyle.gray
        else:
            self.next_button.disabled = False
            self.next_button.style = discord.ButtonStyle.primary

    async def on_timeout(self) -> None:
        """Clean up view after timeout."""
        # Disable children (buttons)
        for child in self.children:
            child.disabled = True
        # Clear children (buttons)
        self.clear_items().stop()

        # Clean up references
        self.prev_button.callback = None
        self.next_button.callback = None
        self.prev_button = None
        self.next_button = None

        # Make funal update to message
        await self.message.edit(view=None)

    def create_embed(self) -> discord.Embed:
        """Create an embed based on the current page of data.

        Returns:
            The formatted embed with the correct page data.
        """
        # Get section of data to display
        start_index = self.current_page * self.items_per_page
        end_index = (self.current_page + 1) * self.items_per_page
        portion = self.data[start_index:end_index]

        # Create embed
        title = self.page_title
        title += (
            f" || Page {self.current_page + 1}\n"
            if self.max_pages > 1
            else "\n"
        )
        title += "=" * 15
        embed = discord.Embed(
            title=title,
            color=discord.Color.dark_red(),
        )

        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)

        # Add each data element to embed
        for element in portion:
            embed.add_field(
                name=self.data_formatter(element), value="", inline=False
            )
        return embed
