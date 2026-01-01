import asyncio
from typing import Callable, TypeVar

import pytest

from arrowhead_alarm import commands
from arrowhead_alarm.commands import (
    mode_command,
    set_output_state_command,
)
from arrowhead_alarm.types import (
    ArmingMode,
    ProtocolMode,
    Request,
)
from arrowhead_alarm.util import get_delimiter_for_mode

T = TypeVar("T")


async def _test_command(
    command_func: Callable[..., Request[T]],
    func_args: tuple,
    expected_command: str,
    response: str,
    expected_result: T,
) -> None:
    request = command_func(*func_args)
    assert request.data == expected_command

    request.response_callback(response)

    result = await asyncio.wait_for(request.awaitable, timeout=1.0)
    assert result == expected_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id,pin,mode,delimiter,expected_cmd,response,expected_result",
    [
        (1, 1234, ArmingMode.AWAY, "\r\n", "ARMAWAY 1 1234", "OK ArmAway 1\r\n", 1),
        (2, 0, ArmingMode.STAY, "\r\n", "ARMSTAY 2 0", "OK ArmStay 2\r\n", 2),
    ],
)
async def test_arm_user_command(
    user_id: int,
    pin: int,
    mode: ArmingMode,
    delimiter: str,
    expected_cmd: str,
    response: str,
    expected_result: int,
) -> None:
    await _test_command(
        commands.arm_user_command,
        (user_id, pin, mode, delimiter),
        expected_cmd,
        response,
        expected_result,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id,pin,delimiter,expected_cmd,response,expected_result",
    [
        (1, 1234, "\r\n", "DISARM 1 1234", "OK Disarm 1\r\n", 1),
        (2, 0, "\r\n", "DISARM 2 0", "OK Disarm 2\r\n", 2),
    ],
)
async def test_disarm_command(
    user_id: int,
    pin: int,
    delimiter: str,
    expected_cmd: str,
    response: str,
    expected_result: int,
) -> None:
    await _test_command(
        commands.disarm_user_command,
        (user_id, pin, delimiter),
        expected_cmd,
        response,
        expected_result,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "area_id,mode,delimiter,expected_cmd,response,expected_result",
    [
        (1, ArmingMode.AWAY, "\r\n", "ARMAWAY 1", "OK ArmAway 1\r\n", 1),
        (2, ArmingMode.STAY, "\r\n", "ARMSTAY 2", "OK ArmStay 2\r\n", 2),
    ],
)
async def test_arm_area_command(
    area_id: int,
    mode: ArmingMode,
    delimiter: str,
    expected_cmd: str,
    response: str,
    expected_result: int,
):
    await _test_command(
        commands.arm_area_command,
        (area_id, mode, delimiter),
        expected_cmd,
        response,
        expected_result,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "zone_id,bypass,delimiter,expected_cmd,response,expected_result",
    [
        (1, True, "\r\n", "BYPASS 1", "OK Bypass 1\r\n", 1),
        (2, False, "\r\n", "UNBYPASS 2", "OK UnBypass 2\r\n", 2),
    ],
)
async def test_bypass_unbypass_zone_commands(
    zone_id: int,
    bypass: bool,
    delimiter: str,
    expected_cmd: str,
    response: str,
    expected_result: int,
):
    await _test_command(
        commands.set_zone_bypass_command,
        (zone_id, bypass, delimiter),
        expected_cmd,
        response,
        expected_result,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output_id,on,delimiter,expected_cmd,response,expected_result",
    [
        (1, True, "\r\n", "OUTPUTON 1", "OK OutputOn 1\r\n", 1),
        (2, False, "\n", "OUTPUTOFF 2", "OK OutputOff 2\n", 2),
        (3, True, "\r", "OUTPUTON 3", "OK OutputOn 3\r", 3),
    ],
)
async def test_output_on_off_commands(
    output_id: int,
    on: bool,
    delimiter: str,
    expected_cmd: str,
    response: str,
    expected_result: int,
):
    await _test_command(
        set_output_state_command,
        (output_id, on, delimiter),
        expected_cmd,
        response,
        output_id,
    )


@pytest.mark.parametrize(
    "delimiter,output_num,expected_cmd,response,expected_result",
    [
        ("\r\n", 4, "OUTPUT 4", "OK Output 4 On\r\n", True),
        ("\n", 2, "OUTPUT 2", "OK Output 2 Off\n", False),
        ("\r", 1, "OUTPUT 1", "OK Output 1 On\r", True),
    ],
)
@pytest.mark.asyncio
async def test_output_state_command(
    delimiter: str,
    output_num: int,
    expected_cmd: str,
    response: str,
    expected_result: bool,
) -> None:
    await _test_command(
        commands.get_output_state_command,
        (output_num, delimiter),
        expected_cmd,
        response,
        expected_result,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "delimiter,expected_cmd,response",
    [
        ("\r\n", "Status", "OK Status\r\nRO\r\nDF\r\n"),
        ("\n", "Status", "OK Status\nRO\nDF\n"),
        ("\r", "Status", "OK Status\rZO4\rZSA12\r"),
    ],
)
async def test_status_command(delimiter: str, expected_cmd: str, response: str) -> None:
    request = commands.status_command(delimiter)
    assert request.data == expected_cmd

    request.response_callback(response)
    result = await asyncio.wait_for(request.awaitable, timeout=1.0)

    assert isinstance(result, list)
    assert all(callable(op) for op in result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,expected_cmd,response,expected_result",
    [
        (
            ProtocolMode.MODE_1,
            "MODE 1",
            "OK\r\nMode 1\r\n",
            "\r\n",
        ),
        (
            ProtocolMode.MODE_2,
            "MODE 2",
            "OK\nMode 2\n",
            "\n",
        ),
        (
            ProtocolMode.MODE_3,
            "MODE 3",
            "OK\nMode 3\n",
            "\n",
        ),
        (
            ProtocolMode.MODE_4,
            "MODE 4",
            "OK\nMode 4\n",
            "\n",
        ),
    ],
)
async def test_mode_command(
    mode: ProtocolMode,
    expected_cmd: str,
    response: str,
    expected_result: str,
) -> None:
    await _test_command(
        mode_command,
        (mode,),
        expected_cmd,
        response,
        expected_result,
    )
