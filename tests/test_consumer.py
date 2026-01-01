"""Tests for the ECI Alarm parsing and command processing."""

# ruff: noqa
# pyright: reportPrivateUsage=false
import asyncio

import pytest

from arrowhead_alarm.commands import (
    arm_area_command,
    arm_user_command,
)
from arrowhead_alarm.consumers import (
    Error,
    FlowResult,
    Go,
    Wait,
    create_future_consumer,
    create_sliding_timeout_consumer,
    line_consumer,
)
from arrowhead_alarm.transformers import wait_lines
from arrowhead_alarm.types import ArmingMode


def line_processor(response: str) -> FlowResult[list[str]]:
    lines = response.splitlines()
    if len(lines) >= 2:
        return Go(lines)
    return Wait()


@pytest.mark.asyncio
async def test_timer_consumer():
    consumer, fut = create_sliding_timeout_consumer(line_processor, timeout=1.0)
    consumer("line1\nline2\n")
    result = await fut

    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_timer_consumer_multiple_feeds():
    consumer, fut = create_sliding_timeout_consumer(line_processor, timeout=1.0)
    consumer("line1\nline2\n")
    await asyncio.sleep(0.5)
    consumer("line3\nline4\nline5\n")
    result = await fut

    assert isinstance(result, list)
    assert len(result) == 5


@pytest.mark.asyncio
async def test_timer_consumer_timeout():
    consumer, fut = create_sliding_timeout_consumer(line_processor, timeout=0.5)
    consumer("line1\n")
    with pytest.raises(TimeoutError):
        await fut


@pytest.mark.asyncio
async def test_timer_consumer_error():
    def error_processor(response: str) -> FlowResult[None]:
        return Error(Exception("Test error"))

    consumer, fut = create_sliding_timeout_consumer(error_processor, timeout=1.0)
    consumer("line1\n")
    with pytest.raises(Exception, match="Test error"):
        await fut


@pytest.mark.asyncio
async def test_timer_exception():
    def exception_processor(response: str) -> FlowResult[None]:
        raise ValueError("Processor exception")

    consumer, fut = create_sliding_timeout_consumer(exception_processor, timeout=1.0)
    consumer("line1\n")
    with pytest.raises(ValueError, match="Processor exception"):
        await fut


@pytest.mark.asyncio
async def test_line_consumer():
    line_waiter, fut = line_consumer("\n")
    line_waiter("line1\nline2\nline3\n")
    line = await fut
    assert line == "line1"


@pytest.mark.asyncio
async def test_line_count_consumer():
    def processor(response: str) -> FlowResult[list[str]]:
        return wait_lines(response, 3, "\n")

    line_waiter, fut = create_future_consumer(processor)
    line_waiter("line1\nline2\nline3\nline4\n")
    lines = await fut
    assert isinstance(lines, list)
    assert len(lines) == 3
    assert lines == ["line1", "line2", "line3"]


@pytest.mark.asyncio
async def test_line_count_consumer_incomplete():
    def processor(response: str) -> FlowResult[list[str]]:
        return wait_lines(response, 3, "\n")

    line_waiter, fut = create_future_consumer(processor)
    line_waiter("line1\nline2\npartial_line")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(fut, timeout=0.5)


@pytest.mark.asyncio
async def test_line_count_consumer_multiple_feeds():
    def processor(response: str) -> FlowResult[list[str]]:
        return wait_lines(response, 4, "\n")

    line_waiter, fut = create_future_consumer(processor)
    line_waiter("line1\nline2\n")
    await asyncio.sleep(0.2)
    line_waiter("line3\nline4\n")
    lines = await fut
    assert isinstance(lines, list)
    assert len(lines) == 4
    assert lines == ["line1", "line2", "line3", "line4"]


@pytest.mark.asyncio
async def test_armaway_area_command():
    request = arm_area_command(1, ArmingMode.AWAY, "\n")
    assert request.data == "ARMAWAY 1"
    response = "OK ARMAWAY 1\n"

    request.response_callback(response)
    result = await request.awaitable
    assert result == 1


@pytest.mark.asyncio
async def test_armstay_area_command():
    request = arm_area_command(2, ArmingMode.STAY, "\n")
    assert request.data == "ARMSTAY 2"
    response = "OK ARMSTAY 2\n"

    request.response_callback(response)
    result = await request.awaitable
    assert result == 2


@pytest.mark.asyncio
async def test_armstay_area_command_error():
    request = arm_area_command(2, ArmingMode.STAY, "\n")
    assert request.data == "ARMSTAY 2"
    response = "ERR 3\n"

    request.response_callback(response)
    with pytest.raises(Exception):
        await request.awaitable


@pytest.mark.asyncio
async def test_armstay_area_command_invalid_int():
    request = arm_area_command(2, ArmingMode.STAY, "\n")
    assert request.data == "ARMSTAY 2"
    response = "OK ARMSTAY X\n"

    request.response_callback(response)
    with pytest.raises(Exception):
        await request.awaitable


@pytest.mark.asyncio
async def test_armaway_user_command():
    request = arm_user_command(1, 123, ArmingMode.AWAY, "\n")
    assert request.data == "ARMAWAY 1 123"
    response = "OK ARMAWAY 1\n"

    request.response_callback(response)
    result = await request.awaitable
    assert result == 1


@pytest.mark.asyncio
async def test_armstay_user_command():
    request = arm_user_command(2, 456, ArmingMode.STAY, "\n")
    assert request.data == "ARMSTAY 2 456"
    response = "OK ARMSTAY 2\n"

    request.response_callback(response)
    result = await request.awaitable
    assert result == 2


@pytest.mark.asyncio
async def test_armstay_user_command_error():
    request = arm_user_command(2, 456, ArmingMode.STAY, "\n")
    assert request.data == "ARMSTAY 2 456"
    response = "ERR 4\n"

    request.response_callback(response)
    with pytest.raises(Exception):
        await request.awaitable


@pytest.mark.asyncio
async def test_armstay_user_command_invalid_int():
    request = arm_user_command(2, 456, ArmingMode.STAY, "\n")
    assert request.data == "ARMSTAY 2 456"
    response = "OK ARMSTAY X\n"

    request.response_callback(response)
    with pytest.raises(Exception):
        await request.awaitable
