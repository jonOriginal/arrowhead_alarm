"""Commands for interacting with the Eci alarm panel."""

from typing import Callable, TypeVar

from elitecloud_alarm import PanelState

from .consumers import (
    create_future_consumer,
    create_line_join_transformer,
    create_sliding_timeout_consumer,
)
from .transformers import (
    check_string_with_options,
    create_command_data_transformer,
    create_command_int_data_transformer,
    create_command_no_data_transformer,
    create_split_lines_transformer,
    create_strip_transformer,
    on_off_boolean_transformer,
    panel_state_message_transformer,
    panel_version_transformer,
    result_discard_transformer,
    wait_any_complete_lines,
    wait_line,
    wait_lines,
)
from .types import (
    ArmingMode,
    Error,
    FlowResult,
    Go,
    PanelVersion,
    ProtocolMode,
    Reject,
    Request,
    Transformer,
)
from .util import get_arming_keyword, get_delimiter_for_mode

T = TypeVar("T")


def create_future_request(command: str, transformer: Transformer[str, T]) -> Request[T]:
    """Create a Request object with a future consumer.

    Args:
        command: The command string to send.
        transformer: The transformer function to process the response.

    Returns:
        A Request object that will process the response using the provided transformer.

    """
    listener, fut = create_future_consumer(transformer)
    return Request(data=command, response_callback=listener, awaitable=fut)


def create_int_command_request(
    cmd_str: str,
    cmd_keyword: str,
    delimiter: str,
) -> Request[int]:
    r"""Return a request that processes an integer command response.

    Args:
        cmd_str: Command string to send.
        cmd_keyword: Command keyword to validate in the response.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will return an integer response.

    """

    def transformer(response: str) -> FlowResult[int]:
        return wait_line(response, delimiter).bind(
            create_command_int_data_transformer(cmd_str, cmd_keyword)
        )

    return create_future_request(cmd_str, transformer)


def version_command(delimiter: str) -> Request[PanelVersion]:
    r"""Return a request that retrieves the panel version.

    Args:
        delimiter: The line delimiter used in the protocol. e.g. "\r\n"

    Returns: A Request object that, when sent, will return the panel version.

    """
    cmd_str = "Version"

    def transformer(response: str) -> FlowResult[PanelVersion]:
        return (
            wait_line(response, delimiter)
            .bind(create_command_data_transformer(cmd_str, cmd_str))  # noqa: F821
            .bind(create_strip_transformer('"'))
            .bind(panel_version_transformer)
        )

    return create_future_request(cmd_str, transformer)


def string_options_command(
    message: str, options: list[str], case_sensitive: bool = True
) -> Request[str]:
    """Return a request that checks the response against a list of string options.

    Args:
        message: The payload message to send.
        options: The list of valid string options.
        case_sensitive: Whether the comparison is case-sensitive.

    Returns:
        A Request object that, when sent, will check the response against the options.

    """

    def transformer(response: str) -> FlowResult[str]:
        return check_string_with_options(response, options, case_sensitive)

    listener, fut = create_future_consumer(transformer)

    return Request(data=message, response_callback=listener, awaitable=fut)


def mode_command(mode: ProtocolMode) -> Request[str]:
    r"""Return a request that sets the protocol mode.

    Args:
        mode: Protocol mode to set.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will set the protocol mode and return \
        the mode delimiter.

    """
    keyword = "MODE"
    cmd_str = f"{keyword} {mode.value}"
    delimiter = get_delimiter_for_mode(mode)

    def mode_checker(number: int) -> FlowResult[str]:
        if number == mode.value:
            return Go(delimiter)
        else:
            return Error(
                ValueError(
                    f"Protocol mode in response ({number}) \
                    does not match requested mode ({mode.value})"
                )
            )

    def transformer(response: str) -> FlowResult[str]:
        return (
            wait_lines(response, 2, delimiter)
            .bind(create_line_join_transformer(" "))
            .bind(create_command_int_data_transformer(cmd_str, keyword))
            .bind(mode_checker)
        )

    return create_future_request(cmd_str, transformer)


def arm_user_command(
    user_id: int, pin: int, mode: ArmingMode, delimiter: str
) -> Request[int]:
    r"""Return a request that arms the panel for the user in the specified mode.

    Args:
        user_id: Positive integer representing the user ID.
        pin: User's PIN as a non-negative integer.
        mode: Arming mode to use.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will arm the panel and return the user ID.

    """
    if user_id <= 0:
        raise ValueError("User ID must be a positive integer.")
    if pin < 0:
        raise ValueError("PIN must be a non-negative integer.")

    command_keyword = get_arming_keyword(mode)
    command = f"{command_keyword} {user_id} {pin}"

    def transformer(response: str) -> FlowResult[int]:
        return wait_line(response, delimiter).bind(
            create_command_int_data_transformer(command, command_keyword)
        )

    return create_future_request(command, transformer)


def disarm_user_command(user_id: int, pin: int, delimiter: str) -> Request[int]:
    r"""Return a request that disarms the panel for the user.

    Args:
        user_id: Positive integer representing the user ID.
        pin: User's PIN as a non-negative integer.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will disarm the panel and return the user ID.

    """
    if user_id <= 0:
        raise ValueError("User ID must be a positive integer.")
    if pin < 0:
        raise ValueError("PIN must be a non-negative integer.")

    keyword = "DISARM"
    command = f"{keyword} {user_id} {pin}"

    return create_int_command_request(command, keyword, delimiter)


def disarm_area_command(area_id: int, pin: int, delimiter: str) -> Request[int]:
    r"""Return a request that disarms an area for the given PIN.

    Args:
        area_id: Positive integer representing the area ID.
        pin: User's PIN as a non-negative integer.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will disarm the area and return the area ID.

    """
    if area_id <= 0:
        raise ValueError("Area ID must be a positive integer.")
    if pin < 0:
        raise ValueError("PIN must be a non-negative integer.")

    keyword = "DISARM"
    command = f"{keyword} {area_id} {pin}"

    return create_int_command_request(command, keyword, delimiter)


def arm_no_pin_command(mode: ArmingMode, delimiter: str) -> Request[None]:
    r"""Return a request that arms the panel in single-button mode.

    Args:
        mode: Arming mode to use.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will arm the panel in single-button mode.

    """
    cmd_str = get_arming_keyword(mode)

    def transformer(response: str) -> FlowResult[None]:
        return wait_line(response, delimiter).bind(
            create_command_no_data_transformer(cmd_str, cmd_str)
        )

    return create_future_request(cmd_str, transformer)


def arm_area_command(area_id: int, mode: ArmingMode, delimiter: str) -> Request[int]:
    r"""Return a request that arms an area in the specified mode.

    Args:
        area_id: Positive integer representing the area ID.
        mode: Arming mode to use.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will arm the area and return the area ID.

    """
    if area_id <= 0:
        raise ValueError("Area ID must be a positive integer.")

    command_keyword = get_arming_keyword(mode)
    cmd_str = f"{command_keyword} {area_id}"

    return create_int_command_request(cmd_str, command_keyword, delimiter)


def status_command(delimiter: str) -> Request[list[Callable[[PanelState], None]]]:
    r"""Return a request that retrieves the panel status.

    Args:
        delimiter: The line delimiter used in the protocol. e.g. "\r\n"

    Returns: A Request object that, when sent, will return the panel status.

    """
    cmd_str = "Status"

    def operation_transformer(
        list_lines: list[str],
    ) -> FlowResult[list[Callable[[PanelState], None]]]:
        ops = []
        for line in list_lines:
            result = panel_state_message_transformer(line)
            match result:
                case Go(value=op):
                    ops.append(op)
                case Error(error=e):
                    return Error(e)
                case _:
                    continue
        return Go(ops)

    def transformer(response: str) -> FlowResult[list[Callable[[PanelState], None]]]:
        return (
            wait_any_complete_lines(response, delimiter)
            .bind(create_line_join_transformer(" "))
            .bind(create_command_data_transformer(cmd_str, cmd_str))
            .bind(create_split_lines_transformer(" "))
            .bind(operation_transformer)
        )

    listener, fut = create_sliding_timeout_consumer(transformer, timeout=0.1)
    return Request(data=cmd_str, response_callback=listener, awaitable=fut)


def bypass_zone_command(zone_id: int, delimiter: str) -> Request[int]:
    r"""Return a request that bypasses a zone.

    Args:
        zone_id: Positive integer representing the zone ID.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will bypass the zone and return the zone ID.

    """
    if zone_id <= 0:
        raise ValueError("Zone ID must be a positive integer.")

    cmd_keyword = "BYPASS"
    cmd_str = f"{cmd_keyword} {zone_id}"

    return create_int_command_request(cmd_str, cmd_keyword, delimiter)


def unbypass_zone_command(zone_id: int, delimiter: str) -> Request[int]:
    r"""Return a request that unbypasses a zone.

    Args:
        zone_id: Positive integer representing the zone ID.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will unbypass the zone and return the zone ID.

    """
    if zone_id <= 0:
        raise ValueError("Zone ID must be a positive integer.")

    cmd_keyword = "UNBYPASS"
    cmd_str = f"{cmd_keyword} {zone_id}"

    return create_int_command_request(cmd_str, cmd_keyword, delimiter)


def output_on_command(output_id: int, delimiter: str) -> Request[int]:
    r"""Return a request that turns on an output for a specified duration.

    Args:
        output_id: Positive integer representing the output ID.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will turn on the output \
        and return the output ID.

    """
    if output_id <= 0:
        raise ValueError("Output ID must be a positive integer.")

    cmd_keyword = "OUTPUTON"
    cmd_str = f"{cmd_keyword} {output_id}"

    return create_int_command_request(cmd_str, cmd_keyword, delimiter)


def output_off_command(output_id: int, delimiter: str) -> Request[int]:
    r"""Return a request that turns off an output.

    Args:
        output_id: Positive integer representing the output ID.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will turn off the output \
        and return the output ID.

    """
    if output_id <= 0:
        raise ValueError("Output ID must be a positive integer.")

    cmd_keyword = "OUTPUTOFF"
    cmd_str = f"{cmd_keyword} {output_id}"

    return create_int_command_request(cmd_str, cmd_keyword, delimiter)


def output_state_command(output_id: int, delimiter: str) -> Request[bool]:
    r"""Return a request that retrieves the state of an output.

    Args:
        output_id: Positive integer representing the output ID.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will return the output state \
        as a boolean (True for ON, False for OFF).

    """
    if output_id <= 0:
        raise ValueError("Output ID must be a positive integer.")

    cmd_keyword = "OUTPUT"
    cmd_str = f"{cmd_keyword} {output_id}"

    def parse_int_off_on(response: str) -> FlowResult[bool]:
        try:
            parts = response.split()
            if len(parts) != 2:
                return Error(ValueError("Response must contain exactly two parts"))
            num = int(parts[0])
            if num != output_id:
                return Error(
                    ValueError(
                        f"Output ID in response ({num}) \
                        does not match request ({output_id})"
                    )
                )
            return on_off_boolean_transformer(parts[1])
        except ValueError as e:
            return Error(e)

    def transformer(response: str) -> FlowResult[bool]:
        return (
            wait_line(response, delimiter)
            .bind(create_command_data_transformer(cmd_str, cmd_keyword))
            .bind(parse_int_off_on)
        )

    return create_future_request(cmd_str, transformer)
