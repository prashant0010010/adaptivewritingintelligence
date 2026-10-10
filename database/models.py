"""Typed records and shared constants for the data layer."""
from __future__ import annotations

from dataclasses import dataclass

SAMPLE_STATUSES = ("representative", "experimental", "not_representative")
FEEDBACK_ACTIONS = ("accept", "reject", "edit")


@dataclass
class ProfileRow:
    id: int
    name: str
    notes: str
    created_at: str
