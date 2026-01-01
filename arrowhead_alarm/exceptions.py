"""Custom exceptions for the Arrowhead Alarm integration."""


class ProtocolError(Exception):
    """Base class for protocol-related errors."""

    def __init__(self, message: str) -> None:
        """Initialize ProtocolError.

        Args:
            message: Error message describing the protocol error.

        """
        self.message = message

    def __str__(self) -> str:
        """Return string representation of the ProtocolError."""
        return f"ProtocolError: {self.message}"


class InvalidResponseError(ProtocolError):
    """Raised when an unexpected response is received from the device."""

    def __init__(self, received: str, expected: str | list[str]) -> None:
        """Initialize InvalidResponseError.

        Args:
            received: The response received from the device.
            expected: The expected response(s) from the device.

        """
        if isinstance(expected, list):
            expected_str = ", ".join(expected)
        else:
            expected_str = expected
        super().__init__(
            f"Invalid response received: '{received}'. Expected: '{expected_str}'."
        )


class CommandError(ProtocolError):
    """Raised when an error response is received from the device."""

    def __init__(self, error: str, command: str, response: str) -> None:
        """Initialize CommandError.

        Args:
            error: The error message.
            command: The command that caused the error.
            response: The response received from the device.

        """
        super().__init__(f"Command '{command}' failed with error {error}: '{response}'")
        self.error = error
        self.command = command
        self.response = response


class XModemSessionFailedError(CommandError):
    """Raised when an XModem session fails."""

    def __init__(self, command: str, response: str) -> None:
        """Initialize XModemSessionFailedError.

        Args:
            command: The command that initiated the XModem session.
            response: The response received from the device.

        """
        super().__init__("XModem session failed", command, response)


class CommandNotUnderstoodError(CommandError):
    """Raised when the device does not understand the command."""

    def __init__(self, command: str, response: str) -> None:
        """Initialize CommandNotUnderstoodError.

        Args:
            command: The command that was not understood.
            response: The response received from the device.

        """
        super().__init__("Command not understood", command, response)


class InvalidParameterError(CommandError):
    """Raised when the alarm reports an invalid parameter for a command."""

    def __init__(self, command: str, response: str) -> None:
        """Initialize InvalidParameterError.

        Args:
            command: The command with invalid parameters.
            response: The response received from the alarm.

        """
        super().__init__("Invalid parameters", command, response)


class CommandNotAllowedError(CommandError):
    """Raised when a command is not allowed in the current alarm state."""

    def __init__(self, command: str, response: str) -> None:
        """Initialize CommandNotAllowedError.

        Args:
            command: The command that is not allowed.
            response: The response received from the alarm.

        """
        super().__init__("Command not allowed", command, response)


class RxBufferOverflowError(CommandError):
    """Raised when the alarm's receive buffer overflows."""

    def __init__(self, command: str, response: str) -> None:
        """Initialize RxBufferOverflowError.

        Args:
            command: The command that caused the overflow.
            response: The response received from the alarm.

        """
        super().__init__("Receive buffer overflow", command, response)


class TxBufferOverflowError(CommandError):
    """Raised when the alarm's transmit buffer overflows."""

    def __init__(self, command: str, response: str) -> None:
        """Initialize TxBufferOverflowError.

        Args:
            command: The command that caused the overflow.
            response: The response received from the alarm.

        """
        super().__init__("Transmit buffer overflow", command, response)


class AuthError(Exception):
    """Base class for authentication-related errors."""

    pass


class NoStringMatchError(Exception):
    """Raised when no matching option is found in a union type."""

    def __init__(self, buffer: str) -> None:
        """Initialize NoUnionMatchError.

        Args:
            buffer: The input buffer that failed to match any option.

        """
        super().__init__(f"No matching option for input: '{buffer}'")
        self.buffer = buffer


class MissingCredentialsError(AuthError):
    """Raised when credentials are required but not provided."""

    def __init__(self, *args: object) -> None:
        """Initialize MissingCredentialsError.

        Args:
            *args: Additional arguments to pass to the base Exception class.

        """
        super().__init__(
            "Credentials are required for authentication but were not provided.", *args
        )


class InvalidCredentialsError(AuthError):
    """Raised when provided credentials are invalid."""

    def __init__(self) -> None:
        """Initialize InvalidCredentialsError."""
        super().__init__("Provided credentials are invalid.")
