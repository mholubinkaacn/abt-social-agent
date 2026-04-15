"""Tests for model-call retry behaviour on 503 high-demand errors."""

from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from app.retry import invoke_with_exponential_backoff

_REQUEST = httpx.Request("POST", "https://example.com")


def _503_error() -> openai.InternalServerError:
    return openai.InternalServerError(
        "503 Model unavailable",
        response=httpx.Response(503, request=_REQUEST),
        body=None,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — retry succeeds
# ---------------------------------------------------------------------------


def test_model_returns_result_after_one_503_retry() -> None:
    """
    Given the model returns a 503 error on the first call, then succeeds
    When the model is invoked
    Then the successful result is returned after one retry
    """
    model = MagicMock(side_effect=[_503_error(), "response"])

    with patch("app.retry.time.sleep"):
        result = invoke_with_exponential_backoff(model)

    assert result == "response"
    assert model.call_count == 2


# ---------------------------------------------------------------------------
# Scenario 2 — retries exhausted
# ---------------------------------------------------------------------------


def test_503_error_is_raised_after_all_retries_exhausted() -> None:
    """
    Given the model keeps returning 503 errors
    When all retries are exhausted
    Then the 503 error is raised to the caller
    """
    model = MagicMock(side_effect=_503_error())

    with patch("app.retry.time.sleep"):
        with pytest.raises(openai.InternalServerError) as exc_info:
            invoke_with_exponential_backoff(model, max_retries=3)

    assert exc_info.value.status_code == 503
    assert model.call_count == 4  # 1 initial + 3 retries


# ---------------------------------------------------------------------------
# Scenario 3 — non-503 errors are not retried
# ---------------------------------------------------------------------------


def test_non_overload_server_error_is_raised_immediately_without_retry() -> None:
    """
    Given the model returns a 500 (non-overload) error
    When the model is invoked
    Then the error is raised immediately without any retry
    """
    error_500 = openai.InternalServerError(
        "500 Internal Server Error",
        response=httpx.Response(500, request=_REQUEST),
        body=None,
    )
    model = MagicMock(side_effect=error_500)

    with patch("app.retry.time.sleep") as mock_sleep:
        with pytest.raises(openai.InternalServerError) as exc_info:
            invoke_with_exponential_backoff(model, max_retries=3)

    assert exc_info.value.status_code == 500
    model.assert_called_once()
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 4 — exponential backoff timing
# ---------------------------------------------------------------------------


def test_each_retry_waits_twice_as_long_as_the_previous() -> None:
    """
    Given the model returns 503 errors three times then succeeds
    When the model is invoked with base_delay=1s
    Then base waits double each retry: 1s, 2s, 4s (jitter excluded)
    """
    model = MagicMock(
        side_effect=[_503_error(), _503_error(), _503_error(), "response"]
    )

    with patch("app.retry.time.sleep") as mock_sleep:
        with patch("app.retry.random.uniform", return_value=0.0):
            invoke_with_exponential_backoff(model, max_retries=3, base_delay=1.0)

    actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert actual_delays == [1.0, 2.0, 4.0]


# ---------------------------------------------------------------------------
# Scenario 5 — delay capped at max_delay
# ---------------------------------------------------------------------------


def test_retry_delay_never_exceeds_configured_maximum() -> None:
    """
    Given the model returns 503 errors with many retries configured
    When max_delay is set to 30s
    Then no individual wait exceeds 30s (including jitter)
    """
    # base_delay=10s → uncapped delays would be 10, 20, 40, 80; capped at 30
    model = MagicMock(
        side_effect=[_503_error(), _503_error(), _503_error(), _503_error(), "response"]
    )

    with patch("app.retry.time.sleep") as mock_sleep:
        with patch("app.retry.random.uniform", return_value=0.0):
            invoke_with_exponential_backoff(
                model, max_retries=4, base_delay=10.0, max_delay=30.0
            )

    actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert actual_delays == [10.0, 20.0, 30.0, 30.0]
    assert all(d <= 30.0 for d in actual_delays)
