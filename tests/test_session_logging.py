"""Tests for structured session logging — feature 0."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.session_logger import SessionLogger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_NOW = datetime(2026, 4, 23, 9, 0, 0, tzinfo=timezone.utc)
FIXED_SESSION_ID = "aaaaaaaa-0000-0000-0000-000000000001"


def _make_logger(logs_dir: Path, feedback_dir: Path) -> "SessionLogger":
    from app.session_logger import SessionLogger

    return SessionLogger(
        session_id=FIXED_SESSION_ID,
        logs_dir=logs_dir,
        feedback_dir=feedback_dir,
        now=FIXED_NOW,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — session log file created on first turn
# ---------------------------------------------------------------------------


def test_session_log_file_created_on_first_turn(tmp_path: Path) -> None:
    """
    Given a session starts at 09:00 UTC
    When the user sends the first message and the turn is recorded
    Then a JSON log file exists in logs/ named YYYY-MM-DD_HHMM_<session_id>.json
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    logger = _make_logger(logs_dir, tmp_path / "feedback")

    logger.record_turn(
        turn=1, user="find me a pub", reply="Right away.", sentinel=None, tool_calls=[]
    )

    expected = logs_dir / f"2026-04-23_0900_{FIXED_SESSION_ID}.json"
    assert expected.exists()


# ---------------------------------------------------------------------------
# Scenario 1b — log filename includes time component
# ---------------------------------------------------------------------------


def test_log_filename_includes_start_time(tmp_path: Path) -> None:
    """
    Given a session starts at a known UTC time
    When the turn is recorded
    Then the log filename contains the session start time as HHMM
    so it is visible in a file browser without opening the file
    """
    from app.session_logger import SessionLogger

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    start_time = datetime(2026, 4, 23, 14, 37, 0, tzinfo=timezone.utc)
    logger = SessionLogger(
        session_id=FIXED_SESSION_ID,
        logs_dir=logs_dir,
        feedback_dir=tmp_path / "feedback",
        now=start_time,
    )
    logger.record_turn(turn=1, user="hi", reply="hello", sentinel=None, tool_calls=[])

    expected = logs_dir / f"2026-04-23_1437_{FIXED_SESSION_ID}.json"
    assert expected.exists()


# ---------------------------------------------------------------------------
# Scenario 2 — tool calls recorded in reasoning trace
# ---------------------------------------------------------------------------


def test_tool_calls_recorded_in_reasoning_trace(tmp_path: Path) -> None:
    """
    Given the agent calls a tool during a turn
    When the turn is recorded
    Then the tool name, input, and output appear in that turn's reasoning trace
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    logger = _make_logger(logs_dir, tmp_path / "feedback")

    tool_calls = [
        {
            "tool": "search_places",
            "input": {"query": "pubs in Shoreditch"},
            "output": "The Owl | 1 Main St",
        }
    ]
    logger.record_turn(
        turn=1,
        user="find a pub",
        reply="Here are some options.",
        sentinel=None,
        tool_calls=tool_calls,
    )

    log_file = logs_dir / f"2026-04-23_0900_{FIXED_SESSION_ID}.json"
    data = json.loads(log_file.read_text())
    assert data["turns"][0]["reasoning"] == tool_calls


# ---------------------------------------------------------------------------
# Scenario 3 — leave_feedback writes JSONL entry with session context
# ---------------------------------------------------------------------------


def test_feedback_written_to_jsonl_with_session_context(tmp_path: Path) -> None:
    """
    Given the agent calls leave_feedback during turn 2
    When record_feedback is called on the logger
    Then a JSONL line is appended to feedback/YYYY-MM-DD_<session_id>.jsonl
    containing the session ID, timestamp, turn number, and message
    """
    feedback_dir = tmp_path / "feedback"
    feedback_dir.mkdir()
    logger = _make_logger(tmp_path / "logs", feedback_dir)

    logger.record_feedback(
        turn=2, message="No pricing tool available.", timestamp=FIXED_NOW
    )

    expected = feedback_dir / f"2026-04-23_0900_{FIXED_SESSION_ID}.jsonl"
    assert expected.exists()
    entry = json.loads(expected.read_text().strip())
    assert entry["session_id"] == FIXED_SESSION_ID
    assert entry["turn"] == 2
    assert entry["message"] == "No pricing tool available."
    assert entry["timestamp"] == FIXED_NOW.isoformat()


# ---------------------------------------------------------------------------
# Scenario 4 — session closed with outcome and ended_at
# ---------------------------------------------------------------------------


def test_session_closed_with_outcome_and_ended_at(tmp_path: Path) -> None:
    """
    Given a session ends with outcome 'booked'
    When close() is called
    Then the session log contains the outcome and a non-null ended_at timestamp
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    logger = _make_logger(logs_dir, tmp_path / "feedback")

    logger.record_turn(
        turn=1, user="book it", reply="Done!", sentinel=None, tool_calls=[]
    )
    logger.close(outcome="booked", now=FIXED_NOW)

    log_file = logs_dir / f"2026-04-23_0900_{FIXED_SESSION_ID}.json"
    data = json.loads(log_file.read_text())
    assert data["outcome"] == "booked"
    assert data["ended_at"] == FIXED_NOW.isoformat()


# ---------------------------------------------------------------------------
# Scenario 5 — multiple sessions produce separate files with shared session ID
# ---------------------------------------------------------------------------


def test_multiple_sessions_produce_separate_files(tmp_path: Path) -> None:
    """
    Given two sessions run on the same day with different session IDs
    When both record a turn and close
    Then two separate log files exist, each with its own session ID in the filename
    And each file's session_id field matches its filename
    """
    from app.session_logger import SessionLogger

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    for i, sid in enumerate(["session-aaa", "session-bbb"], start=1):
        logger = SessionLogger(
            session_id=sid,
            logs_dir=logs_dir,
            feedback_dir=tmp_path / "feedback",
            now=FIXED_NOW,
        )
        logger.record_turn(
            turn=1, user=f"message {i}", reply="Ok.", sentinel=None, tool_calls=[]
        )
        logger.close(outcome="abandoned", now=FIXED_NOW)

    files = sorted(logs_dir.glob("*.json"))
    assert len(files) == 2
    for f in files:
        data = json.loads(f.read_text())
        assert data["session_id"] in f.name


# ---------------------------------------------------------------------------
# Scenario 6 — session log contains started_at, date, and session_id header
# ---------------------------------------------------------------------------


def test_session_log_contains_correct_header_fields(tmp_path: Path) -> None:
    """
    Given a session starts with a known time and session ID
    When a turn is recorded
    Then the log file contains the correct session_id, date, and started_at fields
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    logger = _make_logger(logs_dir, tmp_path / "feedback")

    logger.record_turn(turn=1, user="hello", reply="Hi.", sentinel=None, tool_calls=[])

    log_file = logs_dir / f"2026-04-23_0900_{FIXED_SESSION_ID}.json"
    data = json.loads(log_file.read_text())
    assert data["session_id"] == FIXED_SESSION_ID
    assert data["date"] == "2026-04-23"
    assert data["started_at"] == FIXED_NOW.isoformat()
