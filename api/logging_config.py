"""M7 platform integration (follow-up): structured logging for the
INTEGRATION LAYER ONLY (api/services/*, api/routes_*). Research
scripts under experiments/ keep their own existing print()-based
logging UNCHANGED -- this module is never imported there.

Uses the stdlib `logging` module with a formatter that renders each
record as one JSON line -- easy to grep, easy to pipe into a real log
aggregator later, no new third-party dependency. Never logs raw
request bodies or file contents (only the specific fields named at
each call site: generation_id, request_id, generator, seed,
candidate_count, duration, valid_count, verification_status -- exactly
the task's own specified field list, nothing more)."""

from __future__ import annotations

import json
import logging
import sys

_LOGGER_NAME = "pulli.platform"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload)


def get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(message: str, **fields) -> None:
    get_logger().info(message, extra={"fields": fields})
