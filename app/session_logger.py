"""Structured session logging — Feature 0."""

import json
from datetime import datetime
from pathlib import Path


class SessionLogger:
    def __init__(
        self,
        session_id: str,
        logs_dir: Path,
        feedback_dir: Path,
        now: datetime,
    ) -> None:
        self._session_id = session_id
        self._logs_dir = logs_dir
        self._feedback_dir = feedback_dir
        self._date_str = now.date().isoformat()
        self._time_str = now.strftime("%H%M")
        self._started_at = now.isoformat()
        self._turns: list[dict] = []
        self._log_file = (
            logs_dir / f"{self._date_str}_{self._time_str}_{session_id}.json"
        )
        self._feedback_file = (
            feedback_dir / f"{self._date_str}_{self._time_str}_{session_id}.jsonl"
        )

    def _write_log(self, extra: dict | None = None) -> None:
        data: dict = {
            "session_id": self._session_id,
            "date": self._date_str,
            "started_at": self._started_at,
            "ended_at": None,
            "outcome": None,
            "turns": self._turns,
        }
        if extra:
            data.update(extra)
        self._log_file.write_text(json.dumps(data, indent=2))

    def record_turn(
        self,
        turn: int,
        user: str,
        reply: str,
        sentinel: str | None,
        tool_calls: list[dict],
    ) -> None:
        self._turns.append(
            {
                "turn": turn,
                "user": user,
                "reply": reply,
                "sentinel": sentinel,
                "reasoning": tool_calls,
            }
        )
        self._write_log()

    def record_feedback(self, turn: int, message: str, timestamp: datetime) -> None:
        self._feedback_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "session_id": self._session_id,
            "timestamp": timestamp.isoformat(),
            "turn": turn,
            "message": message,
        }
        with self._feedback_file.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def close(self, outcome: str, now: datetime) -> None:
        self._write_log({"ended_at": now.isoformat(), "outcome": outcome})
