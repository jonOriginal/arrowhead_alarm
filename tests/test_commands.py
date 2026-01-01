import asyncio

import pytest

from elitecloud_alarm.commands import mode_command
from elitecloud_alarm.types import ProtocolMode
from elitecloud_alarm.util import get_delimiter_for_mode


@pytest.mark.asyncio
async def test_mode_command() -> None:
    delimiter = get_delimiter_for_mode(ProtocolMode.MODE_1)
    request = mode_command(ProtocolMode.MODE_1)
    assert request.data == "MODE 1"

    response = f"OK{delimiter}Mode 1{delimiter}"
    request.response_callback(response)

    result = await asyncio.wait_for(request.awaitable, timeout=1.0)
    assert result == delimiter
