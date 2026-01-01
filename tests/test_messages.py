"""Tests for elitecloud_alarm.messages module."""

import pytest

from arrowhead_alarm.types import StatusFlags
from arrowhead_alarm.util import parse_status


@pytest.mark.parametrize(
    "message,expected_code",
    [
        ("ALM", "ALM"),
        ("XYZ", "XYZ"),
        ("A", "A"),
    ],
)
def test_parse_code_only(message: str, expected_code: str) -> None:
    status = parse_status(message)

    assert status.code == expected_code
    assert status.number is None
    assert status.timestamp is None
    assert status.user_number is None
    assert status.expander_code is None
    assert status.expander_number is None
    assert status.flags == StatusFlags.CODE


@pytest.mark.parametrize(
    "message,code,number",
    [
        ("ALM1", "ALM", 1),
        ("AA12", "AA", 12),
        ("ACP999", "ACP", 999),
    ],
)
def test_parse_numbered_code_valid(message: str, code: str, number: int) -> None:
    status = parse_status(message)

    assert status.code == code
    assert status.number == number
    assert status.flags == (StatusFlags.CODE | StatusFlags.NUMBER)


@pytest.mark.parametrize(
    "message,number,timestamp",
    [
        ("ALM1-123.0", 1, 123.0),
        ("ALM1 123.45", 1, 123.45),
        ("ACP999-0.5", 999, 0.5),
    ],
)
def test_parse_timestamp(message: str, number: int, timestamp: float) -> None:
    status = parse_status(message)

    assert status.number == number
    assert status.timestamp == timestamp
    assert status.flags & StatusFlags.TIMESTAMP


@pytest.mark.parametrize(
    "message,number,user_number",
    [
        ("ALM1-U1", 1, 1),
        ("ALM1 U99", 1, 99),
        ("AA12-U123", 12, 123),
    ],
)
def test_parse_user_number(message: str, number: int, user_number: int) -> None:
    status = parse_status(message)

    assert status.number == number
    assert status.user_number == user_number
    assert status.flags & StatusFlags.USER_NUMBER


@pytest.mark.parametrize(
    "message,ext_code,ext_number",
    [
        ("ALM EX1", "EX", 1),
        ("ACP999 IO12", "IO", 12),
        ("AA1 X9", "X", 9),
    ],
)
def test_parse_extender_status(message: str, ext_code: str, ext_number: int) -> None:
    status = parse_status(message)

    assert status.expander_code == ext_code
    assert status.expander_number == ext_number
    assert status.flags & StatusFlags.EXPANDER_CODE
    assert status.flags & StatusFlags.EXPANDER_NUMBER


def test_parse_full_combination() -> None:
    status = parse_status("ALM12-U7 EX3")

    assert status.code == "ALM"
    assert status.number == 12
    assert status.user_number == 7
    assert status.expander_code == "EX"
    assert status.expander_number == 3

    assert status.flags == (
        StatusFlags.CODE
        | StatusFlags.NUMBER
        | StatusFlags.USER_NUMBER
        | StatusFlags.EXPANDER_CODE
        | StatusFlags.EXPANDER_NUMBER
    )


def test_parse_number_timestamp_extender() -> None:
    status = parse_status("ACP5-10.5 IO2")

    assert status.number == 5
    assert status.timestamp == 10.5
    assert status.expander_code == "IO"
    assert status.expander_number == 2


@pytest.mark.parametrize(
    "message",
    [
        "",
        " ",
        "123",
        "ALM-",
        "ALM--1",
        "ALM U",
        "ALM1-U",
        "ALM1-UX",
        "ALM1-1.2.3",
        "ALM1 EX",
        "ALM1 EXX1",
        "ALM1 EX1 EXTRA",
        "ALM 1",
        "ALM1 U1 EX1 EXTRA",
    ],
)
def test_parse_invalid_formats(message: str) -> None:
    with pytest.raises(ValueError):
        parse_status(message)
