import asyncio
from _asyncio import Task
from asyncio import StreamReader, StreamWriter
from typing import Awaitable, Callable

import pytest

from arrowhead_alarm import VersionInfo, create_tcp_client


def no_login_handler(reader: StreamReader, writer: StreamWriter) -> Task[None]:
    async def handle_client() -> None:
        writer.write(b"\r\nWelcome\r\n")
        await writer.drain()

        while True:
            line = await reader.readline()
            if line.strip() == b"Version":
                writer.write(b'OK Version "ECi F/W Ver. 10.3.52 (WR5SPLS1)"\r\n')
                await writer.drain()
            if line.strip().startswith(b"MODE"):
                mode_num = line.strip().split(b" ")[1]
                writer.write(b"OK\r\n" + b"Mode " + mode_num + b"\r\n")
                await writer.drain()

    return asyncio.create_task(handle_client())


async def open_mock(handler: Callable[[StreamReader, StreamWriter], Awaitable[None]]):
    server = await asyncio.start_server(handler, "127.0.0.1")
    return server.sockets[0].getsockname()


@pytest.mark.asyncio
async def test_client_initialization() -> None:
    host, port = await open_mock(no_login_handler)
    client = create_tcp_client(host, port)
    await client.connect()

    assert client.is_connected
    assert client.panel_version is not None
    assert client.panel_version.firmware_version == VersionInfo(10, 3, 52)
