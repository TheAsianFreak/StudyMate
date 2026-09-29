"""Learning-record interface shared by the quiz generator and the quiz/review handlers.

All functions are synchronous and short; async callers wrap them in `asyncio.to_thread`
(`save_quiz_items` is cheap enough to call directly).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from studymate.db import get_db, iso, utc_now
from studymate.errors import UserFacingError
from studymate.learning import review
from studymate.protocol.backend import QuizItem, ReviewCard, WrongNote

if TYPE_CHECKING:
    from studymate.services import Services


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def save_quiz_items(services: Services, items: list[QuizItem]) -> None:
    """Persists generated (verified) items so `quiz_answer` can grade them later."""
    if not items:
        return
    now = iso(utc_now())
    with get_db(services).write() as conn:
        conn.executemany(
            "INSERT INTO quiz_items (item_id, item, created_at) VALUES (?, ?, ?)"
            " ON CONFLICT(item_id) DO UPDATE SET item = excluded.item",  # not REPLACE: that would cascade
            [(it.item_id, it.model_dump_json(exclude_none=True), now) for it in items],
        )


def recent_questions(services: Services, subject: str, unit: str | None, limit: int = 30) -> list[str]:
    """Questions of recent quizzes on the same subject and unit, newest first (so a new
    quiz does not ask them again)."""
    with get_db(services).read() as conn:
        rows = conn.execute(
            "SELECT json_extract(item, '$.question_latex') FROM quiz_items"
            " WHERE json_extract(item, '$.subject') = ?"
            " AND IFNULL(json_extract(item, '$.unit'), '') = ?"
            " ORDER BY created_at DESC LIMIT ?",
            (subject, unit or "", limit),
        ).fetchall()
    return [str(r[0]) for r in rows if r[0]]


def get_quiz_item(services: Services, item_id: str) -> QuizItem | None:
    with get_db(services).read() as conn:
        row = conn.execute("SELECT item FROM quiz_items WHERE item_id = ?", (item_id,)).fetchone()
    return QuizItem.model_validate_json(row[0]) if row else None


def record_answer(
    services: Services, item: QuizItem, answer: str, correct: bool, now: datetime | None = None
) -> str | None:
    """Stores the attempt; a wrong answer creates (or refreshes) the item's wrong note and
    review card. Returns the note id for wrong answers."""
    now = now or utc_now()
    stamp = iso(now)
    with get_db(services).write() as conn:
        conn.execute(
            "INSERT INTO attempts (item_id, answer, correct, at) VALUES (?, ?, ?, ?)",
            (item.item_id, answer, int(correct), stamp),
        )
        if correct:
            return None
        row = conn.execute("SELECT note_id FROM wrong_notes WHERE item_id = ?", (item.item_id,)).fetchone()
        if row is None:
            note_id, card_id = _new_id("n"), _new_id("c")
            card = review.new_card(now)
            conn.execute(
                "INSERT INTO wrong_notes (note_id, item_id, user_answer, created_at) VALUES (?, ?, ?, ?)",
                (note_id, item.item_id, answer, stamp),
            )
            conn.execute(
                "INSERT INTO review_cards (card_id, note_id, item_id, fsrs, due, state, reps, lapses,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)",
                (card_id, note_id, item.item_id, card.fsrs_json, iso(card.due), card.state, stamp),
            )
            return str(note_id)
        note_id = str(row[0])
        conn.execute("UPDATE wrong_notes SET user_answer = ? WHERE note_id = ?", (answer, note_id))
        card_row = conn.execute("SELECT card_id FROM review_cards WHERE note_id = ?", (note_id,)).fetchone()
        if card_row is not None:
            _apply_rating(conn, str(card_row[0]), 1, now)  # missed again: FSRS "again"
        return note_id


def list_wrong_notes(services: Services) -> list[WrongNote]:
    with get_db(services).read() as conn:
        rows = conn.execute(
            "SELECT n.note_id, n.user_answer, n.created_at, c.card_id, q.item"
            " FROM wrong_notes n JOIN quiz_items q ON q.item_id = n.item_id"
            " JOIN review_cards c ON c.note_id = n.note_id"
            " ORDER BY n.created_at DESC, n.note_id"
        ).fetchall()
    return [
        WrongNote(
            note_id=r["note_id"],
            item=QuizItem.model_validate_json(r["item"]),
            user_answer=r["user_answer"],
            created_at=r["created_at"],
            card_id=r["card_id"],
        )
        for r in rows
    ]


def delete_wrong_note(services: Services, note_id: str) -> bool:
    """Deletes the note; its review card and review logs cascade."""
    with get_db(services).write() as conn:
        return conn.execute("DELETE FROM wrong_notes WHERE note_id = ?", (note_id,)).rowcount > 0


def due_cards(services: Services, now: datetime | None = None) -> tuple[list[ReviewCard], str | None]:
    """Cards due at `now` (oldest first) and the due time of the earliest future card."""
    stamp = iso(now or utc_now())
    with get_db(services).read() as conn:
        rows = conn.execute(
            "SELECT c.card_id, c.due, c.state, c.reps, c.lapses, q.item"
            " FROM review_cards c JOIN quiz_items q ON q.item_id = c.item_id"
            " WHERE c.due <= ? ORDER BY c.due, c.card_id",
            (stamp,),
        ).fetchall()
        nxt = conn.execute("SELECT MIN(due) FROM review_cards WHERE due > ?", (stamp,)).fetchone()[0]
    cards = [
        ReviewCard(
            card_id=r["card_id"],
            item=QuizItem.model_validate_json(r["item"]),
            due=r["due"],
            state=r["state"],
            reps=r["reps"],
            lapses=r["lapses"],
        )
        for r in rows
    ]
    return cards, nxt


def grade_card(services: Services, card_id: str, rating: int, now: datetime | None = None) -> str:
    """Schedules the card's next review from a 1..4 rating; returns the new due time."""
    if rating not in (1, 2, 3, 4):
        raise UserFacingError("invalid_rating", "평가 값은 1~4 사이여야 합니다.")
    with get_db(services).write() as conn:
        return _apply_rating(conn, card_id, rating, now or utc_now())


def _apply_rating(conn: sqlite3.Connection, card_id: str, rating: int, now: datetime) -> str:
    row = conn.execute("SELECT fsrs FROM review_cards WHERE card_id = ?", (card_id,)).fetchone()
    if row is None:
        raise UserFacingError("unknown_card", "복습 카드를 찾을 수 없습니다.")
    scheduled = review.rate(row[0], rating, now)
    due = iso(scheduled.due)
    conn.execute(
        "UPDATE review_cards SET fsrs = ?, due = ?, state = ?, reps = reps + 1, lapses = lapses + ?"
        " WHERE card_id = ?",
        (scheduled.fsrs_json, due, scheduled.state, int(scheduled.lapsed), card_id),
    )
    conn.execute(
        "INSERT INTO review_logs (card_id, rating, reviewed_at) VALUES (?, ?, ?)", (card_id, rating, iso(now))
    )
    return due
