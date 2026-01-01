"""Types for Arrowhead alarm integration."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from functools import total_ordering
from typing import (
    Awaitable,
    Callable,
    Dict,
    Generic,
    Literal,
    TypeAlias,
    TypeVar,
    Union,
    override,
)


@dataclass
class Expander:
    """Expander state."""

    expander_id: int
    tamper_alarm_triggered: bool
    mains_fault: bool
    battery_fault: bool
    fuse_fault: bool


@dataclass
class UserPin:
    """User ID and PIN for arming/disarming."""

    user_id: int
    pin: int


@dataclass
class Login:
    """Login credentials for the alarm panel connection."""

    username: str
    password: str


class EciTransport(ABC):
    """Abstract base class for Arrowhead alarm panel transport."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection to the alarm panel."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the alarm panel."""
        ...

    @abstractmethod
    async def write(self, data: str) -> None:
        """Write string data to the connection.

        Args:
            data: String data to send.

        """
        ...

    @abstractmethod
    async def read(self, n: int) -> str:
        """Read string data from the connection.

        Args:
            n: Maximum number of bytes to read.

        Returns: Decoded string data read from the connection.

        """
        ...


class ArmingCapabilities(IntFlag):
    """Capabilities for arming the alarm panel."""

    NONE = 0
    INDIVIDUAL_AREA = 1 << 0
    USER_ID_AND_PIN = 1 << 1
    ONE_PUSH = 1 << 2


class DisarmingCapabilities(IntFlag):
    """Capabilities for disarming the alarm panel."""

    NONE = 0
    INDIVIDUAL_AREA_WITH_USER_PIN = 1 << 0
    USER_ID_AND_PIN = 1 << 1


@dataclass
class AlarmCapabilities:
    """Capabilities of the alarm panel."""

    all_zones_ready_status: bool = False
    arming: ArmingCapabilities = ArmingCapabilities.NONE
    disarming: DisarmingCapabilities = DisarmingCapabilities.NONE


@total_ordering
@dataclass(frozen=True)
class VersionInfo:
    """Version information."""

    major_version: int
    minor_version: int
    patch_version: int

    def _as_tuple(self) -> tuple[int, int, int]:
        return self.major_version, self.minor_version, self.patch_version

    def __lt__(self, other: "VersionInfo") -> bool:
        """Check if this VersionInfo is less than another.

        Args:
            other: The other VersionInfo instance to compare.

        Returns: True if this instance is less than the other, False otherwise.

        """
        return self._as_tuple() < other._as_tuple()

    def __gt__(self, other: "VersionInfo") -> bool:
        """Check if this VersionInfo is greater than another.

        Args:
            other: The other VersionInfo instance to compare.

        Returns: True if this instance is greater than the other, False otherwise.

        """
        return self._as_tuple() > other._as_tuple()

    def __le__(self, other: "VersionInfo") -> bool:
        """Check if this VersionInfo is less than or equal to another.

        Args:
            other: The other VersionInfo instance to compare.
        Returns: True if this instance is less than or \
        equal to the other, False otherwise.

        """
        return self._as_tuple() <= other._as_tuple()

    def __ge__(self, other: "VersionInfo") -> bool:
        """Check if this VersionInfo is greater than or equal to another.

        Args:
            other: The other VersionInfo instance to compare.

        Returns: True if this instance is greater than or \
        equal to the other, False otherwise.

        """
        return self._as_tuple() >= other._as_tuple()


@dataclass
class PanelVersion:
    """Panel version information."""

    model: str
    firmware_version: VersionInfo
    serial_number: str


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
    """Alarm Area status."""

    area_number: int
    state: AlarmState
    ready_to_arm: bool


@dataclass
class Zone:
    """Alarm Zone status."""

    zone_number: int
    supervise_alarm: bool
    trouble_alarm: bool
    bypassed: bool
    alarm: bool
    radio_battery_low: bool
    zone_closed: bool
    sensor_watch_alarm: bool


@dataclass
class Output:
    """Alarm Output status."""

    output_number: int
    on: bool


@dataclass
class PanelState:
    """Overall status of the alarm panel."""

    ready_to_arm: bool
    battery_fault: bool
    mains_fault: bool
    tamper_alarm_triggered: bool
    line_fault: bool
    dialer_fault: bool
    dialer_line_fault: bool
    fuse_fault: bool
    monitoring_station_active: bool
    dialer_active: bool
    code_tamper: bool
    receiver_fault: bool | None
    pendant_battery_fault: bool | None
    rf_battery_low: bool | None
    sensor_watch_alarm: bool | None
    zones: Dict[int, Zone]
    outputs: Dict[int, Output]
    areas: Dict[int, Area]
    zone_expanders: Dict[int, Expander]
    output_expanders: Dict[int, Expander]
    prox_expanders: Dict[int, Expander]


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


class StatusFlags(IntFlag):
    """Parts of a CombinedStatusCode message."""

    CODE = auto()
    NUMBER = auto()
    EXPANDER_CODE = auto()
    EXPANDER_NUMBER = auto()
    USER_NUMBER = auto()
    TIMESTAMP = auto()


STATUS_CODE = StatusFlags.CODE

NUMBERED_STATUS = STATUS_CODE | StatusFlags.NUMBER

EXPANDER_STATUS = STATUS_CODE | StatusFlags.EXPANDER_CODE | StatusFlags.EXPANDER_NUMBER

USER_STATUS = NUMBERED_STATUS | StatusFlags.USER_NUMBER

TIMESTAMPED_STATUS = NUMBERED_STATUS | StatusFlags.TIMESTAMP


@dataclass
class Status:
    """Status message from panel."""

    code: str
    number: int | None = None
    expander_code: str | None = None
    expander_number: int | None = None
    user_number: int | None = None
    timestamp: float | None = None

    @property
    def flags(self) -> StatusFlags:
        """Determine the StatusFlags for this Status instance.

        Returns: The combined StatusFlags representing the fields present.

        """
        flags = StatusFlags.CODE
        if self.number is not None:
            flags |= StatusFlags.NUMBER
        if self.expander_code is not None:
            flags |= StatusFlags.EXPANDER_CODE
        if self.expander_number is not None:
            flags |= StatusFlags.EXPANDER_NUMBER
        if self.user_number is not None:
            flags |= StatusFlags.USER_NUMBER
        if self.timestamp is not None:
            flags |= StatusFlags.TIMESTAMP
        return flags


class ToggleEvent:
    """An asyncio-compatible event that can be set or cleared."""

    def __init__(self) -> None:
        """Initialize the ToggleEvent."""
        self._set_event = asyncio.Event()
        self._clear_event = asyncio.Event()
        self._clear_event.set()

    def is_set(self) -> bool:
        """Check if the event is set.

        Returns: True if the event is set, False otherwise.

        """
        return bool(self._set_event.is_set())

    def is_clear(self) -> bool:
        """Check if the event is clear.

        Returns: True if the event is clear, False otherwise.

        """
        return bool(self._clear_event.is_set())

    def set(self) -> None:
        """Set the event."""
        self._set_event.set()
        self._clear_event.clear()

    def clear(self) -> None:
        """Clear the event."""
        self._set_event.clear()
        self._clear_event.set()

    async def wait_until_set(self) -> None:
        """Wait until the event is set."""
        await self._set_event.wait()

    async def wait_until_clear(self) -> None:
        """Wait until the event is clear."""
        await self._clear_event.wait()


In = TypeVar("In")
Out = TypeVar("Out")

T = TypeVar("T")
F = TypeVar("F")


class FlowResult(Generic[T], ABC):
    """Represents the result of a flow operation."""

    @abstractmethod
    def bind(self, processor: Callable[[T], "FlowResult[Out]"]) -> "FlowResult[Out]":
        """Process the FlowResult with the given processor function.

        Args:
            processor: A function that takes a value of type T and returns a \
            FlowResult of type Out.

        Returns: A FlowResult of type Out after processing.

        """
        ...


Transformer: TypeAlias = Callable[[In], FlowResult[Out]]

Consumer: TypeAlias = Callable[[In | Exception], None]


@dataclass(frozen=True)
class Go(FlowResult[T]):
    """Indicates that the flow should proceed with the given value."""

    value: T

    @override
    def bind(self, processor: Callable[[T], FlowResult[Out]]) -> FlowResult[Out]:
        return processor(self.value)


@dataclass(frozen=True)
class Wait(FlowResult[T]):
    """Indicates that the flow should wait for an external event."""

    @override
    def bind(self, processor: Callable[[T], FlowResult[Out]]) -> FlowResult[Out]:
        return Wait()


@dataclass(frozen=True)
class Reject(FlowResult[T]):
    """Indicates that the flow should be restarted."""

    @override
    def bind(self, processor: Callable[[T], FlowResult[Out]]) -> FlowResult[Out]:
        return Reject()


@dataclass(frozen=True)
class Error(FlowResult[T]):
    """Represents an error in the flow."""

    error: Exception

    @override
    def bind(self, processor: Callable[[T], FlowResult[Out]]) -> FlowResult[Out]:
        return Error(self.error)


@dataclass(frozen=True)
class Success(Generic[T]):
    """Represents a successful outcome."""

    value: T
    ok: Literal[True] = True


@dataclass(frozen=True)
class Fail(Generic[F]):
    """Represents a failed outcome."""

    error: F
    is_success: Literal[False] = False


Param = TypeVar("Param")


Outcome: TypeAlias = Union[Success[T], Fail[Exception]]


@dataclass
class Request(Generic[T]):
    """Represents a request with data, response callback, and awaitable result."""

    data: str
    response_callback: Consumer[str]
    awaitable: Awaitable[T]
