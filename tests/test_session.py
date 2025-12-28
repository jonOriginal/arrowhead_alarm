import asyncio
from asyncio import StreamReader, StreamWriter
from typing import Awaitable, Callable

import pytest

from elitecloud_alarm.session import EciSession, SerialCredentials
from elitecloud_alarm.transport import TcpTransport


def login_server_handler(reader: StreamReader, writer: StreamWriter):
    async def handle_client():
        writer.write(b"\nlogin: ")
        await writer.drain()
        username = (await reader.readline()).decode().strip()

        if username != "admin":
            writer.close()
            await writer.wait_closed()
            return

        writer.write(b"password: ")
        await writer.drain()
        password = (await reader.readline()).decode().strip()

        if password != "admin":
            writer.close()
            await writer.wait_closed()
            return

        writer.write(b"\r\nWelcome\r\n")
        await writer.drain()
        await asyncio.sleep(1)
        writer.close()
        await writer.wait_closed()

    return asyncio.create_task(handle_client())


def panel_login_with_output_oscillation_handler(
    reader: StreamReader, writer: StreamWriter
):
    async def handle_client():
        writer.write(b"\r\nWelcome\r\n")

        while True:
            writer.write(b"OO3\r\n")
            await writer.drain()
            await asyncio.sleep(0.2)
            writer.write(b"OR3\r\n")
            await writer.drain()
            await asyncio.sleep(0.2)

    return asyncio.create_task(handle_client())


def no_login_handler(reader: StreamReader, writer: StreamWriter):
    async def handle_client():
        writer.write(b"\r\nWelcome\r\n")
        await writer.drain()
        await asyncio.sleep(1)
        writer.close()
        await writer.wait_closed()

    return asyncio.create_task(handle_client())


async def open_mock(
    handler: Callable[[StreamReader, StreamWriter], Awaitable[None]],
) -> tuple[str, int]:
    server = await asyncio.start_server(handler, "127.0.0.1")
    return server.sockets[0].getsockname()


@pytest.mark.asyncio
class TestSession:
    async def test_login(self, socket_enabled: None):
        host, port = await open_mock(login_server_handler)
        conn = EciSession(
            transport=TcpTransport(host, port),
            credentials=SerialCredentials(username="admin", password="admin"),
        )
        try:
            await conn.connect()
        except Exception as e:
            pytest.fail(f"Login failed with exception: {e}")
        finally:
            await conn.disconnect()

    async def test_login_no_password_prompt(self, socket_enabled: None):
        host, port = await open_mock(no_login_handler)
        conn = EciSession(
            transport=TcpTransport(host, port),
            credentials=SerialCredentials(username="admin", password="admin"),
        )
        try:
            await conn.connect()
        except Exception as e:
            pytest.fail(f"Login failed with exception: {e}")
        finally:
            await conn.disconnect()

    async def test_login_no_password_prompt_with_creds(self, socket_enabled: None):
        host, port = await open_mock(no_login_handler)
        conn = EciSession(
            transport=TcpTransport(host, port),
            credentials=SerialCredentials(username="admin", password="admin"),
        )
        try:
            await conn.connect()
        except Exception as e:
            pytest.fail(f"Login failed with exception: {e}")
        finally:
            await conn.disconnect()

    async def test_login_incorrect_credentials(self, socket_enabled: None):
        host, port = await open_mock(login_server_handler)
        conn = EciSession(
            transport=TcpTransport(host, port),
            credentials=SerialCredentials(username="wrong", password="wrong"),
        )
        conn.connection_timeout = 2.0
        with pytest.raises(Exception):
            await conn.connect()
        await conn.disconnect()

    async def test_panel_login_with_output_oscillation(self, socket_enabled: None):
        host, port = await open_mock(panel_login_with_output_oscillation_handler)
        conn = EciSession(
            transport=TcpTransport(host, port),
            credentials=SerialCredentials(username="admin", password="admin"),
        )
        message_count = 0

        async def loop():
            nonlocal message_count
            while True:
                await conn.readline("\r\n", timeout=2.0)
                message_count += 1

        try:
            await conn.connect()
            asyncio.create_task(loop())
            await asyncio.sleep(1)
            assert message_count >= 4, "Expected at least 4 messages during oscillation"
        except Exception as e:
            pytest.fail(f"Login failed with exception: {e}")
        finally:
            await conn.disconnect()
