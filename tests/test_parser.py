"""Tests for the ECI Alarm parsing and command processing."""
# pyright: reportPrivateUsage=false

import asyncio

import pytest

from elitecloud_alarm.commands import (
    _arm_command_processor,
    arm_area_command,
    arm_user_command,
)
from elitecloud_alarm.parsing import (
    Error,
    FlowResult,
    Go,
    Wait,
    create_future_parser,
    create_sliding_timeout_parser,
    line_listener,
    wait_lines,
)
from elitecloud_alarm.types import ArmingMode


@pytest.mark.asyncio
class TestParsing:
    @staticmethod
    def processor(response: str) -> FlowResult[list[str]]:
        lines = response.splitlines()
        if len(lines) >= 2:
            return Go(lines)
        return Wait()

    async def test_timer_listener(self):
        listener, fut = create_sliding_timeout_parser(self.processor, timeout=1.0)
        listener("line1\nline2\n")
        result = await fut

        assert isinstance(result, list)
        assert len(result) == 2

    async def test_timer_listener_multiple_feeds(self):
        listener, fut = create_sliding_timeout_parser(self.processor, timeout=1.0)
        listener("line1\nline2\n")
        await asyncio.sleep(0.5)
        listener("line3\nline4\nline5\n")
        result = await fut

        assert isinstance(result, list)
        assert len(result) == 5

    async def test_timer_listener_timeout(self):
        listener, fut = create_sliding_timeout_parser(self.processor, timeout=0.5)
        listener("line1\n")
        with pytest.raises(asyncio.TimeoutError):
            await fut

    async def test_timer_listener_error(self):
        def error_processor(response: str) -> FlowResult[None]:
            return Error(Exception("Test error"))

        listener, fut = create_sliding_timeout_parser(error_processor, timeout=1.0)
        listener("line1\n")
        with pytest.raises(Exception, match="Test error"):
            await fut

    async def test_timer_exception(self):
        def exception_processor(response: str) -> FlowResult[None]:
            raise ValueError("Processor exception")

        listener, fut = create_sliding_timeout_parser(exception_processor, timeout=1.0)
        listener("line1\n")
        with pytest.raises(ValueError, match="Processor exception"):
            await fut

    async def test_line_listener(self):
        line_waiter, fut = line_listener("\n")
        line_waiter("line1\nline2\nline3\n")
        line = await fut
        assert line == "line1"

    async def test_line_count_listener(self):
        def processor(response: str) -> FlowResult[list[str]]:
            return wait_lines(response, 3, "\n")

        line_waiter, fut = create_future_parser(processor)
        line_waiter("line1\nline2\nline3\nline4\n")
        lines = await fut
        assert isinstance(lines, list)
        assert len(lines) == 3
        assert lines == ["line1", "line2", "line3"]

    async def test_line_count_listener_incomplete(self):
        def processor(response: str) -> FlowResult[list[str]]:
            return wait_lines(response, 3, "\n")

        line_waiter, fut = create_future_parser(processor)
        line_waiter("line1\nline2\npartial_line")
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(fut, timeout=0.5)

    async def test_line_count_listener_multiple_feeds(self):
        def processor(response: str) -> FlowResult[list[str]]:
            return wait_lines(response, 4, "\n")

        line_waiter, fut = create_future_parser(processor)
        line_waiter("line1\nline2\n")
        await asyncio.sleep(0.2)
        line_waiter("line3\nline4\n")
        lines = await fut
        assert isinstance(lines, list)
        assert len(lines) == 4
        assert lines == ["line1", "line2", "line3", "line4"]

    async def test_arm_command_processor(self):
        response = "OK ARMAWAY 1\n"
        result = _arm_command_processor(response, "ARMAWAY 1", "ARMAWAY", "\n")
        assert isinstance(result, Go)
        assert result.value == 1

    async def test_arm_command_processor_error(self):
        response = "ERR 5\n"
        result = _arm_command_processor(response, "ARMAWAY 1", "ARMAWAY", "\n")
        assert isinstance(result, Error)

    async def test_arm_command_processor_invalid_int(self):
        response = "OK ARMAWAY X\n"
        result = _arm_command_processor(response, "ARMAWAY 1", "ARMAWAY", "\n")
        assert isinstance(result, Error)

    async def test_armaway_area_command(self):
        request = arm_area_command(1, ArmingMode.AWAY, "\n")
        assert request.data == "ARMAWAY 1"
        response = "OK ARMAWAY 1\n"

        request.callback(response)
        result = await request.awaitable
        assert result == 1

    async def test_armstay_area_command(self):
        request = arm_area_command(2, ArmingMode.STAY, "\n")
        assert request.data == "ARMSTAY 2"
        response = "OK ARMSTAY 2\n"

        request.callback(response)
        result = await request.awaitable
        assert result == 2

    async def test_armstay_area_command_error(self):
        request = arm_area_command(2, ArmingMode.STAY, "\n")
        assert request.data == "ARMSTAY 2"
        response = "ERR 3\n"

        request.callback(response)
        with pytest.raises(Exception):
            await request.awaitable

    async def test_armstay_area_command_invalid_int(self):
        request = arm_area_command(2, ArmingMode.STAY, "\n")
        assert request.data == "ARMSTAY 2"
        response = "OK ARMSTAY X\n"

        request.callback(response)
        with pytest.raises(Exception):
            await request.awaitable

    async def test_armaway_user_command(self):
        request = arm_user_command(1, 123, ArmingMode.AWAY, "\n")
        assert request.data == "ARMAWAY 1 123"
        response = "OK ARMAWAY 1\n"

        request.callback(response)
        result = await request.awaitable
        assert result == 1

    async def test_armstay_user_command(self):
        request = arm_user_command(2, 456, ArmingMode.STAY, "\n")
        assert request.data == "ARMSTAY 2 456"
        response = "OK ARMSTAY 2\n"

        request.callback(response)
        result = await request.awaitable
        assert result == 2

    async def test_armstay_user_command_error(self):
        request = arm_user_command(2, 456, ArmingMode.STAY, "\n")
        assert request.data == "ARMSTAY 2 456"
        response = "ERR 4\n"

        request.callback(response)
        with pytest.raises(Exception):
            await request.awaitable

    async def test_armstay_user_command_invalid_int(self):
        request = arm_user_command(2, 456, ArmingMode.STAY, "\n")
        assert request.data == "ARMSTAY 2 456"
        response = "OK ARMSTAY X\n"

        request.callback(response)
        with pytest.raises(Exception):
            await request.awaitable
