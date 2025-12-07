import asyncio
from contextlib import suppress
from time import monotonic


async def shell_read(
    reader: asyncio.StreamReader,
    buffer_size: int,
    *,
    buffer_period: float | None = 1 / 100,
    max_buffer_duration: float = 1 / 60,
) -> bytes:
    """Read data from a stream reader, with buffer logic to reduce the number of chunks.

    Args:
        reader: A reader instance.
        buffer_size: Maximum buffer size.
        buffer_period: Time in seconds where reads are batched, or `None` for no batching.
        max_buffer_duration: Maximum time in seconds to buffer.

    Returns:
        Bytes read. May be empty on the last read.
    """
    try:
        data = await reader.read(buffer_size)
    except OSError:
        data = b""
    if data and buffer_period is not None:
        buffer_time = monotonic() + max_buffer_duration
        with suppress(asyncio.TimeoutError):
            while len(data) < buffer_size and (time := monotonic()) < buffer_time:
                async with asyncio.timeout(min(buffer_time - time, buffer_period)):
                    try:
                        if chunk := await reader.read(buffer_size - len(data)):
                            data += chunk
                        else:
                            break
                    except OSError:
                        break
    return data
