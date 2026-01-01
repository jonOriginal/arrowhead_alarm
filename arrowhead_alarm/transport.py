"""Asyncio-based connection to Arrowhead alarm system over IP."""

import asyncio
import logging
from typing import TypeVar

try:
    from typing import override  # ty:ignore[unresolved-import]
except ImportError:
    from typing_extensions import override  # ty:ignore[unresolved-import]

from arrowhead_alarm.const import DEF_ENCODING, DEF_READ_LENGTH

from .types import EciTransport

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class TcpTransport(EciTransport):
    """Asyncio-based TCP transport for Arrowhead alarm system."""

    def __init__(
        self,
        host: str,
        port: int,
        encoding: str = DEF_ENCODING,
        connect_timeout: float = 10.0,
    ) -> None:
        """Initialize the Tcp Transport.

        Args:
            host: IP address or hostname of the Arrowhead alarm panel.
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

    @override
    async def connect(self) -> None:
        _LOGGER.info("Connecting to %s:%s", self.host, self.port)
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self.connect_timeout,
        )

    @override
    async def disconnect(self) -> None:
        if self._writer:
            _LOGGER.info("Disconnecting TCP transport")
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    @override
    async def write(self, data: str) -> None:
        if not self._writer:
            raise ConnectionError("TCP transport not connected")

        async with self._write_lock:
            _LOGGER.debug("TCP SEND → %r", data)
            self._writer.write(data.encode(self.encoding))
            await self._writer.drain()

    @override
    async def read(self, n: int = DEF_READ_LENGTH) -> str:
        if not self._reader:
            raise ConnectionError("TCP transport not connected")

        data = await self._reader.read(n)
        if not data:
            raise ConnectionError("TCP connection closed by peer")

        decoded = data.decode(self.encoding)
        _LOGGER.debug("TCP RECV ← %r", decoded)
        return decoded
