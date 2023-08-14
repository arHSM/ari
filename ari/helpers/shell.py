# A stripped down implementation of
# https://github.com/Gorialis/jishaku/blob/master/jishaku/shell.py

from asyncio import AbstractEventLoop, Queue
from asyncio import TimeoutError as ATimeoutError
from asyncio import get_event_loop, wait_for
from re import compile as regex
from subprocess import PIPE, Popen
from time import perf_counter
from typing import IO, Any, Callable, Match

CONTAINER = "evalbot_sandbox"
BASE_COMMAND = [
    "docker",
    "exec",
    "-it",
    CONTAINER,
    "bash",
    "-c",
]

ANSI_ESCAPE_CODE = regex(r"\x1b\[\??(\d*)(?:([ABCDEFGJKSThilmnsu])|;(\d+)([fH]))")


def reader(
    stream: IO[bytes], loop: AbstractEventLoop, callback: Callable[[bytes], Any]
):
    for line in iter(stream.readline, b""):
        loop.call_soon_threadsafe(loop.create_task, callback(line))


class ShellExecutor:
    def __init__(self, command: str, timeout=120) -> None:
        command = [*BASE_COMMAND, command]

        # pylint: disable=R1732
        self.process = Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        self.loop = get_event_loop()
        self.returncode = self.process.returncode
        self.timeout = timeout

        self.readers = (
            self.make_reader(self.process.stdout, self.stdout_handler),
            self.make_reader(self.process.stderr, self.stderr_handler),
        )

        self.queue = Queue(maxsize=250)

    @property
    def closed(self):
        (out, err) = self.readers

        return (not out or out.done()) and (not err or err.done())

    async def executor_wrapper(
        self, stream: IO[bytes], callback: Callable[[bytes], Any]
    ):
        return await self.loop.run_in_executor(
            None, reader, stream, self.loop, callback
        )

    def make_reader(self, stream: IO[bytes] | None, callback: Callable[[bytes], Any]):
        if not stream:
            return None

        return self.loop.create_task(self.executor_wrapper(stream, callback))

    def clean_bytes(self, line: bytes):
        text = line.decode("utf-8").replace("\r", "").replace("``", "`\u200b`")

        def sub(groups: Match[str]):
            return groups.group(0) if groups.group(2) == "m" else ""

        return ANSI_ESCAPE_CODE.sub(sub, text).strip("\n")

    async def stdout_handler(self, line: bytes):
        await self.queue.put(self.clean_bytes(line))

    async def stderr_handler(self, line: bytes):
        await self.queue.put(self.clean_bytes(b"[stderr] " + line))

    def kill(self):
        return self.process.kill()

    def terminate(self):
        return self.process.terminate()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.kill()
        self.terminate()
        self.returncode = self.process.wait(self.timeout)

    def __aiter__(self):
        return self

    async def __anext__(self):
        last_output = perf_counter()

        while not self.closed or not self.queue.empty():
            try:
                item = await wait_for(self.queue.get(), timeout=1)
            except ATimeoutError as exception:
                if perf_counter() - last_output >= self.timeout:
                    raise exception
            else:
                last_output = perf_counter()
                return item

        raise StopAsyncIteration()
