class ProtocolError(Exception):
    """Base class for protocol-related errors."""

    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"ProtocolError: {self.message}"


class InvalidResponseError(ProtocolError):
    """Raised when an unexpected response is received from the device."""

    def __init__(self, received: str, expected: str | list[str]):
        if isinstance(expected, list):
            expected_str = ", ".join(expected)
        else:
            expected_str = expected
        super().__init__(f"Invalid response received: '{received}'. Expected: '{expected_str}'.")


class CommandError(ProtocolError):
    """Raised when an error response is received from the device."""

    def __init__(self, error: str, command: str, response: str):
        super().__init__(f"Command '{command}' failed with error {error}: '{response}'")
        self.error = error
        self.command = command
        self.response = response


class XModemSessionFailed(CommandError):
    """Raised when an XModem session fails."""

    def __init__(self, command: str, response: str):
        super().__init__("XModem session failed", command, response)


class CommandNotUnderstood(CommandError):
    """Raised when the device does not understand the command."""

    def __init__(self, command: str, response: str):
        super().__init__("Command not understood", command, response)


class InvalidParameter(CommandError):
    """Raised when the alarm reports an invalid parameter for a command."""

    def __init__(self, command: str, response: str):
        super().__init__("Invalid parameters", command, response)


class CommandNotAllowed(CommandError):
    """Raised when the alarm reports that a command is not allowed in the current state."""

    def __init__(self, command: str, response: str):
        super().__init__("Command not allowed", command, response)


class RxBufferOverflow(CommandError):
    """Raised when the alarm's receive buffer overflows."""

    def __init__(self, command: str, response: str):
        super().__init__("Receive buffer overflow", command, response)


class TxBufferOverflow(CommandError):
    """Raised when the alarm's transmit buffer overflows."""

    def __init__(self, command: str, response: str):
        super().__init__("Transmit buffer overflow", command, response)


class AuthError(Exception):
    """Base class for authentication-related errors."""
    pass


class NoUnionMatchError(Exception):
    def __init__(self, buffer: str):
        super().__init__(f"No matching option for input: '{buffer}'")
        self.buffer = buffer


class MissingCredentialsError(AuthError):
    """Raised when credentials are required but not provided."""

    def __init__(self, *args):
        super().__init__("Credentials are required for authentication but were not provided.", *args)


class InvalidCredentialsError(AuthError):
    """Raised when provided credentials are invalid."""

    def __init__(self):
        super().__init__("Provided credentials are invalid.")
