"""Utility functions for Arrowhead alarm integration."""

import asyncio
import logging
import re
from asyncio import Task
from typing import Any, Final, Mapping, TypeVar

from .exceptions import (
    CommandError,
    CommandNotAllowedError,
    CommandNotUnderstoodError,
    InvalidParameterError,
    RxBufferOverflowError,
    TxBufferOverflowError,
    XModemSessionFailedError,
)
from .types import (
    AlarmCapabilities,
    ArmingCapabilities,
    ArmingMode,
    DisarmingCapabilities,
    Fail,
    Outcome,
    PanelVersion,
    ProtocolMode,
    Status,
    Success,
    VersionInfo,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def split_complete_lines(response: str, delimiter: str) -> list[str]:
    """Split the response into complete lines based on the specified delimiter.

    Args:
        response: The response string to split.
        delimiter: The delimiter used to split the response.

    Returns: List of complete lines without any trailing incomplete line.

    """
    lines = response.split(delimiter)
    return lines[:-1]


async def cancel_task(task: Task[Any] | None) -> None:
    """Cancel the given asyncio task if it is not already done.

    Args:
        task: The asyncio task to cancel.

    """
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            _LOGGER.warning("Error while cancelling task: %s", type(e).__name__)


version_regex = re.compile(
    r"^([A-Za-z]+)\s+F/W\s+Ver\.\s+(\d+)\.(\d+)\.(\d+)\s+\(([^)]+)\)$"
)


def parse_panel_version_string(version_resp: str) -> PanelVersion:
    """Parse the version response returned by the panel.

    Args:
        version_resp: Version response string.

    Returns: PanelVersion object representing the parsed version information.

    """
    match = version_regex.match(version_resp.strip())
    if not match:
        raise ValueError(f"Invalid version string format: {version_resp}")
    try:
        model = match.group(1)
        major = int(match.group(2))
        minor = int(match.group(3))
        patch = int(match.group(4))
        serial_number = match.group(5)
    except (IndexError, ValueError):
        raise ValueError(f"Invalid version string format: {version_resp}")

    return PanelVersion(
        model=model,
        firmware_version=VersionInfo(major, minor, patch),
        serial_number=serial_number,
    )


def get_command_exception(error_code: int, command: str, response: str) -> Exception:
    """Return the appropriate CommandError exception based on the error code.

    Args:
        error_code: Error code returned by the panel.
        command: Command string that was sent.
        response: response string.

    Returns: Corresponding CommandError exception.

    """
    match error_code:
        case 1:
            return CommandNotUnderstoodError(command, response)
        case 2:
            return InvalidParameterError(command, response)
        case 3:
            return CommandNotAllowedError(command, response)
        case 4:
            return RxBufferOverflowError(command, response)
        case 5:
            return TxBufferOverflowError(command, response)
        case 6:
            return XModemSessionFailedError(command, response)
        case _:
            return CommandError(f"Unknown error code {error_code}", command, response)


def is_mode_4_supported(version: VersionInfo) -> bool:
    """Check if Protocol Mode 4 is supported for the given firmware version.

    Args:
        version: Firmware version.

    Returns: True if Protocol Mode 4 is supported, False otherwise.

    """
    return version >= VersionInfo(10, 3, 50)


def add_delimiter_if_missing(message: str, delimiter: str) -> str:
    """Add the delimiter to the message if it is missing.

    Args:
        message: The message string.
        delimiter: The delimiter to add if missing.
    Returns: The message with the delimiter added if it was missing.

    """
    if not message.endswith(delimiter):
        return message + delimiter
    return message


def get_arming_keyword(mode: ArmingMode) -> str:
    """Return the arming command keyword for the given arming mode.

    Args:
        mode (ArmingMode): The arming mode.

    Returns:
        str: The corresponding arming command keyword.

    Raises:
        ValueError: If the arming mode is unsupported.

    """
    match mode:
        case ArmingMode.AWAY:
            return "ARMAWAY"
        case ArmingMode.STAY:
            return "ARMSTAY"
        case _:
            raise ValueError(f"Unsupported arming mode: {mode}")


def search_prefix(query: str, data: Mapping[str, T]) -> T | None:
    """Search for the first matching prefix of the query in the data mapping.

    Args:
        query: String to search for prefixes within.
        data: The dictionary or mapping to search in.

    Returns:
        The value associated with the first found prefix, or None if no match is found.

    """
    prefix = ""
    for char in query:
        prefix += char
        if prefix in data:
            return data[prefix]
    return None


def get_mode_capabilites(mode: ProtocolMode) -> AlarmCapabilities:
    """Get the alarm capabilities based on the protocol mode."""
    capabilities = AlarmCapabilities()
    match mode:
        case ProtocolMode.MODE_1:
            capabilities.all_zones_ready_status = True
            capabilities.arming = (
                ArmingCapabilities.USER_ID_AND_PIN | ArmingCapabilities.ONE_PUSH
            )
            capabilities.disarming = DisarmingCapabilities.USER_ID_AND_PIN
        case ProtocolMode.MODE_2:
            capabilities.all_zones_ready_status = False
            capabilities.arming = ArmingCapabilities.INDIVIDUAL_AREA
            capabilities.disarming = DisarmingCapabilities.INDIVIDUAL_AREA_WITH_USER_PIN
        case ProtocolMode.MODE_4:
            capabilities.all_zones_ready_status = False
            capabilities.arming = (
                ArmingCapabilities.INDIVIDUAL_AREA | ArmingCapabilities.USER_ID_AND_PIN
            )
            capabilities.disarming = DisarmingCapabilities.USER_ID_AND_PIN
        case _:
            raise NotImplementedError
    return capabilities


STATUS_RE: Final = re.compile(
    r"^(?P<status>[A-Z]+)"
    r"(?P<number>\d+)?"
    r"(?:[-\s]"
    r"(?:"
    r"(?P<timestamp>\d+\.\d+)"
    r"|U(?P<user_number>\d+)"
    r")"
    r")?"
    r"(?:\s(?P<extender_status>[A-Z]{1,2})(?P<extender_number>\d+))?"
    r"$"
)


def parse_status(message: str) -> Outcome[Status]:
    """Parse a status message.

    Args:
        message: The status message string.

    Returns:
        CombinedStatus object.

    Raises:
        ValueError: If the message format is invalid.

    """
    match = STATUS_RE.match(message)
    if not match:
        return Fail(ValueError(f"Invalid status message format: {message}"))

    code_str = match.group("status")
    number_str = match.group("number")
    timestamp_str = match.group("timestamp")
    user_number_str = match.group("user_number")
    extender_code_str = match.group("extender_status")
    extender_number_str = match.group("extender_number")

    return Success(
        Status(
            code=code_str,
            number=int(number_str) if number_str is not None else None,
            timestamp=float(timestamp_str) if timestamp_str is not None else None,
            user_number=int(user_number_str) if user_number_str is not None else None,
            expander_code=extender_code_str,
            expander_number=int(extender_number_str)
            if extender_number_str is not None
            else None,
        )
    )


def get_delimiter_for_mode(mode: ProtocolMode) -> str:
    """Get the line delimiter based on the protocol mode.

    Args:
        mode: The protocol mode.

    Returns:
        The corresponding line delimiter.

    """
    match mode:
        case ProtocolMode.MODE_1:
            return "\r\n"
        case ProtocolMode.MODE_4 | ProtocolMode.MODE_2 | ProtocolMode.MODE_3:
            return "\n"
        case _:
            raise NotImplementedError
