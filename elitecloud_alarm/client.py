"""Client for ECi alarm systems."""

import asyncio
import logging
from dataclasses import dataclass
from enum import IntFlag
from typing import Any, Awaitable, Callable, Coroutine, Dict

from .commands import (
    arm_area_command,
    arm_no_pin_command,
    arm_user_command,
    mode_command,
    status_command,
    version_command,
)
from .const import (
    DEFAULT_MAX_AREAS,
    DEFAULT_MAX_OUTPUTS,
    DEFAULT_MAX_ZONES,
    DEFAULT_VIRTUAL_KEYPAD_NUM,
)
from .session import EciSession
from .types import (
    AlarmMessage,
    AlarmUser,
    Area,
    ArmingMode,
    EciTransport,
    Output,
    PanelStatus,
    PanelVersion,
    ProtocolMode,
    SerialCredentials,
    Zone,
)
from .util import is_mode_4_supported

_LOGGER = logging.getLogger(__name__)


class _ArmingCapabilities(IntFlag):
    NONE = 0
    INDIVIDUAL_AREA = 1 << 0
    USER_ID_AND_PIN = 1 << 1
    ONE_PUSH = 1 << 2


class _DisarmingCapabilities(IntFlag):
    NONE = 0
    INDIVIDUAL_AREA_WITH_USER_PIN = 1 << 0
    USER_ID_AND_PIN = 1 << 1


@dataclass
class _AlarmCapabilities:
    all_zones_ready_status: bool = False
    arming: _ArmingCapabilities = _ArmingCapabilities.NONE
    disarming: _DisarmingCapabilities = _DisarmingCapabilities.NONE


def _capabilities_from_mode(mode: ProtocolMode) -> _AlarmCapabilities:
    capabilities = _AlarmCapabilities()
    match mode:
        case ProtocolMode.MODE_1:
            capabilities.all_zones_ready_status = True
            capabilities.arming = (
                _ArmingCapabilities.USER_ID_AND_PIN | _ArmingCapabilities.ONE_PUSH
            )
            capabilities.disarming = _DisarmingCapabilities.USER_ID_AND_PIN
        case ProtocolMode.MODE_2:
            capabilities.all_zones_ready_status = False
            capabilities.arming = _ArmingCapabilities.INDIVIDUAL_AREA
            capabilities.disarming = (
                _DisarmingCapabilities.INDIVIDUAL_AREA_WITH_USER_PIN
            )
        case ProtocolMode.MODE_4:
            capabilities.all_zones_ready_status = False
            capabilities.arming = (
                _ArmingCapabilities.INDIVIDUAL_AREA
                | _ArmingCapabilities.USER_ID_AND_PIN
            )
            capabilities.disarming = _DisarmingCapabilities.USER_ID_AND_PIN
        case _:
            raise NotImplementedError
    return capabilities


class EciClient:
    """Client for ECi alarm systems over IP."""

    def __init__(
        self, transport: EciTransport, credentials: SerialCredentials | None = None
    ) -> None:
        """Initialize the Eci alarm client.

        Args:
            transport: Transport layer for communication
            credentials: Optional serial credentials for authentication

        """
        self._session = EciSession(
            transport=transport,
            credentials=credentials,
        )
        self._change_subscribers: list[
            Callable[[PanelStatus], None]
            | Callable[[PanelStatus], Coroutine[Any, Any, None]]
        ] = []

        # Initialize panel status
        self.max_zones: int = DEFAULT_MAX_ZONES
        self.max_outputs: int = DEFAULT_MAX_OUTPUTS
        self.max_areas: int = DEFAULT_MAX_AREAS
        self.virtual_keypad_number = DEFAULT_VIRTUAL_KEYPAD_NUM

        # Version information
        self.panel_version: PanelVersion | None = None
        self.supports_rf = False
        self.mode: ProtocolMode | None = None
        self.capabilities: _AlarmCapabilities | None = None

        # Zone states
        self.zones: Dict[int, Zone] = {i: Zone() for i in range(1, self.max_zones + 1)}
        self.outputs: Dict[int, Output] = {
            i: Output() for i in range(1, self.max_outputs + 1)
        }
        self.areas: Dict[int, Area] = {i: Area() for i in range(1, self.max_areas + 1)}

        # System states
        self.battery_ok = True
        self.mains_ok = True
        self.tamper_alarm = False
        self.line_ok = True
        self.dialer_ok = True
        self.fuse_ok = True
        self.dialer_active = False
        self.code_tamper = False
        self.receiver_ok = True if self.supports_rf else None
        self.pendant_battery_ok = True if self.supports_rf else None
        self.rf_battery_low = False if self.supports_rf else None
        self.sensor_watch_alarm = False if self.supports_rf else None

        self.last_update = None
        self.delimiter = "\n"

    def status(self) -> PanelStatus:
        """Return current panel status."""
        return PanelStatus(
            battery_ok=self.battery_ok,
            mains_ok=self.mains_ok,
            tamper_alarm=self.tamper_alarm,
            line_ok=self.line_ok,
            dialer_ok=self.dialer_ok,
            fuse_ok=self.fuse_ok,
            dialer_active=self.dialer_active,
            code_tamper=self.code_tamper,
            receiver_ok=self.receiver_ok,
            pendant_battery_ok=self.pendant_battery_ok,
            rf_battery_low=self.rf_battery_low,
            sensor_watch_alarm=self.sensor_watch_alarm,
            zones=self.zones,
            outputs=self.outputs,
            areas=self.areas,
        )

    async def connect(self) -> None:
        """Connect to the panel."""
        await self._session.connect()
        version = await self._query_panel_version()
        if version:
            self.panel_version = version
            _LOGGER.info("Connected to panel version: %s", version)
        await self._auto_set_mode()

    async def disconnect(self) -> None:
        """Disconnect from the panel."""
        await self._session.disconnect()

    @property
    def is_connected(self) -> bool:
        """Return True if connected and authenticated."""
        return self._session.connected()

    def on_change(
        self,
        callback: Callable[[PanelStatus], None]
        | Callable[[PanelStatus], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to panel status changes."""
        self._change_subscribers.append(callback)

    def _emit_change(self, status: PanelStatus) -> None:
        for subscriber in self._change_subscribers:
            result = subscriber(status)
            if isinstance(result, Awaitable):
                asyncio.create_task(result)

    def _process_message(self, message: str) -> None:
        """Process incoming messages with protocol-aware parsing."""
        _LOGGER.debug("Processing message: %s", message)
        alarm_msg = AlarmMessage.parse(message)
        handlers: list[Callable[[AlarmMessage], bool]] = [
            self._process_system_message,
            self._process_rf_message,
            self._process_area_message,
            self._process_zone_message,
            self._process_output_message,
        ]
        try:
            for handler in handlers:
                if not handler(alarm_msg):
                    continue
                _LOGGER.debug("Message processed by %s", handler.__name__)
                self._emit_change(self.status())
                return
            _LOGGER.warning("Unhandled message type: %s", message)
        except Exception as err:
            _LOGGER.error("Error processing message '%s': %s", message, err)

    def _process_system_message(self, message: AlarmMessage) -> bool:
        """Process system status messages."""
        match message.message_type:
            case "RO":
                self.ready_to_arm = True
            case "NR":
                self.ready_to_arm = False
            case "MF":
                self.mains_ok = False
            case "MR":
                self.mains_ok = True
            case "BF":
                self.battery_ok = False
            case "BR":
                self.battery_ok = True
            case "TA":
                self.tamper_alarm = True
            case "TR":
                self.tamper_alarm = False
            case "LF":
                self.line_ok = False
            case "LR":
                self.line_ok = True
            case "DF":
                self.dialer_ok = False
            case "DR":
                self.dialer_ok = True
            case "FF":
                self.fuse_ok = False
            case "FR":
                self.fuse_ok = True
            case "CAL":
                self.dialer_active = True
            case "CLF":
                self.dialer_active = False
            case _:
                return False
        return True

    def _process_rf_message(self, message: AlarmMessage) -> bool:
        """Process RF-related messages."""
        if not self.supports_rf:
            return False

        match message.message_type:
            case "RIF":
                self.receiver_ok = False
            case "RIR":
                self.receiver_ok = True
            case "ZBL":
                self.rf_battery_low = True
            case "ZBR":
                self.rf_battery_low = False
            case "ZIA":
                self.sensor_watch_alarm = True
            case "ZIR":
                self.sensor_watch_alarm = False
            case _:
                return False
        return True

    def _process_area_message(self, message: AlarmMessage) -> bool:
        """Process area-related messages."""
        area_num = message.number
        if not area_num:
            return False

        match message.message_type:
            case "A":
                self.armed = True
                self.arming = False
                if area_num == 1:
                    self.area_a_armed = True
                elif area_num == 2:
                    self.area_b_armed = True
            case "EA":
                self.arming = True
            case "ES":
                self.arming = True
            case "S":
                self.armed = True
                self.arming = False
                self.stay_mode = True
                if area_num == 1:
                    self.area_a_armed = True
                elif area_num == 2:
                    self.area_b_armed = True
            case "D":
                if area_num == 1:
                    self.area_a_armed = False
                elif area_num == 2:
                    self.area_b_armed = False
                if not self.area_a_armed and not self.area_b_armed:
                    self.armed = False
            case _:
                return False
        return True

    def _process_zone_message(self, message: AlarmMessage) -> bool:
        """Process zone-related messages."""
        zone_num = message.number
        if zone_num is None:
            return False

        if zone_num not in self.zones:
            return False

        match message.message_type:
            case "ZO":
                self.zones[zone_num].zone_closed = False
            case "ZC":
                self.zones[zone_num].zone_closed = True
            case "ZA":
                self.zones[zone_num].alarm = True
                self.alarm = True
            case "ZR":
                self.zones[zone_num].alarm = False
                self.alarm = any(self.zones[z].alarm for z in self.zones)
            case "ZT":
                self.zones[zone_num].trouble_alarm = True
            case "ZTR":
                self.zones[zone_num].trouble_alarm = False
            case "ZBY":
                self.zones[zone_num].bypassed = True
            case "ZBYR":
                self.zones[zone_num].bypassed = False
            case "ZSA" if self.supports_rf:
                self.zone_supervise_fail = True
            case "ZSR" if self.supports_rf:
                self.zone_supervise_fail = False
            case _:
                return False
        return True

    def _process_output_message(self, message: AlarmMessage) -> bool:
        """Process output-related messages."""
        output_num = message.number
        if output_num is None:
            return False

        if output_num not in self.outputs:
            return False

        match message.message_type:
            case "OO":
                self.outputs[output_num].state = True
            case "OR":
                self.outputs[output_num].state = False
            case _:
                return False
        return True

    async def _query_panel_version(self) -> PanelVersion:
        """Query the panel for its firmware version."""
        try:
            _LOGGER.info("Querying panel version")
            req = version_command("\r\n")
            return await self._session.request(req)
        except Exception as err:
            _LOGGER.error("Error querying panel version: %s", err)
            raise

    async def arm_no_pin(self, mode: ArmingMode) -> None:
        """Arm the alarm in away mode."""
        _LOGGER.info("Attempting to arm in %s mode without PIN", mode.name)
        try:
            req = arm_no_pin_command(mode, "\r\n")
            await self._session.request(req)
        except RuntimeError as err:
            _LOGGER.warning("Panel returned error for %s: %s", mode.name, err)
            raise
        except Exception as err:
            _LOGGER.error("Error sending %s command: %s", mode.name, err)
            raise

    async def arm_user(self, user: AlarmUser, mode: ArmingMode) -> None:
        """Arm the alarm in away mode using specific user credentials."""
        _LOGGER.info(
            "Attempting to arm in away mode using user code: %s, pin: %s",
            user.user_id,
            user.pin,
        )
        if self.mode != ProtocolMode.MODE_1:
            _LOGGER.error(
                "Cannot arm away with user credentials: protocol mode %d does not support user commands",
                self.mode,
            )
            return
        try:
            req = arm_user_command(user.user_id, user.pin, mode, "\r\n")
            await self._session.request(req)
        except RuntimeError as err:
            _LOGGER.warning("Panel returned error for ARMAWAY: %s", err)
        except Exception as err:
            _LOGGER.error("Error sending ARMAWAY command: %s", err)

    async def arm_area(self, area_number: int, mode: ArmingMode) -> None:
        """Arm the alarm in away mode for a specific area."""
        _LOGGER.info("Attempting to arm in away mode for area %d", area_number)
        if self.mode != ProtocolMode.MODE_4:
            _LOGGER.error(
                "Cannot arm away for area %d: protocol mode %d does not support area commands",
                area_number,
                self.mode,
            )
            return
        try:
            req = arm_area_command(area_number, mode, "\r\n")
            await self._session.request(req)
        except Exception as err:
            _LOGGER.error(
                "Error sending ARMAWAY command for area %d: %s", area_number, err
            )

    async def disarm(self, user: AlarmUser):
        """Disarm the alarm using specific user credentials."""
        _LOGGER.info(
            "Attempting to disarm using user code: %s, pin: %s", user.user_id, user.pin
        )
        try:
            _LOGGER.debug("Trying DISARM command with user credentials")
            response = await self._send_command(f"DISARM {user.user_id} {user.pin}")
            _LOGGER.debug("DISARM command response: %r", response)
        except RuntimeError as err:
            _LOGGER.warning("Panel returned error for DISARM: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Error sending DISARM command: %s", err)
            return False

    async def bypass_zone(self, zone_number: int):
        """Bypass a zone."""
        try:
            _LOGGER.info("Sending bypass command for zone %d", zone_number)
            if zone_number not in self.zones:
                _LOGGER.warning(
                    "Zone number %d is not valid for this panel", zone_number
                )
                return False
            _LOGGER.debug("Sending BYPASS command for zone %d", zone_number)
            resp = await self._send_command(f"BYPASS {zone_number}")
            _LOGGER.debug("BYPASS command response: %r", resp)
        except Exception as err:
            _LOGGER.error("Error bypassing zone %d: %s", zone_number, err)
            return False

    async def unbypass_zone(self, zone_number: int) -> None:
        """Remove bypass from a zone."""
        _LOGGER.info("Sending unbypass command for zone %d", zone_number)
        if zone_number not in self.zones:
            _LOGGER.warning("Zone number %d is not valid for this panel", zone_number)
            return
        try:
            await self._send_command(f"UNBYPASS {zone_number}")
        except Exception as err:
            _LOGGER.error("Error unbypassing zone %d: %s", zone_number, err)
            raise

    async def turn_output_on(self, output_number: int) -> None:
        """Turn output on permanently."""
        _LOGGER.info("Turning on output %d", output_number)
        if output_number > self.max_outputs:
            _LOGGER.warning(
                "Output number %d exceeds max outputs %d",
                output_number,
                self.max_outputs,
            )
        try:
            await self._send_command(f"OUTPUTON {output_number}")
        except Exception as err:
            _LOGGER.error("Error turning on output %d: %s", output_number, err)
            raise

    async def turn_output_off(self, output_number: int) -> None:
        """Turn output off."""
        _LOGGER.info("Turning off output %d", output_number)
        if output_number > self.max_outputs:
            _LOGGER.warning(
                "Output number %d exceeds max outputs %d",
                output_number,
                self.max_outputs,
            )
            raise ValueError(
                "Output number %d exceeds max outputs %d",
                output_number,
                self.max_outputs,
            )
        try:
            await self._send_command(f"OUTPUTOFF {output_number}")
        except Exception as err:
            _LOGGER.error("Error turning off output %d: %s", output_number, err)
            raise

    async def get_output_state(self, output_number: int) -> bool:
        """Get the current state of an output."""
        _LOGGER.info("Getting state for output %d", output_number)
        if output_number > self.max_outputs:
            raise ValueError(
                "Output number %d exceeds max outputs %d",
                output_number,
                self.max_outputs,
            )
        try:
            resp = await self._send_command(f"OUTPUT {output_number}")
            if resp is None:
                raise
            elif resp.startswith("OK"):
                parts = resp.split()
                if len(parts) == 4 and parts[3].upper() in ("ON", "OFF"):
                    state = parts[2] == "ON"
                    _LOGGER.info(
                        "Output %d state is %s", output_number, "ON" if state else "OFF"
                    )
                    return state
                else:
                    raise ValueError(
                        "Unexpected format in output state response: %r", resp
                    )
            else:
                raise ValueError(
                    "Unexpected response for output state %d: %r", output_number, resp
                )
        except Exception as err:
            _LOGGER.error("Error getting state for output %d: %s", output_number, err)
            raise

    async def set_virtual_keypad_number(self, keypad_number: int) -> None:
        """Set the virtual keypad number."""
        _LOGGER.info("Setting virtual keypad number to %d", keypad_number)
        try:
            resp = await self._send_command(f"DEVICE {keypad_number}")
            if resp and "OK" in resp:
                _LOGGER.info(
                    "Virtual keypad number set to %d successfully", keypad_number
                )
                self.virtual_keypad_number = keypad_number
            else:
                _LOGGER.warning(
                    "Failed to set virtual keypad number to %d. Response: %r",
                    keypad_number,
                    resp,
                )
                raise ValueError(
                    f"Failed to set virtual keypad number to {keypad_number}"
                )
        except Exception as err:
            _LOGGER.error(
                "Error setting virtual keypad number to %d: %s", keypad_number, err
            )

    # async def get_virtual_keypad_number(self) -> int:
    #     """Get the current virtual keypad number."""
    #     _LOGGER.info("Getting virtual keypad number")
    #     try:
    #         resp = await self._send_command("DEVICE ?")
    #         if resp is None:
    #             _LOGGER.warning("No response received for DEVICE command")
    #             return self.virtual_keypad_number
    #         if resp.startswith("OK"):
    #             parts = resp.split()
    #             if len(parts) == 3 and parts[2].isdigit():
    #                 keypad_number = int(parts[2])
    #                 _LOGGER.info("Current virtual keypad number is %d", keypad_number)
    #                 self.virtual_keypad_number = keypad_number
    #                 return keypad_number
    #             else:
    #                 _LOGGER.warning("Unexpected format in DEVICE response: %r", resp)
    #                 return self.virtual_keypad_number
    #         _LOGGER.warning("Unexpected response for DEVICE command: %r", resp)
    #         return self.virtual_keypad_number
    #     except Exception as err:
    #         _LOGGER.error("Error getting virtual keypad number: %s", err)
    #         return self.virtual_keypad_number

    # async def send_keypad_input(self, input_str: str) -> None:
    #     """Send keypad input to the panel."""
    #     _LOGGER.info("Sending keypad input: %s", input_str)
    #     try:
    #         await self._send_command(f"KEYPAD {input_str}")
    #     except Exception as err:
    #         _LOGGER.error("Error sending keypad input '%s': %s", input_str, err)

    # async def send_program_input(self, address: int, option: int, value: str) -> None:
    #     """Send programming input to the panel."""
    #     _LOGGER.info("Sending program input: address=%d, option=%d, value=%s", address, option, value)
    #     try:
    #         resp = await self._send_command(f"P{address}E{option}={value}")
    #         if resp:
    #             _LOGGER.info("Program input accepted for address=%d option=%d", address, option)
    #         else:
    #             _LOGGER.warning("Program input not accepted for address=%d option=%d. Response: %r", address,
    #             option, resp)
    #     except Exception as err:
    #         _LOGGER.error("Error sending program input address=%d option=%d value=%s: %s", address, option, value, err)

    # async def query_program_value(self, address: int, option: int) -> str | None:
    #     """Query a programming value from the panel."""
    #     _LOGGER.info("Querying program value: address=%d, option=%d", address, option)
    #     try:
    #
    #     except Exception as err:
    #         _LOGGER.error(
    #             "Error querying program value address=%d option=%d: %s",
    #             address,
    #             option,
    #             err,
    #         )
    #         return None

    def set_output_count(self, max_outputs: int) -> None:
        """Set outputs based on detected count from panel."""
        _LOGGER.info("Setting outputs, max_outputs: %d", max_outputs)
        self.max_outputs = max_outputs
        self.outputs = {i: Output() for i in range(1, max_outputs + 1)}
        _LOGGER.debug("Outputs configured: %s", self.outputs)

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

    async def _set_mode(self, mode: ProtocolMode) -> None:
        """Set the protocol mode of the panel."""
        _LOGGER.info("Setting protocol mode to %d", mode.value)
        try:
            command = mode_command(mode, self.delimiter)
            await self._session.request(command)
            self.mode = mode
            self.capabilities = _capabilities_from_mode(mode)
        except Exception as err:
            _LOGGER.error("Error setting protocol mode to %d: %s", mode, err)
            raise

    async def request_status(self) -> PanelStatus:
        """Returns:"""
        _LOGGER.info("Getting current panel status")
        if not self.is_connected:
            _LOGGER.error("Cannot get status: not connected to panel")
            raise ConnectionError("Not connected to panel")
        try:
            cmd = status_command(self.delimiter)
            await self._session.request(cmd)
        except Exception as err:
            _LOGGER.error("Error requesting status from panel: %s", err)
            raise
        return self.status()
