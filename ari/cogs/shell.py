from discord.ext.commands import Cog, Context, command

from ..helpers.command_paginator import CommandPaginatorView
from ..helpers.shell import ShellExecutor


class Shell(Cog):
    def __init__(self) -> None:
        return

    @command(name="sh", aliases=["shell", "bash", "exec", "eval"])
    async def shell(self, ctx: Context, *, cmd: str):
        view = CommandPaginatorView(ctx)

        await view.reply()

        with ShellExecutor(cmd) as executor:
            view.executor = executor
            await view.add_line(f"$ {cmd}\n")

            async for line in executor:
                await view.add_line(line)

        view.executor = None

        await view.add_line(f"\n$ [process exited with code {executor.returncode}]")


async def setup(bot):
    await bot.add_cog(Shell())
