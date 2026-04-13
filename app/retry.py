"""Retry utilities for model calls that fail due to transient high-demand errors."""

import logging
import time
from typing import Any, Callable

import openai

logger = logging.getLogger(__name__)


def invoke_with_exponential_backoff(
    invoke_fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    **kwargs: Any,
) -> Any:
    """Call *invoke_fn* with exponential backoff on 503 model-overload errors.

    Args:
        invoke_fn: The callable to invoke (e.g. ``llm.invoke``).
        *args: Positional arguments forwarded to *invoke_fn*.
        max_retries: Maximum number of retry attempts after the first failure.
        base_delay: Initial wait in seconds; doubles on each subsequent retry.
        max_delay: Upper bound on the wait between retries.
        **kwargs: Keyword arguments forwarded to *invoke_fn*.
    """
    for attempt in range(max_retries + 1):
        try:
            return invoke_fn(*args, **kwargs)
        except openai.InternalServerError as exc:
            if exc.status_code != 503 or attempt >= max_retries:
                raise
            delay = min(base_delay * (2**attempt), max_delay)
            logger.warning(
                "Model overloaded (503) — retrying in %.1fs (attempt %d/%d)",
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)
