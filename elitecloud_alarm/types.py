"""Types for EliteCloud Alarm integration."""
import asyncio
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import (
    Awaitable,
    Callable,
    Dict,
    Generic,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
)


@dataclass
class AlarmUser:
    user_id: int
    pin: int


@dataclass
class SerialCredentials:
    username: str
    password: str


class EciTransport(ABC):
    async def connect(self) -> None:
        raise NotImplementedError
    async def disconnect(self) -> None:
        raise NotImplementedError
    async def write(self, data: str) -> None:
        raise NotImplementedError
    async def read(self) -> str:
        raise NotImplementedError


@dataclass
class VersionInfo:
    """Version information for the alarm panel firmware."""

    major_version: int
    minor_version: int
    patch_version: int

    def __gt__(self, other: "VersionInfo") -> bool:
        """Determine if this version is greater than another version.

        Args:
            other: The other VersionInfo to compare against.

        Returns: True if this version is greater than the other version, False otherwise

        """
        if self.major_version != other.major_version:
            return self.major_version > other.major_version
        if self.minor_version != other.minor_version:
            return self.minor_version > other.minor_version
        return self.patch_version > other.patch_version

    def __ge__(self, other: "VersionInfo") -> bool:
        """Determine if this version is greater than or equal to another version.

        Args:
            other: The other VersionInfo to compare against.

        Returns:
            True if this version is greater than or equal to the other version,
            False otherwise

        """
        return self > other or self == other

    def __eq__(self, other: object) -> bool:
        """Args:
            other:

        Returns:

        """
        if not isinstance(other, VersionInfo):
            return NotImplemented
        return (
            self.major_version == other.major_version
            and self.minor_version == other.minor_version
            and self.patch_version == other.patch_version
        )

    def __lt__(self, other: "VersionInfo") -> bool:
        """Args:
            other:

        Returns:

        """
        return not self >= other

    def __le__(self, other: "VersionInfo") -> bool:
        """Args:
            other:

        Returns:

        """
        return not self > other

    def __repr__(self) -> str:
        """Returns:"""
        return f"{self.major_version}.{self.minor_version}.{self.patch_version}"


@dataclass
class PanelVersion:
    model: str
    firmware_version: VersionInfo
    serial_number: str


@dataclass
class AlarmMessage:
    message_type: str
    number: int | None

    def is_type(self, msg_type: str) -> bool:
        return self.message_type.lower() == msg_type.lower()

    @staticmethod
    def parse(message: str) -> "AlarmMessage":
        first_digit = next(
            (index for index, char in enumerate(message) if char.isdigit()),
            len(message),
        )
        message_type = message[:first_digit]
        number_part = message[first_digit:]
        number = int(number_part) if number_part.isdigit() else None
        return AlarmMessage(message_type=message_type, number=number)


class ConnectionState(Enum):
    """Connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class AlarmState(Enum):
    """Alarm states."""

    DISARMED = "disarmed"
    ARMED_AWAY = "armed_away"
    ARMED_STAY = "armed_stay"
    ARMING_AWAY = "arming_away"
    ARMING_STAY = "arming_stay"
    ALARM_TRIGGERED = "alarm_triggered"


@dataclass
class Area:
    state: AlarmState = AlarmState.DISARMED
    ready_to_arm: bool = True


@dataclass
class Zone:
    supervise_alarm: bool = False
    trouble_alarm: bool = False
    bypassed: bool = False
    alarm: bool = False
    radio_battery_low: bool = False
    zone_closed: bool = True
    sensor_watch_alarm: bool = False


@dataclass
class Output:
    state = False


class ProtocolMode(Enum):
    """Protocol modes."""

    MODE_1 = 1  # Default, no acknowledgments
    MODE_2 = 2  # AAP mode, with acknowledgments
    MODE_3 = 3  # Permaconn mode, with acknowledgments
    MODE_4 = 4  # Home Automation mode, no acknowledgments (ECi FW 10.3.50+)


class ArmingMode(Enum):
    """Arming modes."""

    AWAY = "away"
    STAY = "stay"


class PanelStatus(TypedDict):
    battery_ok: bool
    mains_ok: bool
    tamper_alarm: bool
    line_ok: bool
    dialer_ok: bool
    fuse_ok: bool
    dialer_active: bool
    code_tamper: bool
    receiver_ok: bool | None
    pendant_battery_ok: bool | None
    rf_battery_low: bool | None
    sensor_watch_alarm: bool | None
    zones: Dict[int, Zone]
    outputs: Dict[int, Output]
    areas: Dict[int, Area]


class ToggleEvent:
    def __init__(self):
        self._set_event = asyncio.Event()
        self._clear_event = asyncio.Event()
        self._clear_event.set()

    def is_set(self) -> bool:
        return bool(self._set_event.is_set())

    def is_clear(self) -> bool:
        return bool(self._clear_event.is_set())

    def set(self) -> None:
        self._set_event.set()
        self._clear_event.clear()

    def clear(self) -> None:
        self._set_event.clear()
        self._clear_event.set()

    async def wait_set(self) -> None:
        await self._set_event.wait()

    async def wait_clear(self) -> None:
        await self._clear_event.wait()


In = TypeVar("In")
Out = TypeVar("Out")

T = TypeVar("T")
F = TypeVar("F")


class FlowResult(Generic[T]):
    def bind(self, processor: Callable[[T], "FlowResult[Out]"]) -> "FlowResult[Out]":
        match self:
            case Go(value):
                return processor(value)
            case Wait():
                return Wait()
            case Restart():
                return Restart()
            case Error(e):
                return Error(e)
            case _:
                raise NotImplementedError("Unknown FlowResult type")


Processor: TypeAlias = Callable[[In], FlowResult[Out]]

Listener: TypeAlias = Callable[[In | Exception], None]


@dataclass(frozen=True)
class Go(FlowResult[T]):
    value: T


@dataclass(frozen=True)
class Wait(FlowResult[T]):
    pass


@dataclass(frozen=True)
class Restart(FlowResult[T]):
    pass


@dataclass(frozen=True)
class Error(FlowResult[T]):
    error: Exception


@dataclass(frozen=True)
class Success(Generic[T]):
    """Represents a successful result."""

    value: T


@dataclass(frozen=True)
class Fail(Generic[F]):
    """Represents a failed result."""

    error: F


Param = TypeVar("Param")


Result: TypeAlias = Union[Success[T], Fail[Exception]]


@dataclass
class Request(Generic[T]):
    data: str
    callback: Listener[str]
    awaitable: Awaitable[T]
