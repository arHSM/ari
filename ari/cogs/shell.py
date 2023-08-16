from discord.ext import commands

from ..helpers.command_paginator import CommandPaginatorView
from ..helpers.shell import ShellExecutor


class Shell(commands.Cog):
    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        error = getattr(error, "original", error)
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command cannot be used in DMs.")
        elif isinstance(error, commands.PrivateMessageOnly):
            await ctx.send("This command can only be used in DMs.")
        else:
            await ctx.send(f"An unknown error occurred: {error}")
            raise error

    @commands.guild_only()
    @commands.command(name="sh", aliases=["shell", "bash", "exec", "eval"])
    async def shell(self, ctx: commands.Context, *, cmd: str):
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
