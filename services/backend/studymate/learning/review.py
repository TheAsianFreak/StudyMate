"""FSRS scheduling (py-fsrs) for wrong-answer review cards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Literal

from fsrs import Card, Rating, Scheduler, State

CardState = Literal["learning", "review", "relearning"]

_STATE_NAMES: dict[State, CardState] = {
    State.Learning: "learning",
    State.Review: "review",
    State.Relearning: "relearning",
}


@dataclass(frozen=True)
class Scheduled:
    fsrs_json: str
    due: datetime
    state: CardState
    lapsed: bool  # a review-state card was forgotten (rating Again)


@lru_cache(maxsize=1)
def scheduler() -> Scheduler:
    # FSRS defaults: 90% desired retention, 1m/10m learning steps, 10m relearning step.
    return Scheduler()


def new_card(now: datetime) -> Scheduled:
    """A fresh card due immediately (first review in the learning steps)."""
    card = Card(due=now)
    return Scheduled(card.to_json(), card.due, _STATE_NAMES[card.state], False)


def rate(fsrs_json: str, rating: int, now: datetime) -> Scheduled:
    """Applies a 1..4 rating (again, hard, good, easy) at `now`."""
    card = Card.from_json(fsrs_json)
    before = card.state
    updated, _log = scheduler().review_card(card, Rating(rating), now)
    lapsed = before == State.Review and rating == Rating.Again
    return Scheduled(updated.to_json(), updated.due, _STATE_NAMES[updated.state], lapsed)
