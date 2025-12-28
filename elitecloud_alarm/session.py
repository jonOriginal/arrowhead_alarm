"""Manages an authenticated session with an Eci alarm panel over TCP."""

import asyncio
import logging
import uuid
from asyncio import Event, Lock
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, TypeVar

from .commands import string_options_request
from .const import (
    AUTH_LOGIN_MSG,
    AUTH_PASSWORD_PROMPT,
    AUTH_WELCOME_MSG,
)
from .exceptions import (
    InvalidCredentialsError,
    InvalidResponseError,
    MissingCredentialsError,
)
from .parsing import line_listener, string_options_listener
from .types import EciTransport, Request, SerialCredentials, ToggleEvent
from .util import add_delimiter_if_missing, cancel_task

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class EciSession:
    """Manages an authenticated session with an Eci alarm panel."""

    def __init__(
        self, transport: EciTransport, credentials: SerialCredentials | None = None
    ) -> None:
        """Initialize the Eci session.

        Args:
            transport: The Eci transport to use for communication.
            credentials: Optional serial credentials for authentication.

        """
        self.credentials: SerialCredentials | None = credentials
        self.reconnect_delay = 1.0
        self.connection_timeout = 10.0
        self.authentication_timeout = 5.0
        self.max_retries = 10

        self._connect_lock: Lock = Lock()
        self._disconnect_lock: Lock = Lock()
        self._connected_event: ToggleEvent = ToggleEvent()
        self._cancel_event: Event = Event()

        self._reconnect_task: asyncio.Task[None] | None = None
        self._read_task: asyncio.Task[None] | None = None

        self._callback_lock: Lock = Lock()
        self._callbacks: dict[str, Callable[[str | Exception], None]] = {}

        self._transport: EciTransport = transport

    async def connect(self) -> None:
        """Establish connection and authenticate. Returns when connected.

        Returns: None

        """
        if self.connected():
            return
        _LOGGER.info("Starting connection")
        self._cancel_event.clear()
        self._reconnect_task = asyncio.create_task(self._reconnect_worker())
        await self._ensure_connected()

    def connected(self) -> bool:
        """Check if the session is currently connected and authenticated."""
        return self._connected_event.is_set()

    async def disconnect(self) -> None:
        """Disconnect from the Eci panel and stop reconnection attempts."""
        _LOGGER.info("Disconnecting from transport")
        self._cancel_event.set()
        await self._cleanup_connection()
        await cancel_task(self._reconnect_task)

    async def _ensure_connected(self) -> None:
        """Wait for the connection to be established."""
        try:
            await asyncio.wait_for(
                self._connected_event.wait_set(), timeout=self.connection_timeout
            )
        except asyncio.TimeoutError:
            raise ConnectionError(
                f"Failed to connect to within {self.connection_timeout}s"
            )

    async def _cleanup_connection(self) -> None:
        """Clean up the current connection."""
        _LOGGER.info("Cleaning up connection")
        async with self._disconnect_lock:
            self._connected_event.clear()
            await cancel_task(self._read_task)
            await self._transport.disconnect()
            await self._cleanup_callbacks()

    async def _cleanup_callbacks(self) -> None:
        """Invoke all callbacks with a disconnection error."""
        async with self._callback_lock:
            for callback in self._callbacks.values():
                try:
                    callback(ConnectionError("Connection closed"))
                except Exception as e:
                    _LOGGER.exception("Callback failed during cleanup: %s", e)
            self._callbacks.clear()

    async def _establish_connection(self) -> None:
        """Establish the transport connection and authenticate."""
        async with self._connect_lock:
            if self._connected_event.is_set():
                return

            await self._transport.connect()
            self._read_task = asyncio.create_task(self._read_loop())

            _LOGGER.debug("Authenticating...")
            await self._authenticate()

            self._connected_event.set()
            _LOGGER.info("Connected and authenticated to Eci panel")

    async def _read_loop(self) -> None:
        """Continuously read data from the queue and dispatch to callbacks."""
        while True:
            try:
                data = await self._transport.read()
                async with self._callback_lock:
                    for listener in self._callbacks.values():
                        try:
                            listener(data)
                        except Exception as e:
                            _LOGGER.exception("Callback failed: %s", e)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _LOGGER.error("Read loop error: %s", e)
                self._connected_event.clear()
                break

    async def _reconnect_worker(self) -> None:
        """While not cancelled, attempt to reconnect when disconnected."""
        while not self._cancel_event.is_set():
            await self._connected_event.wait_clear()
            for attempt in range(self.max_retries):
                try:
                    await asyncio.wait_for(
                        self._establish_connection(),
                        timeout=self.connection_timeout,
                    )
                    break
                except Exception as e:
                    _LOGGER.error(
                        "Attempt %d/%d failed: %s", attempt + 1, self.max_retries, e
                    )
                    if attempt + 1 == self.max_retries:
                        _LOGGER.error("Max reconnect attempts reached")
                        return

                try:
                    await asyncio.wait_for(
                        self._cancel_event.wait(), timeout=self.reconnect_delay
                    )
                    return
                except asyncio.TimeoutError:
                    pass

    async def readline(self, delimiter: str, timeout: float | None = None) -> str:
        """Read a single line terminated by the specified delimiter.

        Args:
            delimiter: Delimiter indicating end of line.
            timeout: Optional timeout for the read operation.

        Returns: The line read from the transport.

        """
        await self._ensure_connected()
        listener, future = line_listener(delimiter)
        async with self._read_context(listener):
            return await asyncio.wait_for(future, timeout=timeout)

    async def _write_raw(self, data: str) -> None:
        """Write data to the connection.

        Args:
            data: Data string to send.

        """
        _LOGGER.debug("Writing to transport: %s", data)
        try:
            await self._transport.write(data)
        except Exception as e:
            _LOGGER.error("Write failed: %s", e)
            self._connected_event.clear()
            raise

    async def writeline(self, data: str, delimiter: str) -> None:
        """Write a message with the specified delimiter.

        Args:
            data: Data string to write.
            delimiter: Delimiter to append to the data.

        """
        await self._ensure_connected()
        await self._transport.write(add_delimiter_if_missing(data, delimiter))

    async def request(
        self, request: Request[T], delimiter: str = "\n", timeout: float | None = None
    ) -> T:
        """Send a message and register a listener for the response."""
        await self._ensure_connected()
        return await asyncio.wait_for(
            self._request_raw(request, delimiter), timeout=timeout
        )

    async def _request_raw(self, request: Request[T], delimiter: str) -> T:
        """Send a message and register a listener for the response."""
        async with self._read_context(request.callback):
            await self._write_raw(add_delimiter_if_missing(request.data, delimiter))
            return await request.awaitable

    @asynccontextmanager
    async def _read_context(
        self, callback: Callable[[Exception | str], None]
    ) -> AsyncIterator[None]:
        """Context manager to register a read callback.

        Args:
            callback: Callback to invoke on received messages.

        """
        listener_id = str(uuid.uuid4())
        async with self._callback_lock:
            self._callbacks[listener_id] = callback
        try:
            yield
        finally:
            async with self._callback_lock:
                self._callbacks.pop(listener_id, None)

    async def _authenticate(self) -> None:
        """Handle authentication based on initial prompts."""
        listener, future = string_options_listener(AUTH_WELCOME_MSG, AUTH_LOGIN_MSG)
        try:
            async with self._read_context(listener):
                resp = await future
        except ConnectionError as e:
            _LOGGER.error("Authentication detection failed: connection reset")
            raise InvalidCredentialsError() from e
        else:
            _LOGGER.debug("Auth detection received: %s", resp)
            if resp == AUTH_WELCOME_MSG:
                _LOGGER.debug("No authentication required")
                return
            elif resp == AUTH_LOGIN_MSG:
                _LOGGER.debug("Username/password authentication required")
                await self._authenticate_credentials()
            else:
                _LOGGER.error("Unexpected authentication prompt: %s", resp)
                raise InvalidResponseError(resp, [AUTH_WELCOME_MSG, AUTH_LOGIN_MSG])

    async def _authenticate_credentials(self) -> None:
        """Perform authentication based on provided credentials."""
        if not self.credentials:
            _LOGGER.error("No credentials provided when required")
            raise MissingCredentialsError()
        try:
            req = string_options_request(
                self.credentials.username, [AUTH_PASSWORD_PROMPT], False
            )
            await self._request_raw(req, delimiter="\n")

            req = string_options_request(
                self.credentials.password, [AUTH_WELCOME_MSG], False
            )
            await self._request_raw(req, delimiter="\n")

            _LOGGER.debug("Password accepted, authentication successful")
        except ConnectionError as e:
            _LOGGER.error("Authentication failed: %s", type(e).__name__)
            raise
