"""Sentinel token stripping — shared between cli.py and streamlit_app.py."""

_SENTINELS = ("[SESSION:DECLINED]", "[SESSION:FAILED]")


def _strip_sentinel(reply: str) -> tuple[str, str | None]:
    """Remove a trailing sentinel token from *reply*.

    Returns (clean_text, sentinel_or_None).
    """
    stripped = reply.rstrip()
    for sentinel in _SENTINELS:
        if stripped.endswith(sentinel):
            return stripped[: -len(sentinel)].rstrip(), sentinel
    return reply, None
