"""Module for parsing alarm messages with various formats."""

from typing import Callable, Final

from arrowhead_alarm.types import (
    EXPANDER_STATUS,
    NUMBERED_STATUS,
    STATUS_CODE,
    TIMESTAMPED_STATUS,
    USER_STATUS,
    AlarmState,
    PanelState,
    Status,
)


def set_panel_ready(panel: PanelState) -> None:
    """Set the panel status to ready.

    Args:
        panel: PanelState object to mutate.

    """
    panel.ready_to_arm = True


def set_panel_not_ready(panel: PanelState) -> None:
    """Set the panel status to not ready.

    Args:
        panel: PanelState object to mutate.

    """
    panel.ready_to_arm = False


def set_battery_fault(panel: PanelState) -> None:
    """Set the battery fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.battery_fault = True


def clear_battery_fault(panel: PanelState) -> None:
    """Clear the battery fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.battery_fault = False


def set_monitoring_station_active(panel: PanelState) -> None:
    """Set the monitoring station status to active.

    Args:
        panel: PanelState object to mutate.

    """
    panel.monitoring_station_active = True


def set_monitoring_station_inactive(panel: PanelState) -> None:
    """Set the monitoring station status to inactive.

    Args:
        panel: PanelState object to mutate.

    """
    panel.monitoring_station_active = False


def set_dialer_fault(panel: PanelState) -> None:
    """Set the dialer fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.dialer_fault = True


def clear_dialer_fault(panel: PanelState) -> None:
    """Clear the dialer fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.dialer_fault = False


def set_dialer_line_fault(panel: PanelState) -> None:
    """Set the dialer line fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.dialer_line_fault = True


def clear_dialer_line_fault(panel: PanelState) -> None:
    """Clear the dialer line fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.dialer_line_fault = False


def set_mains_fault(panel: PanelState) -> None:
    """Set the mains fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.mains_fault = True


def clear_mains_fault(panel: PanelState) -> None:
    """Clear the mains fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.mains_fault = False


def set_tamper_alarm_triggered(panel: PanelState) -> None:
    """Set the tamper alarm status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.tamper_alarm_triggered = True


def clear_tamper_alarm_triggered(panel: PanelState) -> None:
    """Clear the tamper alarm status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.tamper_alarm_triggered = False


def set_fuse_fault(panel: PanelState) -> None:
    """Set the fuse fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.fuse_fault = True


def clear_fuse_fault(panel: PanelState) -> None:
    """Clear the fuse fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.fuse_fault = False


def set_area_armed_away(area_number: int, panel: PanelState) -> None:
    """Set the specified area as armed away."""
    panel.areas[area_number].state = AlarmState.ARMED_AWAY


def set_area_disarmed(area_number: int, panel: PanelState) -> None:
    """Set the specified area as disarmed."""
    panel.areas[area_number].state = AlarmState.DISARMED


def set_area_armed_stay(area_number: int, panel: PanelState) -> None:
    """Set the specified area as armed stay."""
    panel.areas[area_number].state = AlarmState.ARMED_STAY


def set_area_arming_away(
    area_number: int, exit_delay: float, panel: PanelState
) -> None:
    """Set the specified area as arming away."""
    panel.areas[area_number].state = AlarmState.ARMING_AWAY


def set_area_arming_stay(
    area_number: int, exit_delay: float, panel: PanelState
) -> None:
    """Set the specified area as arming stay."""
    panel.areas[area_number].state = AlarmState.ARMING_STAY


def set_zone_entry_delay_started(
    zone_number: int, entry_delay: float, panel: PanelState
) -> None:
    """Set the specified zone as having started entry delay."""
    pass


def set_area_alarm_triggered(area_number: int, panel: PanelState) -> None:
    """Set the specified area as alarm triggered."""
    panel.areas[area_number].state = AlarmState.ALARM_TRIGGERED


def set_area_alarm_restored(area_number: int, panel: PanelState) -> None:
    """Set the specified area as alarm restored."""
    panel.areas[area_number].state = AlarmState.DISARMED


def set_area_not_ready(area_number: int, panel: PanelState) -> None:
    """Set the specified area as not ready."""
    panel.areas[area_number].ready_to_arm = False


def set_area_ready(area_number: int, panel: PanelState) -> None:
    """Set the specified area as ready."""
    panel.areas[area_number].ready_to_arm = True


def set_battery_fault_zone_expander(expander_number: int, panel: PanelState) -> None:
    """Set the battery fault status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].battery_fault = True


def clear_battery_fault_zone_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the battery fault status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].battery_fault = False


def set_battery_fault_output_expander(expander_number: int, panel: PanelState) -> None:
    """Set the battery fault status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].battery_fault = True


def clear_battery_fault_output_expander(
    expander_number: int, panel: PanelState
) -> None:
    """Clear the battery fault status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].battery_fault = False


def set_battery_fault_prox_expander(expander_number: int, panel: PanelState) -> None:
    """Set the battery fault status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].battery_fault = True


def clear_battery_fault_prox_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the battery fault status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].battery_fault = False


def set_mains_fault_prox_expander(expander_number: int, panel: PanelState) -> None:
    """Set the mains fault status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].mains_fault = True


def clear_mains_fault_prox_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the mains fault status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].mains_fault = False


def set_mains_fault_zone_expander(expander_number: int, panel: PanelState) -> None:
    """Set the mains fault status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].mains_fault = True


def clear_mains_fault_zone_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the mains fault status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].mains_fault = False


def set_mains_fault_output_expander(expander_number: int, panel: PanelState) -> None:
    """Set the mains fault status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].mains_fault = True


def clear_mains_fault_output_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the mains fault status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].mains_fault = False


def set_fuse_fault_output_expander(expander_number: int, panel: PanelState) -> None:
    """Set the fuse fault status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].fuse_fault = True


def clear_fuse_fault_output_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the fuse fault status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].fuse_fault = False


def set_fuse_fault_zone_expander(expander_number: int, panel: PanelState) -> None:
    """Set the fuse fault status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].fuse_fault = True


def clear_fuse_fault_zone_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the fuse fault status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].fuse_fault = False


def set_fuse_fault_prox_expander(expander_number: int, panel: PanelState) -> None:
    """Set the fuse fault status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].fuse_fault = True


def clear_fuse_fault_prox_expander(expander_number: int, panel: PanelState) -> None:
    """Clear the fuse fault status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].fuse_fault = False


def set_tamper_alarm_triggered_prox_expander(
    expander_number: int, panel: PanelState
) -> None:
    """Set the tamper alarm status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].tamper_alarm_triggered = True


def clear_tamper_alarm_triggered_prox_expander(
    expander_number: int, panel: PanelState
) -> None:
    """Clear the tamper alarm status for a prox expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.prox_expanders[expander_number].tamper_alarm_triggered = False


def set_tamper_alarm_triggered_zone_expander(
    expander_number: int, panel: PanelState
) -> None:
    """Set the tamper alarm status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].tamper_alarm_triggered = True


def clear_tamper_alarm_triggered_zone_expander(
    expander_number: int, panel: PanelState
) -> None:
    """Clear the tamper alarm status for a zone expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.zone_expanders[expander_number].tamper_alarm_triggered = False


def set_tamper_alarm_triggered_output_expander(
    expander_number: int, panel: PanelState
) -> None:
    """Set the tamper alarm status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].tamper_alarm_triggered = True


def clear_tamper_alarm_triggered_output_expander(
    expander_number: int, panel: PanelState
) -> None:
    """Clear the tamper alarm status for an output expander.

    Args:
        expander_number: The expander number.
        panel: PanelState object to mutate.

    """
    panel.output_expanders[expander_number].tamper_alarm_triggered = False


# Zone status operations
def set_zone_alarm(zone_number: int, panel: PanelState) -> None:
    """Set the specified zone into alarm state."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].alarm = True


def clear_zone_alarm(zone_number: int, panel: PanelState) -> None:
    """Clear the specified zone alarm/restored."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].alarm = False


def set_zone_radio_battery_low(zone_number: int, panel: PanelState) -> None:
    """Mark a radio zone's battery as low."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].radio_battery_low = True


def clear_zone_radio_battery_low(zone_number: int, panel: PanelState) -> None:
    """Mark a radio zone's battery as restored."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].radio_battery_low = False


def set_zone_bypassed(zone_number: int, panel: PanelState) -> None:
    """Set a zone as bypassed."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].bypassed = True


def clear_zone_bypassed(zone_number: int, panel: PanelState) -> None:
    """Clear a zone bypass."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].bypassed = False


def set_zone_closed(zone_number: int, panel: PanelState) -> None:
    """Mark a zone as closed/sealed."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].zone_closed = True


def set_zone_open(zone_number: int, panel: PanelState) -> None:
    """Mark a zone as open/unsealed."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].zone_closed = False


def set_zone_sensor_watch_alarm(zone_number: int, panel: PanelState) -> None:
    """Set sensor-watch alarm for a zone."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].sensor_watch_alarm = True


def clear_zone_sensor_watch_alarm(zone_number: int, panel: PanelState) -> None:
    """Clear sensor-watch alarm for a zone."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].sensor_watch_alarm = False


def set_zone_trouble(zone_number: int, panel: PanelState) -> None:
    """Set trouble alarm for a zone."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].trouble_alarm = True


def clear_zone_trouble(zone_number: int, panel: PanelState) -> None:
    """Clear trouble alarm for a zone."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].trouble_alarm = False


def set_zone_supervise_alarm(zone_number: int, panel: PanelState) -> None:
    """Set supervise alarm for a zone."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].supervise_alarm = True


def clear_zone_supervise_alarm(zone_number: int, panel: PanelState) -> None:
    """Clear supervise alarm for a zone."""
    if zone_number not in panel.zones:
        return
    panel.zones[zone_number].supervise_alarm = False


# Output status operations
def set_output_on(output_number: int, panel: PanelState) -> None:
    """Turn an output on."""
    if output_number not in panel.outputs:
        return
    panel.outputs[output_number].on = True


def set_output_off(output_number: int, panel: PanelState) -> None:
    """Turn an output off."""
    if output_number not in panel.outputs:
        return
    panel.outputs[output_number].on = False


def set_receiver_fault(panel: PanelState) -> None:
    """Set the receiver fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.receiver_fault = True


def clear_receiver_fault(panel: PanelState) -> None:
    """Clear the receiver fault status.

    Args:
        panel: PanelState object to mutate.

    """
    panel.receiver_fault = False


EXPANDER_CODE_DISPATCHER: Final[
    dict[tuple[str, str], Callable[[int, PanelState], None]]
] = {
    ("BF", "ZX"): set_battery_fault_zone_expander,
    ("BF", "OX"): set_battery_fault_output_expander,
    ("BF", "PX"): set_battery_fault_prox_expander,
    ("BR", "ZX"): clear_battery_fault_zone_expander,
    ("BR", "OX"): clear_battery_fault_output_expander,
    ("BR", "PX"): clear_battery_fault_prox_expander,
    ("MR", "PX"): clear_mains_fault_prox_expander,
    ("MR", "ZX"): clear_mains_fault_zone_expander,
    ("MR", "OX"): clear_mains_fault_output_expander,
    ("MF", "PX"): set_mains_fault_prox_expander,
    ("MF", "ZX"): set_mains_fault_zone_expander,
    ("MF", "OX"): set_mains_fault_output_expander,
    ("FR", "OX"): clear_fuse_fault_output_expander,
    ("FR", "ZX"): clear_fuse_fault_zone_expander,
    ("FR", "PX"): clear_fuse_fault_prox_expander,
    ("FF", "OX"): set_fuse_fault_output_expander,
    ("FF", "ZX"): set_fuse_fault_zone_expander,
    ("FF", "PX"): set_fuse_fault_prox_expander,
    ("TR", "PX"): clear_tamper_alarm_triggered_prox_expander,
    ("TR", "ZX"): clear_tamper_alarm_triggered_zone_expander,
    ("TR", "OX"): clear_tamper_alarm_triggered_output_expander,
    ("TA", "PX"): set_tamper_alarm_triggered_prox_expander,
    ("TA", "ZX"): set_tamper_alarm_triggered_zone_expander,
    ("TA", "OX"): set_tamper_alarm_triggered_output_expander,
}


def get_expander_status_operation(
    status: Status,
) -> Callable[[PanelState], None]:
    """Return a function that mutates PanelState based on the expander status.

    Args:
        status: Status object.

    Returns: Function that mutates PanelState based on the expander status.

    """
    if status.expander_code is None or status.expander_number is None:
        raise ValueError(
            "Extender status, expander number are required for\
             expander status operations"
        )
    key = (status.code, status.expander_code)
    operation = EXPANDER_CODE_DISPATCHER.get(key)
    if not operation:
        raise ValueError(f"Unsupported expander status: {key}")

    def panel_state_operation(panel: PanelState) -> None:
        operation(status.expander_number, panel)

    return panel_state_operation


NUMBERED_STATUS_DISPATCHER: Final[dict[str, Callable[[int, PanelState], None]]] = {
    "A": set_area_armed_away,
    "D": set_area_disarmed,
    "AA": set_area_alarm_triggered,
    "AR": set_area_alarm_restored,
    "S": set_area_armed_stay,
    "NR": set_area_not_ready,
    "RO": set_area_ready,
    "ZA": set_zone_alarm,
    "ZBL": set_zone_radio_battery_low,
    "ZBR": clear_zone_radio_battery_low,
    "ZBY": set_zone_bypassed,
    "ZBYR": clear_zone_bypassed,
    "ZC": set_zone_closed,
    "ZIA": set_zone_sensor_watch_alarm,
    "ZIR": clear_zone_sensor_watch_alarm,
    "ZO": set_zone_open,
    "ZR": clear_zone_alarm,
    "ZT": set_zone_trouble,
    "ZTR": clear_zone_trouble,
    "ZSA": set_zone_supervise_alarm,
    "ZSR": clear_zone_supervise_alarm,
    "OO": set_output_on,
    "OR": set_output_off,
}


def get_numbered_status_operation(
    numbered_status: Status,
) -> Callable[[PanelState], None]:
    """Return a function that mutates PanelState based on the numbered status.

    Args:
        numbered_status: Status object.

    Returns: Function that mutates PanelState based on the numbered status.

    """
    if numbered_status.code not in NUMBERED_STATUS_DISPATCHER:
        raise ValueError(f"Unsupported numbered status: {numbered_status.code}")
    if numbered_status.number is None:
        raise ValueError("Area number is required for numbered status operations")

    operation = NUMBERED_STATUS_DISPATCHER[numbered_status.code]

    number = numbered_status.number

    def panel_state_operation(panel: PanelState) -> None:
        operation(number, panel)

    return panel_state_operation


USER_STATUS_DISPATCHER: Final[dict[str, Callable[[int, PanelState], None]]] = {
    "A": set_area_armed_away,
    "D": set_area_disarmed,
    "S": set_area_armed_stay,
}


def get_user_status_operation(
    status: Status,
) -> Callable[[PanelState], None]:
    """Return a function that mutates PanelState based on the user status.

    Args:
        status: Status object.

    Returns: Function that mutates PanelState based on the user status.

    """
    if status.code not in USER_STATUS_DISPATCHER:
        raise ValueError(f"Unsupported user status: {status.code}")
    if status.number is None:
        raise ValueError("Area number is required for user status operations")
    if status.user_number is None:
        raise ValueError("User number is required for user status operations")

    operation = USER_STATUS_DISPATCHER[status.code]
    number = status.number

    def panel_state_operation(panel: PanelState) -> None:
        operation(number, panel)

    return panel_state_operation


TIMESTAMPED_STATUS_DISPATCHER: Final[
    dict[str, Callable[[int, float, PanelState], None]]
] = {
    "EDA": set_area_arming_away,
    "EDS": set_area_arming_stay,
    "ZEDS": set_zone_entry_delay_started,
}


def get_timestamped_status_operation(
    status: Status,
) -> Callable[[PanelState], None]:
    """Return a function that mutates PanelState based on the timestamped status.

    Args:
        status: Status object.

    Returns: Function that mutates PanelState based on the timestamped status.

    """
    if status.code not in TIMESTAMPED_STATUS_DISPATCHER:
        raise ValueError(f"Unsupported timestamped status: {status.code}")
    if status.number is None:
        raise ValueError("Area number is required for timestamped status operations")
    if status.timestamp is None:
        raise ValueError("Timestamp is required for timestamped status operations")

    operation = TIMESTAMPED_STATUS_DISPATCHER[status.code]
    number = status.number
    timestamp = status.timestamp

    def panel_state_operation(panel: PanelState) -> None:
        operation(number, timestamp, panel)

    return panel_state_operation


STATUS_CODE_DISPATCHER: Final = {
    "RO": set_panel_ready,
    "NR": set_panel_not_ready,
    "BF": set_battery_fault,
    "BR": clear_battery_fault,
    "CAL": set_monitoring_station_active,
    "CLF": set_monitoring_station_inactive,
    "DF": set_dialer_fault,
    "DR": clear_dialer_fault,
    "LF": set_dialer_line_fault,
    "LR": clear_dialer_line_fault,
    "MF": set_mains_fault,
    "MR": clear_mains_fault,
    "TA": set_tamper_alarm_triggered,
    "TR": clear_tamper_alarm_triggered,
    "FF": set_fuse_fault,
    "FR": clear_fuse_fault,
    "RIF": set_receiver_fault,
    "RIR": clear_receiver_fault,
}


def get_only_status_operation(status: Status) -> Callable[[PanelState], None]:
    """Return a function that mutates PanelState based on the status.

    Args:
        status: Status object.

    Returns: Function that mutates PanelState based on the status.

    """
    panel_state_operation = STATUS_CODE_DISPATCHER.get(status.code)
    if not panel_state_operation:
        raise ValueError(f"Unsupported status: {status.code}")
    return panel_state_operation


STATUS_TYPE_DISPATCHER: Final[
    dict[int, Callable[[Status], Callable[[PanelState], None]]]
] = {
    STATUS_CODE: get_only_status_operation,
    NUMBERED_STATUS: get_numbered_status_operation,
    EXPANDER_STATUS: get_expander_status_operation,
    USER_STATUS: get_user_status_operation,
    TIMESTAMPED_STATUS: get_timestamped_status_operation,
}


def get_status_operation(
    status: Status,
) -> Callable[[PanelState], None]:
    """Return a function that mutates PanelState based on the status type.

    Args:
        status: Status object.

    Returns: Function that mutates PanelState based on the status type.

    """
    operation_getter = STATUS_TYPE_DISPATCHER.get(status.flags)
    if not operation_getter:
        raise ValueError(f"Unsupported status type: {status.flags}")
    return operation_getter(status)
