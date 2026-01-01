"""Parsing utilities for handling command datas."""

from asyncio import Future, Handle, Queue, get_event_loop
from typing import Callable, Tuple, TypeVar

from .transformers import (
    check_string_with_options,
    create_command_data_transformer,
    create_line_join_transformer,
    create_split_lines_transformer,
    create_strip_transformer,
    panel_state_message_transformer,
    transform_and_catch,
    wait_any_complete_lines,
    wait_line,
)
from .types import (
    Consumer,
    Error,
    Fail,
    FlowResult,
    Go,
    Outcome,
    PanelState,
    Reject,
    Success,
    Transformer,
    Wait,
)

T = TypeVar("T")
U = TypeVar("U")


def create_future_consumer(  # noqa: C901
    transformer: Transformer[str, T],
) -> tuple[Consumer[str], Future[T]]:
    """Create a consumer that completes a Future when done.

    Args:
        transformer: Transformer function to handle the data.

    Returns: Tuple containing the consumer and the Future.

    """
    fut: Future[T] = get_event_loop().create_future()
    buffer: str = ""

    def process_char(char: str) -> None:
        nonlocal buffer
        buffer += char
        result = transform_and_catch(buffer, transformer)
        if fut.done():
            return
        match result:
            case Go(value):
                fut.set_result(value)
            case Error(e):
                fut.set_exception(e)
            case Wait():
                pass
            case Reject():
                buffer = ""
            case _:
                raise NotImplementedError("Unknown FlowResult type")

    def consumer(data: str | Exception) -> None:
        if fut.done():
            return
        if isinstance(data, Exception):
            fut.set_exception(data)
            return
        for char in data:
            process_char(char)

    return consumer, fut


def create_queue_consumer(
    transformer: Transformer[str, T],
) -> tuple[Consumer[str], Queue[Outcome[T]]]:
    """Create a consumer that puts results into a queue.

    Args:
        transformer: Transformer function to handle the data.

    Returns:
        Tuple containing the consumer and the Queue.

    """
    queue: Queue[Outcome[T]] = Queue()
    buffer: str = ""

    def consumer(data: str | Exception) -> None:
        nonlocal buffer
        if isinstance(data, Exception):
            queue.put_nowait(Fail(data))
            return
        for char in data:
            buffer += char
            result = transform_and_catch(buffer, transformer)
            match result:
                case Go(value):
                    queue.put_nowait(Success(value))
                    buffer = ""
                case Error(e):
                    queue.put_nowait(Fail(e))
                    buffer = ""
                case Wait():
                    pass
                case Reject():
                    buffer = ""
                case _:
                    raise NotImplementedError("Unknown FlowResult type")

    return consumer, queue


def create_sliding_timeout_consumer(  # noqa: C901
    transformer: Transformer[str, T], timeout: float
) -> tuple[Consumer[str], Future[T]]:
    """Return a consumer and future that uses a sliding timeout to determine completion.

    Args:
        transformer: Transformer function to handle the data.
        timeout: Sliding timeout duration in seconds.

    Returns: Tuple containing the consumer and the Future.

    """
    fut: Future[T] = get_event_loop().create_future()
    buffer = ""
    timer: Handle | None = None

    def consumer(data: str | Exception) -> None:
        nonlocal buffer
        nonlocal timer
        if fut.done():
            return
        if isinstance(data, Exception):
            fut.set_exception(data)
            return
        if timer is None:
            timer = get_event_loop().call_later(timeout, _on_timeout, None)
        for char in data:
            if fut.done():
                return
            buffer += char
            result = transform_and_catch(buffer, transformer)
            match result:
                case Error(e):
                    fut.set_exception(e)
                case Reject():
                    buffer = ""
                case Go(_):
                    timer.cancel()
                    timer = get_event_loop().call_later(timeout, _on_timeout, None)
                    pass
                case Wait():
                    pass
                case _:
                    raise NotImplementedError("Unknown FlowResult type")

    def _on_timeout(_: None) -> None:
        nonlocal buffer
        if fut.done():
            return
        result = transformer(buffer)
        match result:
            case Go(value):
                fut.set_result(value)
            case Error(e):
                fut.set_exception(e)
            case _:
                fut.set_exception(TimeoutError("Incomplete"))

    return consumer, fut


def line_consumer(delimiter: str) -> Tuple[Consumer[str], Future[str]]:
    """Return a consumer and future that collects a single line.

    Args:
        delimiter: Line ending delimiter.

    Returns: Tuple containing the consumer and the Future.

    """

    def transformer(data: str) -> FlowResult[str]:
        return wait_line(data, delimiter).bind(create_strip_transformer())

    return create_future_consumer(transformer)


def string_options_consumer(
    *args: str, case_sensitive: bool = True
) -> Tuple[Consumer[str], Future[str]]:
    """Return a consumer and future that checks the data against a list of string options.

    Args:
        *args: Valid string options.
        case_sensitive: Whether the comparison is case-sensitive.

    Returns:
        Tuple containing the consumer and the Future.

    """
    options = list(args)

    def transformer(data: str) -> FlowResult[str]:
        return check_string_with_options(data, options, case_sensitive)

    return create_future_consumer(transformer)


def create_status_consumer(
    timeout: float, delimiter: str
) -> Tuple[Consumer[str], Future[list[str]]]:
    """Return a consumer and future that processes an OK status response.

    Args:
        timeout: Sliding timeout duration in seconds.
        delimiter: Line ending delimiter.

    Returns: Tuple containing the consumer and the Future.

    """
    command = "STATUS"

    def complete_line_transformer(data: str) -> FlowResult[list[str]]:
        return wait_any_complete_lines(data, delimiter)

    def transformer(data: str) -> FlowResult[list[str]]:
        return (
            complete_line_transformer(data)
            .bind(create_line_join_transformer(" "))
            .bind(create_command_data_transformer(command, command))
            .bind(create_split_lines_transformer(" "))
        )

    return create_sliding_timeout_consumer(transformer, timeout)


def simple_panel_state_transformer(
    code: str, operation: Callable[[PanelState], None]
) -> Transformer[str, Callable[[PanelState], None]]:
    """Process panel status messages based on the provided code and operation."""

    def transformer(data: str) -> FlowResult[Callable[[PanelState], None]]:
        if data.strip() == code:
            return Go[Callable[[PanelState], None]](operation)
        return Reject()

    return transformer


def create_integer_panel_state_transformer(
    code: str, operation: Callable[[int, PanelState], None]
) -> Transformer[str, Callable[[PanelState], None]]:
    """Return a transformer that handles panel status messages with integer values."""

    def transformer(data: str) -> FlowResult[Callable[[PanelState], None]]:
        parts = data.strip().split(" ", 1)
        if parts[0] != code:
            return Reject()
        try:
            num = int(parts[1])

            def apply_operation(p: PanelState) -> None:
                operation(num, p)

            return Go[Callable[[PanelState], None]](apply_operation)
        except ValueError:
            return Error(ValueError(f"Invalid integer in panel status: {data}"))

    return transformer


def panel_state_consumer(
    delimiter: str,
) -> Tuple[Consumer[str], Queue[Outcome[Callable[[PanelState], None]]]]:
    """Return a consumer that processes panel status lines."""

    def transformer(data: str) -> FlowResult[Callable[[PanelState], None]]:
        return wait_line(data, delimiter).bind(panel_state_message_transformer)

    return create_queue_consumer(transformer)
