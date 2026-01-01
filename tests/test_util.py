# ruff: noqa

import asyncio

import pytest

from arrowhead_alarm.types import ToggleEvent
from arrowhead_alarm.util import parse_panel_version_string, split_complete_lines


def test_version_parsing():
    version_output = """ECi F/W Ver. 10.3.52 (WR5SPLS1)"""

    version = parse_panel_version_string(version_output)
    assert version.model == "ECi"
    assert version.firmware_version.major_version == 10
    assert version.firmware_version.minor_version == 3
    assert version.firmware_version.patch_version == 52


def test_version_parsing_with_unexpected_format():
    version_output = """Unexpected Format String"""

    with pytest.raises(ValueError):
        parse_panel_version_string(version_output)


def test_version_comparison():
    v1 = parse_panel_version_string("ECi F/W Ver. 10.3.52 (WR5SPLS1)")
    v2 = parse_panel_version_string("ECi F/W Ver. 10.4.0 (WR5SPLS1)")
    v3 = parse_panel_version_string("ECi F/W Ver. 11.0.0 (WR5SPLS1)")

    assert v1.firmware_version < v2.firmware_version
    assert v2.firmware_version < v3.firmware_version
    assert v3.firmware_version > v1.firmware_version
    assert v1.firmware_version <= v1.firmware_version
    assert v2.firmware_version >= v1.firmware_version


def test_version_equality():
    v1 = parse_panel_version_string("ECi F/W Ver. 10.3.52 (WR5SPLS1)")
    v2 = parse_panel_version_string("ECi F/W Ver. 10.3.52 (W4RXPY2A)")

    assert v1.firmware_version == v2.firmware_version


def test_version_inequality():
    v1 = parse_panel_version_string("ECi F/W Ver. 10.3.52 (WR5SPLS1)")
    v2 = parse_panel_version_string("ECi F/W Ver. 10.3.53 (WR5SPLS1)")

    assert v1.firmware_version != v2.firmware_version


def test_toggle_event_init():
    toggle_event = ToggleEvent()
    assert toggle_event.is_clear()
    assert not toggle_event.is_set()


def test_toggle_event_set():
    toggle_event = ToggleEvent()
    toggle_event.set()
    assert toggle_event.is_set()
    assert not toggle_event.is_clear()


def test_toggle_event_clear():
    toggle_event = ToggleEvent()
    toggle_event.clear()
    assert toggle_event.is_clear()
    assert not toggle_event.is_set()


@pytest.mark.asyncio
async def test_toggle_event_wait_set():
    toggle_event = ToggleEvent()

    async def set_event_later():
        await asyncio.sleep(0.1)
        toggle_event.set()

    asyncio.create_task(set_event_later())
    await toggle_event.wait_until_set()
    assert toggle_event.is_set()


@pytest.mark.asyncio
async def test_toggle_event_wait_clear():
    toggle_event = ToggleEvent()
    toggle_event.set()

    async def clear_event_later():
        await asyncio.sleep(0.1)
        toggle_event.clear()

    asyncio.create_task(clear_event_later())
    await toggle_event.wait_until_clear()
    assert toggle_event.is_clear()


@pytest.mark.asyncio
async def test_split_complete_lines():
    data = "line1\nline2\npartial_line"
    lines = split_complete_lines(data, delimiter="\n")
    assert lines == ["line1", "line2"]


@pytest.mark.asyncio
async def test_split_complete_lines_no_complete():
    data = "partial_line"
    lines = split_complete_lines(data, delimiter="\r\n")
    assert lines == []


@pytest.mark.asyncio
async def test_split_complete_lines_different_delimiter():
    data = "line1\r\nline2\r\npartial_line"
    lines = split_complete_lines(data, delimiter="\r\n")
    assert lines == ["line1", "line2"]


@pytest.mark.asyncio
async def test_split_complete_lines_empty_string():
    data = ""
    lines = split_complete_lines(data, delimiter="\n")
    assert lines == []
