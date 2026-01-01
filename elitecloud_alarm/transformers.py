"""Common transformers for EliteCloud Alarm protocol processing."""

from typing import Callable, TypeVar

from elitecloud_alarm.const import COMMAND_ERROR_PREFIX, COMMAND_OK_PREFIX
from elitecloud_alarm.messages import (
    get_status_operation,
)
from elitecloud_alarm.types import (
    Error,
    FlowResult,
    Go,
    PanelState,
    PanelVersion,
    Reject,
    Status,
    Transformer,
    Wait,
)
from elitecloud_alarm.util import (
    get_command_exception,
    parse_panel_version_string,
    parse_status,
    split_complete_lines,
)

T = TypeVar("T")
U = TypeVar("U")


def apply_and_catch(data: T, func: Callable[[T], U]) -> FlowResult[U]:
    """Apply a function to the data and catch exceptions.

    Args:
        data: data to process.
        func: Function to apply to the data.

    Returns:
        FlowResult containing the processing result or an Error.

    """
    try:
        result = func(data)
        return Go(result)
    except Exception as e:
        return Error(e)


def transform_and_catch(data: T, transformer: Transformer[T, U]) -> FlowResult[U]:
    """Process the data using the provided transformer and catches exceptions.

    Args:
        data: data to process.
        transformer: Transformer function to handle the data.

    Returns: FlowResult containing the processing result or an Error.

    """
    try:
        return transformer(data)
    except Exception as e:
        return Error(e)


def command_ok_or_err(prefix: str) -> FlowResult[bool]:
    """Check if the command prefix indicates success or failure.

    Args:
        prefix: Prefix string.

    Returns: FlowResult indicating Ok (True), Error (False).

    """
    if prefix == COMMAND_OK_PREFIX:
        return Go(True)
    elif prefix == COMMAND_ERROR_PREFIX:
        return Go(False)
    else:
        return Reject()


def on_off_boolean_transformer(data: str) -> FlowResult[bool]:
    """Transform "ON"/"OFF" strings into boolean values.

    Args:
        data: Input string, expected to be "ON" or "OFF".

    Returns: FlowResult containing True for "ON", False for "OFF", or Reject.

    """
    data_upper = data.strip().upper()
    if data_upper == "ON":
        return Go(True)
    elif data_upper == "OFF":
        return Go(False)
    else:
        return Reject()


def check_expected_keyword(
    keyword: str, expected_keyword: str, case_sensitive: bool = False
) -> FlowResult[None]:
    """Check if the keyword matches the expected keyword.

    Args:
        keyword: Keyword string.
        expected_keyword: Expected keyword to match.
        case_sensitive: Whether the comparison is case-sensitive.

    Returns: FlowResult indicating success or rejection.

    """
    if not case_sensitive:
        word_cmp = keyword.upper()
        expected_keyword_cmp = expected_keyword.upper()
    else:
        word_cmp = keyword
        expected_keyword_cmp = expected_keyword
    if word_cmp == expected_keyword_cmp:
        return Go(None)
    else:
        return Reject()


def wait_any_complete_lines(data: str, delimiter: str) -> FlowResult[list[str]]:
    """Check if the data contains any complete lines."""
    lines = split_complete_lines(data, delimiter)
    if len(lines) == 0:
        return Wait()
    return Go(lines)


def wait_lines(data: str, expected_lines: int, delimiter: str) -> FlowResult[list[str]]:
    """Check if the data contains the expected number of complete lines."""
    lines = split_complete_lines(data, delimiter)
    if len(lines) == expected_lines:
        return Go(lines)
    return Wait()


def wait_line(data: str, delimiter: str) -> FlowResult[str]:
    """Wait for a single complete line."""

    def first_line_transformer(lines: list[str]) -> FlowResult[str]:
        return Go(lines[0])

    return wait_lines(data, 1, delimiter).bind(first_line_transformer)


def create_line_join_transformer(joiner: str) -> Transformer[list[str], str]:
    """Return Transformer that joins lines using the specified joiner.

    Args:
        joiner: String used to join the lines.

    Returns: Transformer that joins the lines.

    """

    def transformer(lines: list[str]) -> FlowResult[str]:
        joined = joiner.join(lines)
        return Go(joined)

    return transformer


def create_split_lines_transformer(delimiter: str) -> Transformer[str, list[str]]:
    """Return Transformer that splits data into lines using the specified delimiter.

    Args:
        delimiter: Delimiter used to split the data.

    """

    def transformer(data: str) -> FlowResult[list[str]]:
        lines = data.split(delimiter)
        return Go(lines)

    return transformer


def result_discard_transformer(_: object) -> FlowResult[None]:
    """Discards the data and indicates completion."""
    return Go(None)


def create_strip_transformer(chars: str | None = None) -> Transformer[str, str]:
    """Return a Transformer that strips characters from the data string.

    Args:
        chars: Characters to strip from the data string.

    Returns: Transformer that strips characters from the data string.

    """

    def transformer(data: str) -> FlowResult[str]:
        stripped = data.strip(chars)
        return Go(stripped)

    return transformer


def str_to_int_transformer(data: str) -> FlowResult[int]:
    """Parse the data string into an integer."""
    try:
        value = int(data.strip())
        return Go(value)
    except ValueError as e:
        return Error(e)


def check_string_with_options(
    data: str, options: list[str], case_sensitive: bool = True
) -> FlowResult[str]:
    """Check the data string against a list of options.

    Args:
        data: data string to check.
        options: List of valid options.
        case_sensitive: Whether the comparison is case-sensitive.

    Returns:
        FlowResult containing the matched option or an error.

    """
    if not case_sensitive:
        data_cmp = data.upper()
        options_cmp = [option.upper() for option in options]
    else:
        data_cmp = data
        options_cmp = options

    for opt in options_cmp:
        if opt == data_cmp:
            return Go(opt)

    for opt in options_cmp:
        if opt.startswith(data_cmp):
            return Wait()

    return Reject()


def panel_version_transformer(version_string: str) -> FlowResult[PanelVersion]:
    """Check and parse the version string into a PanelVersion object.

    Args:
        version_string: Version string to parse.

    Returns: FlowResult containing the PanelVersion or an Error.

    """
    try:
        version = parse_panel_version_string(version_string)
        return Go(version)
    except ValueError as e:
        return Error(e)


def create_command_data_transformer(
    command: str, keyword: str
) -> Transformer[str, str]:
    r"""Return a Transformer that checks for command response prefixes.

    Response format:
    <COMMAND_OK/ERR> <KEYWORD> <DATA>

    Example:
    OK STATUS All systems normal

    Args:
        command: Command string that was sent.
        keyword: Expected keyword in the data.

    Returns:
        Transformer that processes the response string.

    """

    def transformer(response: str) -> FlowResult[str]:
        parts = response.strip().split(" ", 2)
        if len(parts) < 2:
            return Reject()

        def return_data(_: None) -> FlowResult[str]:
            if len(parts) == 2:
                return Go("")
            else:
                return Go(parts[2])

        def error_or_keyword_transformer(is_ok: bool) -> FlowResult[str]:
            if is_ok:
                return check_expected_keyword(parts[1], keyword).bind(return_data)
            else:
                try:
                    error_code_int = int(parts[1])
                    exception = get_command_exception(error_code_int, command, response)
                    return Error(exception)
                except ValueError as e:
                    return Error(e)

        return command_ok_or_err(parts[0]).bind(error_or_keyword_transformer)

    return transformer


def create_command_int_data_transformer(
    command: str, keyword: str
) -> Transformer[str, int]:
    """Return a Transformer that processes command responses with integer data.

    Response format:
    <COMMAND_OK/ERR> <KEYWORD> <INTEGER_DATA>

    Example:
    OK STATUS 42

    Args:
        command: Command string that was sent.
        keyword: Expected keyword in the data.

    Returns:
        Transformer that processes the response string and extracts integer data.

    """
    command_transformer = create_command_data_transformer(command, keyword)

    def transformer(response: str) -> FlowResult[int]:
        return command_transformer(response).bind(str_to_int_transformer)

    return transformer


def create_command_no_data_transformer(
    command: str, keyword: str
) -> Transformer[str, None]:
    """Return a Transformer that processes command responses with no data.

    Response format:
    <COMMAND_OK/ERR> <KEYWORD>

    Example:
    OK STATUS

    Args:
        command: Command string that was sent.
        keyword: Expected keyword in the data.

    Returns:
        Transformer that processes the response string.

    """
    command_transformer = create_command_data_transformer(command, keyword)

    def transformer(response: str) -> FlowResult[None]:
        return command_transformer(response).bind(result_discard_transformer)

    return transformer


def panel_state_message_transformer(
    data: str,
) -> FlowResult[Callable[[PanelState], None]]:
    """Return a FlowResult containing the operation to apply to PanelStatus.

    Args:
        data: Status line data string.

    Returns: FlowResult containing the operation to apply to PanelStatus.

    """

    def status_transformer(
        status: Status,
    ) -> FlowResult[Callable[[PanelState], None]]:
        return apply_and_catch(status, get_status_operation)

    return apply_and_catch(data, parse_status).bind(status_transformer)
