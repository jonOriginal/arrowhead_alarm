"""Commands for interacting with the Eci alarm panel."""

from .parsing import (
    check_string_with_options,
    check_version_string,
    create_future_parser,
    create_sliding_timeout_parser,
    go_discard,
    join_lines,
    parse_int,
    single_line_command_step,
    strip,
    wait_lines,
)
from .types import (
    ArmingMode,
    Error,
    FlowResult,
    Go,
    PanelVersion,
    ProtocolMode,
    Request,
)


def version_command(delimiter: str) -> Request[PanelVersion]:
    r"""Return a request that retrieves the panel version.

    Args:
        delimiter: The line delimiter used in the protocol. e.g. "\r\n"

    Returns: A Request object that, when sent, will return the panel version.

    """
    cmd_str = "Version"

    def processor(response: str) -> FlowResult[PanelVersion]:
        return single_line_command_step(response, cmd_str, "Version", delimiter).bind(
            check_version_string
        )

    listener, fut = create_future_parser(processor)

    return Request(data=cmd_str, callback=listener, awaitable=fut)


def string_options_request(
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

    def processor(response: str) -> FlowResult[str]:
        return check_string_with_options(response, options, case_sensitive)

    listener, fut = create_future_parser(processor)

    return Request(data=message, callback=listener, awaitable=fut)


def mode_command(mode: ProtocolMode, delimiter: str) -> Request[None]:
    r"""Return a request that sets the protocol mode.

    Args:
        mode: Protocol mode to set.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will set the protocol mode.

    """
    cmd_str = f"MODE {mode.value}"

    def mode_processor(response: str) -> FlowResult[int]:
        try:
            return Go(int(response.strip()))
        except ValueError:
            return Error(ValueError("Invalid mode response"))

    def command_success_processor(response: str) -> FlowResult[str]:
        return single_line_command_step(response, cmd_str, "Mode", delimiter)

    def join_line_processor(response: list[str]) -> FlowResult[str]:
        return join_lines(response, "\n")

    def processor(response: str) -> FlowResult[None]:
        return (
            wait_lines(response, 2, delimiter)
            .bind(join_line_processor)
            .bind(command_success_processor)
            .bind(mode_processor)
            .bind(go_discard)
        )

    listener, fut = create_future_parser(processor)

    return Request(data=cmd_str, callback=listener, awaitable=fut)


def get_arming_keyword(mode: ArmingMode) -> str:
    """Return the arming command keyword for the given arming mode.

    Args:
        mode (ArmingMode): The arming mode.

    Returns:
        str: The corresponding arming command keyword.

    Raises:
        ValueError: If the arming mode is unsupported.

    """
    match mode:
        case ArmingMode.AWAY:
            return "ARMAWAY"
        case ArmingMode.STAY:
            return "ARMSTAY"
        case _:
            raise ValueError(f"Unsupported arming mode: {mode}")


def _arm_command_processor(
    response: str, command: str, command_keyword: str, delimiter: str
) -> FlowResult[str]:
    return single_line_command_step(response, command, command_keyword, delimiter)


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

    def processor(response: str) -> FlowResult[int]:
        return (
            _arm_command_processor(response, command, command_keyword, delimiter)
            .bind(strip)
            .bind(parse_int)
        )

    listener, fut = create_future_parser(processor)

    return Request(data=command, callback=listener, awaitable=fut)


def arm_no_pin_command(mode: ArmingMode, delimiter: str) -> Request[None]:
    r"""Return a request that arms the panel in single-button mode.

    Args:
        mode: Arming mode to use.
        delimiter: Line delimiter used in the protocol. e.g. "\r\n"

    Returns:
        Request object that, when sent, will arm the panel in single-button mode.

    """
    cmd_str = get_arming_keyword(mode)

    def processor(response: str) -> FlowResult[None]:
        return _arm_command_processor(response, cmd_str, cmd_str, delimiter).bind(
            go_discard
        )

    listener, fut = create_future_parser(processor)

    return Request(data=cmd_str, callback=listener, awaitable=fut)


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

    def processor(response: str) -> FlowResult[int]:
        return (
            _arm_command_processor(response, cmd_str, command_keyword, delimiter)
            .bind(strip)
            .bind(parse_int)
        )

    listener, fut = create_future_parser(processor)

    return Request(data=cmd_str, callback=listener, awaitable=fut)


def status_command(delimiter: str) -> Request[None]:
    r"""Return a request that retrieves the panel status.

    Args:
        delimiter: The line delimiter used in the protocol. e.g. "\r\n"

    Returns: A Request object that, when sent, will return the panel status.

    """
    cmd_str = "Status"

    def processor(response: str) -> FlowResult[None]:
        return single_line_command_step(response, cmd_str, "Status", delimiter).bind(
            go_discard
        )

    listener, fut = create_sliding_timeout_parser(processor, timeout=0.1)

    return Request(data=cmd_str, callback=listener, awaitable=fut)
