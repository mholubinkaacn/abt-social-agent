"""Tests for the feedback tool."""

from pathlib import Path
from unittest.mock import patch

import app.tools.feedback as fb_module

# ---------------------------------------------------------------------------
# Scenario 1 — tool request feedback written to log file
# ---------------------------------------------------------------------------


def test_tool_request_feedback_is_written_to_log_file(tmp_path: Path) -> None:
    """
    Given the agent is running and lacks a tool
    When it calls leave_feedback with a message describing what it needs
    Then the message is written to feedback-<execution_time>.log with confirmation
    """
    with patch.object(fb_module, "LOG_PATH", tmp_path / "feedback-test.log"):
        result = fb_module.leave_feedback.invoke(
            {"message": "I need a tool that books restaurants via OpenTable"}
        )

    log_file = tmp_path / "feedback-test.log"
    assert log_file.exists()
    assert "I need a tool that books restaurants via OpenTable" in log_file.read_text()
    assert "Feedback recorded" in result


# ---------------------------------------------------------------------------
# Scenario 2 — missing context feedback appended to same file
# ---------------------------------------------------------------------------


def test_missing_context_feedback_is_written_to_log_file(tmp_path: Path) -> None:
    """
    Given the agent lacks context needed to proceed
    When it calls leave_feedback with a message describing what is missing
    Then the message is appended to the same log file and a confirmation is returned
    """
    log_file = tmp_path / "feedback-test.log"
    with patch.object(fb_module, "LOG_PATH", log_file):
        result = fb_module.leave_feedback.invoke(
            {"message": "I need the team's dietary requirements before searching"}
        )

    assert log_file.exists()
    assert (
        "I need the team's dietary requirements before searching"
        in log_file.read_text()
    )
    assert "Feedback recorded" in result


# ---------------------------------------------------------------------------
# Scenario 3 — multiple feedback calls in one execution share the same file
# ---------------------------------------------------------------------------


def test_multiple_feedback_calls_append_to_the_same_file(tmp_path: Path) -> None:
    """
    Given the agent has already written one feedback entry
    When it calls leave_feedback again in the same execution
    Then both entries appear in the same log file
    """
    log_file = tmp_path / "feedback-test.log"
    with patch.object(fb_module, "LOG_PATH", log_file):
        fb_module.leave_feedback.invoke({"message": "First feedback entry"})
        fb_module.leave_feedback.invoke({"message": "Second feedback entry"})

    content = log_file.read_text()
    assert "First feedback entry" in content
    assert "Second feedback entry" in content


# ---------------------------------------------------------------------------
# Scenario 4 — storage failure returns error message
# ---------------------------------------------------------------------------


def test_storage_failure_returns_error_message(tmp_path: Path) -> None:
    """
    Given the log file cannot be written due to a permissions error
    When the agent calls leave_feedback
    Then an error message is returned describing the failure
    """
    with patch.object(fb_module, "LOG_PATH", tmp_path / "feedback-test.log"):
        with patch("pathlib.Path.open", side_effect=OSError("Permission denied")):
            result = fb_module.leave_feedback.invoke({"message": "This should fail"})

    assert "Failed to record feedback" in result
    assert "Permission denied" in result
