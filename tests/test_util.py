import asyncio

import pytest

from elitecloud_alarm.types import AlarmMessage, ToggleEvent
from elitecloud_alarm.util import parse_version_string


@pytest.mark.asyncio
class TestUtil:
    def test_version_parsing(self):
        version_output = """ECi F/W Ver. 10.3.52 (WR5SPLS1)"""

        version = parse_version_string(version_output)
        assert version.model == "ECi"
        assert version.firmware_version.major_version == 10
        assert version.firmware_version.minor_version == 3
        assert version.firmware_version.patch_version == 52

    def test_version_parsing_with_unexpected_format(self):
        version_output = """Unexpected Format String"""

        with pytest.raises(ValueError):
            parse_version_string(version_output)

    def test_version_comparison(self):
        v1 = parse_version_string("ECi F/W Ver. 10.3.52 (WR5SPLS1)")
        v2 = parse_version_string("ECi F/W Ver. 10.4.0 (WR5SPLS1)")
        v3 = parse_version_string("ECi F/W Ver. 11.0.0 (WR5SPLS1)")

        assert v1.firmware_version < v2.firmware_version
        assert v2.firmware_version < v3.firmware_version
        assert v3.firmware_version > v1.firmware_version
        assert v1.firmware_version <= v1.firmware_version
        assert v2.firmware_version >= v1.firmware_version

    def test_version_equality(self):
        v1 = parse_version_string("ECi F/W Ver. 10.3.52 (WR5SPLS1)")
        v2 = parse_version_string("ECi F/W Ver. 10.3.52 (W4RXPY2A)")

        assert v1.firmware_version == v2.firmware_version

    def test_version_inequality(self):
        v1 = parse_version_string("ECi F/W Ver. 10.3.52 (WR5SPLS1)")
        v2 = parse_version_string("ECi F/W Ver. 10.3.53 (WR5SPLS1)")

        assert v1.firmware_version != v2.firmware_version

    def test_alarm_message_parsing(self):
        msg = AlarmMessage.parse("A1")
        assert msg.message_type == "A"
        assert msg.number == 1

    def test_alarm_message_parsing_without_number(self):
        msg = AlarmMessage.parse("ARMED")
        assert msg.message_type == "ARMED"
        assert msg.number is None

    def test_alarm_message_is_type(self):
        msg = AlarmMessage.parse("A1")
        assert msg.is_type("A")
        assert not msg.is_type("B")

    def test_alarm_message_is_type_case_insensitive(self):
        msg = AlarmMessage.parse("armed")
        assert msg.is_type("ARMED")
        assert msg.is_type("armed")
        assert not msg.is_type("DISARMED")

    def test_toggle_event_init(self):
        toggle_event = ToggleEvent()
        assert toggle_event.is_clear()
        assert not toggle_event.is_set()

    def test_toggle_event_set(self):
        toggle_event = ToggleEvent()
        toggle_event.set()
        assert toggle_event.is_set()
        assert not toggle_event.is_clear()

    def test_toggle_event_clear(self):
        toggle_event = ToggleEvent()
        toggle_event.clear()
        assert toggle_event.is_clear()
        assert not toggle_event.is_set()

    async def test_toggle_event_wait_set(self):
        toggle_event = ToggleEvent()

        async def set_event_later():
            await asyncio.sleep(0.1)
            toggle_event.set()

        asyncio.create_task(set_event_later())
        await toggle_event.wait_set()
        assert toggle_event.is_set()

    async def test_toggle_event_wait_clear(self):
        toggle_event = ToggleEvent()
        toggle_event.set()

        async def clear_event_later():
            await asyncio.sleep(0.1)
            toggle_event.clear()

        asyncio.create_task(clear_event_later())
        await toggle_event.wait_clear()
        assert toggle_event.is_clear()

    async def test_split_complete_lines(self):
        from custom_components.eci_alarm.util import split_complete_lines

        data = "line1\nline2\npartial_line"
        lines = split_complete_lines(data, delimiter="\n")
        assert lines == ["line1", "line2"]

    async def test_split_complete_lines_no_complete(self):
        from custom_components.eci_alarm.util import split_complete_lines

        data = "partial_line"
        lines = split_complete_lines(data, delimiter="\r\n")
        assert lines == []

    async def test_split_complete_lines_different_delimiter(self):
        from custom_components.eci_alarm.util import split_complete_lines

        data = "line1\r\nline2\r\npartial_line"
        lines = split_complete_lines(data, delimiter="\r\n")
        assert lines == ["line1", "line2"]

    async def test_split_complete_lines_empty_string(self):
        from custom_components.eci_alarm.util import split_complete_lines

        data = ""
        lines = split_complete_lines(data, delimiter="\n")
        assert lines == []
