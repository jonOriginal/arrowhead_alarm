"""Parsing utilities for handling command responses."""

import asyncio
from asyncio import Future, Queue
from typing import Tuple, TypeVar

from .const import COMMAND_ERROR_PREFIX, COMMAND_OK_PREFIX
from .exceptions import (
    CommandError,
    CommandNotAllowed,
    CommandNotUnderstood,
    InvalidParameter,
    RxBufferOverflow,
    TxBufferOverflow,
    XModemSessionFailed,
)
from .types import (
    Error,
    Fail,
    FlowResult,
    Go,
    Listener,
    PanelVersion,
    Processor,
    Restart,
    Result,
    Success,
    Wait,
)
from .util import parse_version_string, split_complete_lines

T = TypeVar("T")
U = TypeVar("U")


def process_and_catch(response: T, processor: Processor[T, U]) -> FlowResult[U]:
    """Process the response using the provided processor and catches exceptions.

    Args:
        response: Response data to process.
        processor: Processor function to handle the response.

    Returns: FlowResult containing the processing result or an Error.

    """
    try:
        return processor(response)
    except Exception as e:
        return Error(e)


def create_future_parser(
    processor: Processor[str, T],
) -> tuple[Listener[str], Future[T]]:
    """Create a parser that completes a Future when done.

    Args:
        processor: Processor function to handle the response.

    Returns: Tuple containing the listener and the Future.

    """
    fut: Future[T] = asyncio.get_event_loop().create_future()
    buffer = ""

    def process_char(char: str) -> None:
        nonlocal buffer
        buffer += char
        result = process_and_catch(buffer, processor)
        if fut.done():
            return
        match result:
            case Go(value):
                fut.set_result(value)
            case Error(e):
                fut.set_exception(e)
            case Wait():
                pass
            case Restart():
                buffer = ""
            case _:
                raise NotImplementedError("Unknown FlowResult type")

    def listener(response: str | Exception) -> None:
        if fut.done():
            return
        if isinstance(response, Exception):
            fut.set_exception(response)
            return
        for char in response:
            process_char(char)

    return listener, fut


def create_queue_parser(
    processor: Processor[str, T],
) -> tuple[Listener[str], Queue[Result[T]]]:
    """Create a parser that puts results into a queue.

    Args:
        processor: Processor function to handle the response.

    Returns:
        Tuple containing the listener and the Queue.

    """
    queue: Queue[Result[T]] = Queue()
    buffer = ""

    def parser(response: str | Exception) -> None:
        nonlocal buffer
        if isinstance(response, Exception):
            queue.put_nowait(Fail(response))
            return
        for char in response:
            buffer += char
            result = process_and_catch(buffer, processor)
            match result:
                case Go(value):
                    queue.put_nowait(Success(value))
                    buffer = ""
                case Error(e):
                    queue.put_nowait(Fail(e))
                    buffer = ""
                case Wait():
                    pass
                case Restart():
                    buffer = ""
                case _:
                    raise NotImplementedError("Unknown FlowResult type")

    return parser, queue


def create_sliding_timeout_parser(
    processor: Processor[str, T], timeout: float
) -> tuple[Listener[str], Future[T]]:
    """Return a parser that uses a sliding timeout to determine completion.

    Args:
        processor: Processor function to handle the response.
        timeout: Sliding timeout duration in seconds.

    Returns: Tuple containing the listener and the Future.

    """
    fut: Future[T] = asyncio.get_event_loop().create_future()
    buffer = ""
    timer: asyncio.Handle | None = None

    def parser(response: str | Exception) -> None:
        nonlocal buffer
        nonlocal timer
        if fut.done():
            return
        if isinstance(response, Exception):
            fut.set_exception(response)
            return
        if timer is None:
            timer = asyncio.get_event_loop().call_later(timeout, _on_timeout, None)
        for char in response:
            if fut.done():
                return
            buffer += char
            result = process_and_catch(buffer, processor)
            match result:
                case Error(e):
                    fut.set_exception(e)
                case Restart():
                    buffer = ""
                case Go(_):
                    timer.cancel()
                    timer = asyncio.get_event_loop().call_later(
                        timeout, _on_timeout, None
                    )
                    pass
                case Wait():
                    pass
                case _:
                    raise NotImplementedError("Unknown FlowResult type")

    def _on_timeout(_: None) -> None:
        nonlocal buffer
        if fut.done():
            return
        result = processor(buffer)
        match result:
            case Go(value):
                fut.set_result(value)
            case Error(e):
                fut.set_exception(e)
            case _:
                fut.set_exception(asyncio.TimeoutError("Incomplete"))

    return parser, fut


def check_version_string(version_string: str) -> FlowResult[PanelVersion]:
    try:
        version = parse_version_string(version_string)
        return Go(version)
    except ValueError as e:
        return Error(e)


def get_command_exception(error_code: int, command: str, response: str) -> Exception:
    match error_code:
        case 1:
            return CommandNotUnderstood(command, response)
        case 2:
            return InvalidParameter(command, response)
        case 3:
            return CommandNotAllowed(command, response)
        case 4:
            return RxBufferOverflow(command, response)
        case 5:
            return TxBufferOverflow(command, response)
        case 6:
            return XModemSessionFailed(command, response)
        case _:
            return CommandError(f"Unknown error code {error_code}", command, response)


def catch_command_error(response: str, command: str) -> FlowResult[str]:
    words = response.split()
    if words and words[0] == COMMAND_OK_PREFIX:
        response = " ".join(words[1:])
        return Go(response)
    elif words and words[0] == COMMAND_ERROR_PREFIX:
        try:
            error_code = int(words[1])
        except (IndexError, ValueError):
            error_code = 0
        exception = get_command_exception(error_code, command, response)
        return Error(exception)
    else:
        return Wait()


def wait_any_complete_lines(response: str, delimiter: str) -> FlowResult[list[str]]:
    """Splits the response into complete lines based on the delimiter. If the last line is incomplete,
    it is excluded.
    """
    lines = split_complete_lines(response, delimiter)
    if len(lines) == 0:
        return Wait()
    return Go(lines)


def wait_lines(
    response: str, expected_lines: int, delimiter: str
) -> FlowResult[list[str]]:
    """Checks if the response contains the expected number of complete lines."""
    lines = split_complete_lines(response, delimiter)
    if len(lines) == expected_lines:
        return Go(lines)
    return Wait()


def wait_line(response: str, delimiter: str) -> FlowResult[str]:
    """Waits for a single complete line in the response."""

    def first_line_processor(lines: list[str]) -> FlowResult[str]:
        return Go(lines[0])

    return wait_lines(response, 1, delimiter).bind(first_line_processor)


def join_lines(response: list[str], delimiter: str) -> FlowResult[str]:
    joined_response = delimiter.join(response)
    return Go(joined_response)


def split_lines(response: str, delimiter: str) -> FlowResult[list[str]]:
    lines = response.split(delimiter)
    return Go(lines)


def check_expected_keyword(
    response: str, expected_keyword: str, case_sensitive: bool = True
) -> FlowResult[str]:
    words = response.split()
    words[0] = words[0]
    if not case_sensitive:
        words[0] = words[0].upper()
        expected_keyword = expected_keyword.upper()
    if words and words[0] == expected_keyword:
        response = " ".join(words[1:])
        return Go(response)
    return Wait()


def go_discard(_: object) -> FlowResult[None]:
    """Discards the response and indicates completion."""
    return Go(None)


def strip(response: str) -> FlowResult[str]:
    """Strips leading and trailing whitespace from the response."""
    return Go(response.strip())


def parse_int(response: str) -> FlowResult[int]:
    """Parses the response string into an integer."""
    try:
        value = int(response.strip())
        return Go(value)
    except ValueError as e:
        return Error(e)


def check_string_with_options(
    response: str, options: list[str], case_sensitive: bool = True
) -> FlowResult[str]:
    """Waits for a response that ends with a valid option from the provided list."""
    response_cmp = response
    options_cmp = options
    if not case_sensitive:
        response_cmp = response.upper()
        options_cmp = [option.upper() for option in options]

    for opt in options_cmp:
        if opt == response_cmp:
            return Go(opt)

    for opt in options_cmp:
        if opt.startswith(response_cmp):
            return Wait()

    return Restart()


def single_line_command_step(
    resp: str, command: str, keyword: str, delimiter: str
) -> FlowResult[str]:
    """Checks if the response does not contain an error and is followed by the expected keyword."""

    def keyword_processor(response: str) -> FlowResult[str]:
        return check_expected_keyword(response, keyword)

    def catch_command_error_processor(response: str) -> FlowResult[str]:
        return catch_command_error(response, command)

    return (
        wait_line(resp, delimiter)
        .bind(catch_command_error_processor)
        .bind(keyword_processor)
    )


def line_listener(line_ending: str) -> Tuple[Listener[str], Future[str]]:
    """Listener that reads lines ending with the specified line ending."""

    def processor(response: str) -> FlowResult[str]:
        return wait_line(response, line_ending).bind(strip)

    return create_future_parser(processor)


def string_options_listener(
    *args: str, case_sensitive: bool = True
) -> Tuple[Listener[str], Future[str]]:
    """Listener that matches strings against a set of options."""
    options = list(args)

    def processor(response: str) -> FlowResult[str]:
        return check_string_with_options(response, options, case_sensitive)

    return create_future_parser(processor)


def ok_status_listener(
    timeout: float, delimiter: str
) -> Tuple[Listener[str], Future[list[str]]]:
    """Listener that collects lines until an OK status is received."""

    def complete_line_processor(response: str) -> FlowResult[list[str]]:
        return wait_any_complete_lines(response, delimiter)

    def join_line_processor(response: list[str]) -> FlowResult[str]:
        return join_lines(response, delimiter)

    def command_success_processor(response: str) -> FlowResult[str]:
        return catch_command_error(response, "OK Status")

    def command_keyword_processor(response: str) -> FlowResult[str]:
        return check_expected_keyword(response, "Status")

    def split_line_processor(response: str) -> FlowResult[list[str]]:
        return split_lines(response, delimiter)

    def processor(response: str) -> FlowResult[list[str]]:
        return (
            complete_line_processor(response)
            .bind(join_line_processor)
            .bind(command_success_processor)
            .bind(command_keyword_processor)
            .bind(split_line_processor)
        )

    return create_sliding_timeout_parser(processor, timeout)
