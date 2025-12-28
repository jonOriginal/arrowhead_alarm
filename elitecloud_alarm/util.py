"""Utility functions for Eci Alarm integration."""

import asyncio
import logging
import re
from asyncio import Task
from typing import Any

from .types import PanelVersion, VersionInfo

_LOGGER = logging.getLogger(__name__)


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


def parse_version_string(version_resp: str) -> PanelVersion:
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
