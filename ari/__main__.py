from os import getenv

from discord import Intents
from discord.ext.commands import Bot
from dotenv import load_dotenv

load_dotenv()

intents = Intents.none()
intents.guild_messages = True
intents.dm_messages = True
intents.message_content = True


class ShellBot(Bot):
    async def setup_hook(self) -> None:
        await bot.load_extension(".cogs.shell", package="src")


bot = ShellBot(command_prefix=">", intents=intents)

bot.run(getenv("TOKEN"))
