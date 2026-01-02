"""Common transformers for Arrowhead alarm protocol processing."""

from typing import Callable, TypeVar

from arrowhead_alarm.const import COMMAND_ERROR_PREFIX, COMMAND_OK_PREFIX
from arrowhead_alarm.messages import (
    get_status_operation,
)
from arrowhead_alarm.types import (
    Error,
    Fail,
    Flow,
    FlowResult,
    Go,
    Outcome,
    PanelState,
    PanelVersion,
    Reject,
    Success,
    Transformer,
    Wait,
)
from arrowhead_alarm.util import (
    get_command_exception,
    parse_panel_version_string,
    parse_status,
    split_complete_lines,
)

T = TypeVar("T")
U = TypeVar("U")


def create_transformer(func: Callable[[T], U]) -> Transformer[T, U]:
    """Create a Transformer from a simple function.

    Args:
        func: Function to convert T to U.

    Returns: Transformer that applies the function.

    """

    def transformer(data: T) -> FlowResult[U]:
        try:
            result = func(data)
            return Go(result)
        except Exception as e:
            return Error(e)

    return transformer


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


def outcome_transformer(outcome: Outcome[T]) -> FlowResult[T]:
    """Transform an Outcome into a FlowResult.

    Args:
        outcome: Outcome to transform.

    Returns: FlowResult containing the value or an Error.

    """
    match outcome:
        case Success(value):
            return Go(value)
        case Fail(exception):
            return Error(exception)
        case _:
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


def create_wait_any_complete_line_transformer(
    delimiter: str,
) -> Transformer[str, list[str]]:
    """Wait for any complete lines in the data.

    Args:
        delimiter: Delimiter used to identify line endings.

    Returns:
        Transformer that waits for any complete lines.

    """

    def transformer(data: str) -> FlowResult[list[str]]:
        lines = split_complete_lines(data, delimiter)
        if lines:
            return Go[list[str]](lines)
        return Wait()

    return transformer


def create_wait_lines_transformer(
    expected_lines: int, delimiter: str
) -> Transformer[str, list[str]]:
    """Wait for a specific number of complete lines.

    Args:
        expected_lines: Number of complete lines to wait for.
        delimiter: Delimiter used to identify line endings.

    Returns:
        Transformer that waits for the specified number of complete lines.

    """

    def transformer(data: str) -> FlowResult[list[str]]:
        lines = split_complete_lines(data, delimiter)
        if len(lines) == expected_lines:
            return Go(lines)
        return Wait()

    return transformer


def create_wait_line_transformer(delimiter: str) -> Transformer[str, str]:
    """Return Transformer that waits for a single complete line.

    Args:
        delimiter: Delimiter used to identify line endings.

    Returns: Transformer that waits for a single complete line.

    """

    def first_line_transformer(lines: list[str]) -> FlowResult[str]:
        return Go(lines[0])

    return (
        Flow() >> create_wait_lines_transformer(1, delimiter) >> first_line_transformer
    )


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


def create_split_transformer(delimiter: str) -> Transformer[str, list[str]]:
    """Return Transformer that splits data into lines using the specified delimiter.

    Args:
        delimiter: Delimiter used to split the data.

    """

    def transformer(data: str) -> FlowResult[list[str]]:
        if not data:
            return Go([])
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
    return (
        Flow()
        >> create_command_data_transformer(command, keyword)
        >> str_to_int_transformer
    )


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
    return (
        Flow()
        >> create_command_data_transformer(command, keyword)
        >> result_discard_transformer
    )


panel_state_message_transformer = (
    Flow()
    >> create_transformer(parse_status)
    >> outcome_transformer
    >> create_transformer(get_status_operation)
)


def create_simple_panel_state_transformer(
    code: str, operation: Callable[[PanelState], None]
) -> Transformer[str, Callable[[PanelState], None]]:
    """Return a transformer that applies a simple PanelState operation if the code matches.

    Args:
        code: Code string to match.
        operation: Operation to apply to the PanelState.

    Returns: Transformer that applies the operation if the code matches.

    """  # noqa: E501

    def transformer(data: str) -> FlowResult[Callable[[PanelState], None]]:
        if data.strip() == code:
            return Go[Callable[[PanelState], None]](operation)
        return Reject()

    return transformer


def create_integer_panel_state_transformer(
    code: str, operation: Callable[[int, PanelState], None]
) -> Transformer[str, Callable[[PanelState], None]]:
    """Return a transformer that applies an integer PanelState operation if the code matches.

    Args:
        code: Code string to match.
        operation: Operation to apply to the PanelState with an integer parameter.

    Returns:
        Transformer that applies the operation if the code matches.

    """  # noqa: E501

    def transformer(parts: list[str]) -> FlowResult[Callable[[PanelState], None]]:
        if parts[0] != code:
            return Reject()
        try:
            num = int(parts[1])

            def apply_operation(p: PanelState) -> None:
                operation(num, p)

            return Go[Callable[[PanelState], None]](apply_operation)
        except ValueError:
            return Error(ValueError(f"Invalid integer in panel status: {parts}"))

    return Flow() >> create_split_transformer(" ") >> transformer
