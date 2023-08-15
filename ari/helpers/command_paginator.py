from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Coroutine, Final, TypeVar

from discord import ButtonStyle, HTTPException
from discord.ext.commands import Context, Paginator
from discord.ui import View, button

from .shell import ShellExecutor

if TYPE_CHECKING:
    from discord import Interaction, Message
    from discord.ui import Button

T = TypeVar("T")

class CommandPaginatorView(View):
    DEBOUNCE_TIMEOUT: Final[int] = 1

    def __init__(self, ctx: Context, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)

        self.paginator = Paginator(prefix="```ansi")
        self._has_page_set = False
        self._current_page = -1
        self.ctx = ctx

        self.message = None
        self.executor: ShellExecutor | None = None
        self._edit: asyncio.Task[Message] | None = None
        self._initial_edit: bool = False

    async def _debounce(self, coro: Coroutine[None, None, T]) -> T:
        if self._initial_edit:
            await asyncio.sleep(self.DEBOUNCE_TIMEOUT)
        else:
            self._initial_edit = True
        return await coro

    @property
    def total_pages(self):
        return None if len(self.paginator.pages) == 0 else len(self.paginator.pages) - 1

    @property
    def display_page(self):
        if self._has_page_set:
            return self._current_page
        return self.total_pages

    @display_page.setter
    def display_page(self, value: int | None):
        if len(self.paginator.pages) != 0:
            if value is not None:
                self._current_page = value
            self._has_page_set = value is not None
        else:
            self._current_page = 0
            self._has_page_set = False

    @property
    def content(self):
        return (
            self.paginator.pages[self.display_page]
            if self.display_page is not None
            else "executing..."
        )

    @property
    def send_kwargs(self):
        return {
            "content": self.content,
            "view": self,
        }

    async def reply(self):
        self.update_view()

        self.message = await self.ctx.reply(**self.send_kwargs)
        return self.message

    async def add_line(self, line: str):
        # pylint: disable=W0212
        true_max_size = (
            self.paginator.max_size
            - self.paginator._prefix_len
            - self.paginator._suffix_len
            - 2 * self.paginator._linesep_len
        )

        start = 0
        needle = 0
        last_newline = -1
        last_space = -1

        while needle < len(line):
            if needle - start >= true_max_size:
                if last_newline != -1:
                    self.paginator.add_line(line[start:last_newline])
                    needle = last_newline + 1
                    start = last_newline + 1
                elif last_space != -1:
                    self.paginator.add_line(line[start:last_space])
                    needle = last_space + 1
                    start = last_space
                else:
                    self.paginator.add_line(line[start:needle])
                    start = needle

                last_newline = -1
                last_space = -1

            if line[needle] == "\n":
                last_newline = needle
            elif line[needle] == " ":
                last_space = needle

            needle += 1

        last_line = line[start:needle]
        if last_line:
            self.paginator.add_line(last_line)

        if not self._has_page_set and self.message:
            self.update_view()

            try:
                if self._edit is not None and not self._edit.done():
                    self._edit.cancel()
                self._edit = self.ctx.bot.loop.create_task(
                    self._debounce(self.message.edit(**self.send_kwargs))
                )
                await self._edit
            except asyncio.CancelledError:
                pass
            except HTTPException as exception:
                if exception.status == 404:
                    self.message = None
                raise

    def update_view(self, timedout: bool = False):
        self.button_start.disabled = self.button_back.disabled = (
            timedout or self.display_page == 0
        )
        self.button_end.disabled = self.button_forward.disabled = timedout or (
            self.display_page == self.total_pages
        )

        self.button_kill.disabled = self.button_terminate.disabled = timedout or (
            True if self.executor is None else self.executor.closed
        )

    async def try_edit(self, interaction: Interaction):
        try:
            await interaction.response.edit_message(**self.send_kwargs)
        except HTTPException as exception:
            if exception.status == 404:
                self.message = None
            raise

    async def interaction_check(self, interaction: Interaction, /):
        if interaction.user.id == self.ctx.author.id:
            return True

        await interaction.response.send_message(
            "You cannot contol this pagination menu!", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        if self.message:
            self.update_view(True)

            try:
                await self.message.edit(**self.send_kwargs)
            except HTTPException:
                pass

    @button(label="≪", style=ButtonStyle.gray)
    async def button_start(self, interaction: Interaction, _: Button):
        self.display_page = 0

        self.update_view()
        await self.try_edit(interaction)

    @button(label="Back", style=ButtonStyle.blurple)
    async def button_back(self, interaction: Interaction, _: Button):
        if self.display_page != 0:
            self.display_page -= 1

        self.update_view()
        await self.try_edit(interaction)

    @button(label="Forward", style=ButtonStyle.blurple)
    async def button_forward(self, interaction: Interaction, _: Button):
        if self.display_page != self.total_pages:
            self.display_page += 1

        self.update_view()
        await self.try_edit(interaction)

    @button(label="≫", style=ButtonStyle.gray)
    async def button_end(self, interaction: Interaction, _: Button):
        self.display_page = None

        self.update_view()
        await self.try_edit(interaction)

    @button(label="Kill", style=ButtonStyle.red, row=2)
    async def button_kill(self, interaction: Interaction, _: Button):
        if self.executor:
            self.executor.kill()

        self.update_view()
        await self.try_edit(interaction)

    @button(label="Terminate", style=ButtonStyle.red, row=2)
    async def button_terminate(self, interaction: Interaction, _: Button):
        if self.executor:
            self.executor.terminate()

        self.update_view()
        await self.try_edit(interaction)
