"""Client for Arrowhead alarm systems."""

import asyncio
import logging
from typing import Callable, Dict

from .commands import (
    arm_area_command,
    arm_no_pin_command,
    arm_user_command,
    disarm_user_command,
    get_output_state_command,
    mode_command,
    set_output_state_command,
    set_zone_bypass_command,
    status_command,
    version_command,
)
from .const import (
    DEFAULT_MAX_AREAS,
    DEFAULT_MAX_OUTPUTS,
    DEFAULT_MAX_ZONES,
    OUTPUT_EXPANDER_COUNT,
    PROX_EXPANDER_COUNT,
    ZONE_EXPANDER_COUNT,
)
from .consumers import panel_state_consumer
from .session import EciSession
from .types import (
    AlarmState,
    Area,
    ArmingMode,
    EciTransport,
    Expander,
    Fail,
    Login,
    Output,
    PanelState,
    PanelVersion,
    ProtocolMode,
    Success,
    UserPin,
    Zone,
)
from .util import get_mode_capabilites, is_mode_4_supported

_LOGGER = logging.getLogger(__name__)


class EciClient:
    """Client for Arrowhead alarm systems over IP."""

    def __init__(
        self, transport: EciTransport, credentials: Login | None = None
    ) -> None:
        """Initialize the Arrowhead alarm client.

        Args:
            transport: Transport layer for communication
            credentials: Optional serial credentials for authentication

        """
        self._session: EciSession = EciSession(
            transport=transport,
            credentials=credentials,
        )
        self._subscribers: list[Callable[[PanelState], None]] = []
        self._subscribers_lock = asyncio.Lock()

        self._state: PanelState = self._default_panel_state()

        self.last_update = None
        self.delimiter = "\r\n"
        self.panel_version: PanelVersion | None = None

        self.status_worker_task: asyncio.Task[None] | None = None

    def state(self) -> PanelState:
        """Return current panel status."""
        return self._state

    def generate_default_zones(self) -> Dict[int, Zone]:
        """Generate default zones based on default constants."""
        return {
            i: Zone(
                zone_number=i,
                supervise_alarm=False,
                bypassed=False,
                trouble_alarm=False,
                alarm=False,
                radio_battery_low=False,
                zone_closed=True,
                sensor_watch_alarm=False,
            )
            for i in range(1, DEFAULT_MAX_ZONES + 1)
        }

    def generate_default_areas(self) -> Dict[int, Area]:
        """Generate default areas based on default constants."""
        return {
            i: Area(area_number=i, state=AlarmState.DISARMED, ready_to_arm=True)
            for i in range(1, DEFAULT_MAX_AREAS + 1)
        }

    def generate_expanders(self, count: int) -> Dict[int, Expander]:
        """Generate default expanders based on default constants."""
        return {
            i: Expander(
                expander_id=i,
                tamper_alarm_triggered=False,
                mains_fault=False,
                battery_fault=False,
                fuse_fault=False,
            )
            for i in range(1, count + 1)
        }

    def generate_default_outputs(self) -> Dict[int, Output]:
        """Generate default outputs based on default constants."""
        return {
            i: Output(output_number=i, on=False)
            for i in range(1, DEFAULT_MAX_OUTPUTS + 1)
        }

    def _default_panel_state(self) -> PanelState:
        return PanelState(
            ready_to_arm=False,
            battery_fault=False,
            mains_fault=False,
            tamper_alarm_triggered=False,
            line_fault=False,
            dialer_fault=False,
            dialer_line_fault=False,
            fuse_fault=False,
            monitoring_station_active=False,
            dialer_active=False,
            code_tamper=False,
            receiver_fault=None,
            pendant_battery_fault=None,
            rf_battery_low=None,
            sensor_watch_alarm=None,
            zones=self.generate_default_zones(),
            outputs=self.generate_default_outputs(),
            areas=self.generate_default_areas(),
            zone_expanders=self.generate_expanders(ZONE_EXPANDER_COUNT),
            output_expanders=self.generate_expanders(OUTPUT_EXPANDER_COUNT),
            prox_expanders=self.generate_expanders(PROX_EXPANDER_COUNT),
        )

    async def connect(self) -> None:
        """Connect to the panel."""
        await self._session.connect()
        await self._set_mode(ProtocolMode.MODE_1)
        version = await self.query_panel_version()
        if version:
            self.panel_version = version
            _LOGGER.info("Connected to panel version: %s", version)

    async def disconnect(self) -> None:
        """Disconnect from the panel."""
        await self._session.disconnect()

    @property
    def is_connected(self) -> bool:
        """Return True if connected and authenticated."""
        return self._session.connected()

    async def _status_worker(self) -> None:
        listener, queue = panel_state_consumer(self.delimiter)
        async with await self._session.read_context(listener):
            while True:
                status = await queue.get()
                match status:
                    case Success(value=operation):
                        operation(self._state)
                    case Fail(error):
                        _LOGGER.error("Error parsing status message: %s", error)
                self.last_update = asyncio.get_event_loop().time()
                await self._emit_change(self._state)

    async def on_change(self, callback: Callable[[PanelState], None]) -> None:
        """Subscribe to panel state changes."""
        async with self._subscribers_lock:
            self._subscribers.append(callback)

    async def _emit_change(self, state: PanelState) -> None:
        async with self._subscribers_lock:
            subs = list(self._subscribers)

        for subscriber in subs:
            try:
                subscriber(state)
            except Exception as err:
                _LOGGER.error("Error in change subscriber: %s", err)

    async def query_panel_version(self) -> PanelVersion:
        """Query the panel for its firmware version."""
        try:
            _LOGGER.info("Querying panel version")
            req = version_command(self.delimiter)
            return await self._session.request(req)
        except Exception as err:
            _LOGGER.error("Error querying panel version: %s", err)
            raise

    async def arm_no_pin(self, mode: ArmingMode) -> None:
        """Arm the alarm in away mode."""
        _LOGGER.info("Attempting to arm in %s mode without PIN", mode.name)
        try:
            req = arm_no_pin_command(mode, self.delimiter)
            await self._session.request(req)
        except RuntimeError as err:
            _LOGGER.warning("Panel returned error for %s: %s", mode.name, err)
            raise
        except Exception as err:
            _LOGGER.error("Error sending %s command: %s", mode.name, err)
            raise

    async def arm_user(self, user: UserPin, mode: ArmingMode) -> None:
        """Arm the alarm in away mode using specific user credentials."""
        _LOGGER.info(
            "Attempting to arm in away mode using user code: %s, pin: %s",
            user.user_id,
            user.pin,
        )
        if self.mode != ProtocolMode.MODE_1:
            _LOGGER.error(
                "Protocol mode %d does not support user commands",
                self.mode,
            )
            return
        try:
            req = arm_user_command(user.user_id, user.pin, mode, self.delimiter)
            await self._session.request(req)
        except RuntimeError as err:
            _LOGGER.warning("Panel returned error for ARMAWAY: %s", err)
        except Exception as err:
            _LOGGER.error("Error sending ARMAWAY command: %s", err)

    async def arm_area(self, area_number: int, mode: ArmingMode) -> None:
        """Arm a specific area in away mode.

        Args:
            area_number: Area number to arm.
            mode: Arming mode to use.

        """
        _LOGGER.info("Attempting to arm in away mode for area %d", area_number)
        if self.mode != ProtocolMode.MODE_4:
            _LOGGER.error(
                "protocol mode %d does not support area commands",
                area_number,
                self.mode,
            )
            return
        try:
            req = arm_area_command(area_number, mode, self.delimiter)
            await self._session.request(req)
        except Exception as err:
            _LOGGER.error(
                "Error sending ARMAWAY command for area %d: %s", area_number, err
            )

    async def disarm(self, user: UserPin) -> None:
        """Disarm the alarm using specific user credentials.

        Args:
            user:  UserPin object with user ID and PIN.

        """
        _LOGGER.info(
            "Attempting to disarm using user code: %s, pin: %s", user.user_id, user.pin
        )
        try:
            _LOGGER.debug("Trying DISARM command with user credentials")
            req = disarm_user_command(user.user_id, user.pin, self.delimiter)
            response = await self._session.request(req)
            _LOGGER.debug("DISARM command response: %r", response)
        except RuntimeError as err:
            _LOGGER.warning("Panel returned error for DISARM: %s", err)
            raise
        except Exception as err:
            _LOGGER.error("Error sending DISARM command: %s", err)
            raise

    async def set_zone_bypass(self, zone_number: int, bypass: bool) -> None:
        """Bypass a zone.

        Args:
            zone_number: Zone number to bypass.
            bypass: True to bypass, False to unbypass.

        """
        if zone_number not in self._state.zones:
            _LOGGER.warning("Zone number %d is not valid for this panel", zone_number)
            raise ValueError("Invalid zone number %d", zone_number)
        try:
            _LOGGER.debug("Sending BYPASS command for zone %d", zone_number)
            req = set_zone_bypass_command(zone_number, bypass, self.delimiter)
            resp = await self._session.request(req)
            _LOGGER.debug("BYPASS command response: %r", resp)
            self._state.zones[zone_number].bypassed = True
        except Exception as err:
            _LOGGER.error("Error bypassing zone %d: %s", zone_number, err)
            raise

    async def set_output_state(self, output_number: int, on: bool) -> None:
        """Turn output on permanently."""
        _LOGGER.info("Turning on output %d", output_number)
        if output_number > len(self._state.outputs):
            _LOGGER.warning(
                "Output number %d exceeds max outputs %d",
                output_number,
                len(self._state.outputs),
            )
        try:
            req = set_output_state_command(output_number, on, self.delimiter)
            resp = await self._session.request(req)
            _LOGGER.debug("OUTPUTON command response: %r", resp)
            self._state.outputs[output_number].on = True
        except Exception as err:
            _LOGGER.error("Error turning on output %d: %s", output_number, err)
            raise

    async def get_output_state(self, output_number: int) -> bool:
        """Get the current state of an output."""
        _LOGGER.info("Getting state for output %d", output_number)
        if output_number > len(self._state.outputs):
            _LOGGER.warning(
                "Output number %d exceeds max outputs %d",
                output_number,
                len(self._state.outputs),
            )
        try:
            req = get_output_state_command(output_number, self.delimiter)
            resp = await self._session.request(req)
            _LOGGER.debug("OUTPUTSTATE command response: %r", resp)
            self._state.outputs[output_number].on = resp
            return resp
        except Exception as err:
            _LOGGER.error("Error getting state for output %d: %s", output_number, err)
            raise

    async def _auto_set_mode(self) -> None:
        """Automatically set the best protocol mode based on panel capabilities."""
        if self.panel_version is None:
            _LOGGER.error("Cannot set protocol mode: panel version unknown")
            raise RuntimeError("Panel version unknown")
        if is_mode_4_supported(self.panel_version.firmware_version):
            _LOGGER.info("Panel supports Mode 4, setting protocol mode to 4")
            return await self._set_mode(ProtocolMode.MODE_4)
        else:
            _LOGGER.info("Panel does not support Mode 4, setting protocol mode to 2")
            return await self._set_mode(ProtocolMode.MODE_2)

    async def _restart_status_worker(self) -> None:
        """Restart the status worker task."""
        if self.status_worker_task:
            self.status_worker_task.cancel()
            try:
                await self.status_worker_task
            except asyncio.CancelledError:
                pass
        self.status_worker_task = asyncio.create_task(self._status_worker())

    async def _set_mode(self, mode: ProtocolMode) -> None:
        """Set the protocol mode of the panel."""
        _LOGGER.info("Setting protocol mode to %d", mode.value)
        try:
            command = mode_command(mode)
            delimiter = await self._session.request(command, timeout=5.0)
            self.mode = mode
            self.delimiter = delimiter
            self.capabilities = get_mode_capabilites(mode)
            await self._restart_status_worker()

        except Exception as err:
            _LOGGER.error("Error setting protocol mode to %d: %s", mode, err)
            raise

    async def request_state(self) -> PanelState:
        """Request the current panel state.

        Returns:
            PanelState: Current state of the panel.

        """
        _LOGGER.info("Getting current panel state")
        if not self.is_connected:
            _LOGGER.error("Cannot get state: not connected to panel")
            raise ConnectionError("Not connected to panel")
        try:
            cmd = status_command(self.delimiter)
            ops = await self._session.request(cmd)
            for op in ops:
                op(self._state)
            await self._emit_change(self._state)
        except Exception as err:
            _LOGGER.error("Error requesting state from panel: %s", err)
            raise
        return self.state()
