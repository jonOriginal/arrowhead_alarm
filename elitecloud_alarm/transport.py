"""Asyncio-based connection to Eci alarm system over IP."""

import asyncio
import logging
import typing

from .types import EciTransport

_LOGGER = logging.getLogger(__name__)

T = typing.TypeVar("T")


class TcpTransport(EciTransport):
    """Asyncio-based TCP transport for Eci alarm system."""

    def __init__(
        self,
        host: str,
        port: int,
        encoding: str = "ascii",
        connect_timeout: float = 10.0,
    ) -> None:
        """Initialize the TcpTransport.

        Args:
            host: IP address or hostname of the Eci alarm panel.
            port: TCP port number to connect to.
            encoding: The encoding used for messages, defaults to 'ascii'.
            connect_timeout: Timeout for establishing the connection in seconds.

        """
        self.host = host
        self.port = port
        self.encoding = encoding
        self.connect_timeout = connect_timeout

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish a TCP connection to the Eci alarm panel."""
        _LOGGER.info("Connecting to %s:%s", self.host, self.port)
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self.connect_timeout,
        )

    async def disconnect(self) -> None:
        """Close the TCP connection to the Eci alarm panel."""
        if self._writer:
            _LOGGER.info("Disconnecting TCP transport")
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def write(self, data: str) -> None:
        """Write string data to the TCP connection.

        Args:
            data: String data to send.

        """
        if not self._writer:
            raise ConnectionError("TCP transport not connected")

        async with self._write_lock:
            _LOGGER.debug("TCP SEND → %r", data)
            self._writer.write(data.encode(self.encoding))
            await self._writer.drain()

    async def read(self, n: int = 1024) -> str:
        """Read string data from the TCP connection.

        Args:
            n: Maximum number of bytes to read.

        Returns: Decoded string data read from the connection.

        """
        if not self._reader:
            raise ConnectionError("TCP transport not connected")

        data = await self._reader.read(n)
        if not data:
            raise ConnectionError("TCP connection closed by peer")

        decoded = data.decode(self.encoding)
        _LOGGER.debug("TCP RECV ← %r", decoded)
        return decoded
