from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_db import make_services

from studymate.db import get_db, parse_iso, utc_now
from studymate.errors import UserFacingError
from studymate.learning import store
from studymate.learning.review import new_card, rate
from studymate.protocol.backend import QuizItem, QuizSource, ScriptStep, Solution


def quiz_item(item_id: str = "q_1", answer: str = "8", choices: list[str] | None = None) -> QuizItem:
    return QuizItem(
        item_id=item_id,
        subject="수학",
        unit="일차방정식",
        difficulty="normal",
        question_latex="2x - 5 = 11 일 때 x의 값은?",
        choices=choices,
        answer=answer,
        solution=Solution(steps=[ScriptStep(say="양변에 5를 더해요.", write="2x = 16")]),
        confidence="high",
        source=QuizSource(doc_id="d_1", page=3, excerpt="일차방정식의 풀이"),
    )


def test_quiz_items_round_trip_and_upsert(tmp_path: Path) -> None:
    services, _ = make_services(tmp_path)
    item = quiz_item()
    store.save_quiz_items(services, [item, quiz_item("q_2")])
    store.save_quiz_items(services, [])
    assert store.get_quiz_item(services, "q_1") == item
    assert store.get_quiz_item(services, "missing") is None

    note_id = store.record_answer(services, item, "7", correct=False)
    assert note_id
    changed = item.model_copy(update={"answer": "x=8"})
    store.save_quiz_items(services, [changed])  # upsert must not cascade-delete the note
    assert store.get_quiz_item(services, "q_1") == changed
    assert [n.note_id for n in store.list_wrong_notes(services)] == [note_id]
    services.shutdown()


def test_wrong_answer_creates_note_and_due_card(tmp_path: Path) -> None:
    services, _ = make_services(tmp_path)
    item = quiz_item()
    store.save_quiz_items(services, [item])
    assert store.record_answer(services, item, "8", correct=True) is None
    assert store.list_wrong_notes(services) == []

    now = utc_now()
    note_id = store.record_answer(services, item, "7", correct=False, now=now)
    notes = store.list_wrong_notes(services)
    assert len(notes) == 1
    note = notes[0]
    assert note.note_id == note_id and note.user_answer == "7" and note.item == item
    assert note.created_at.endswith("Z")

    cards, next_due = store.due_cards(services, now)
    assert [c.card_id for c in cards] == [note.card_id]
    assert cards[0].state == "learning" and cards[0].reps == 0 and cards[0].lapses == 0
    assert next_due is None

    # the same item missed again reuses the note and card (FSRS "again")
    again = store.record_answer(services, item, "6", correct=False, now=now + timedelta(minutes=1))
    assert again == note_id
    notes = store.list_wrong_notes(services)
    assert len(notes) == 1 and notes[0].user_answer == "6"
    with get_db(services).read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 3
        assert conn.execute("SELECT reps FROM review_cards").fetchone()[0] == 1
    services.shutdown()


def test_review_grading_moves_due_forward(tmp_path: Path) -> None:
    services, _ = make_services(tmp_path)
    item = quiz_item()
    store.save_quiz_items(services, [item])
    now = utc_now()
    store.record_answer(services, item, "7", correct=False, now=now)
    card_id = store.list_wrong_notes(services)[0].card_id

    t = now
    dues = []
    for _ in range(4):  # "good" each time the card comes due
        due = parse_iso(store.grade_card(services, card_id, 3, now=t))
        assert due > t
        dues.append(due)
        t = due
    intervals = [(b - a).total_seconds() for a, b in zip([now, *dues], dues, strict=False)]
    assert intervals[-1] > intervals[0]  # spacing grows
    cards, next_due = store.due_cards(services, now + timedelta(seconds=1))
    assert cards == []
    assert next_due is not None and parse_iso(next_due) == dues[-1]

    card = store.due_cards(services, t)[0][0]
    assert card.state == "review" and card.reps == 4 and card.lapses == 0
    store.grade_card(services, card_id, 1, now=t)  # forgot a review card -> lapse
    with get_db(services).read() as conn:
        row = conn.execute("SELECT state, lapses FROM review_cards").fetchone()
        assert (row["state"], row["lapses"]) == ("relearning", 1)
        assert conn.execute("SELECT COUNT(*) FROM review_logs").fetchone()[0] == 5

    with pytest.raises(UserFacingError) as e:
        store.grade_card(services, "c_missing", 3)
    assert e.value.code == "unknown_card"
    with pytest.raises(UserFacingError):
        store.grade_card(services, card_id, 5)
    services.shutdown()


def test_delete_wrong_note_removes_card(tmp_path: Path) -> None:
    services, _ = make_services(tmp_path)
    item = quiz_item()
    store.save_quiz_items(services, [item])
    note_id = store.record_answer(services, item, "7", correct=False)
    assert note_id
    card_id = store.list_wrong_notes(services)[0].card_id
    store.grade_card(services, card_id, 3)
    assert store.delete_wrong_note(services, note_id)
    assert not store.delete_wrong_note(services, note_id)
    assert store.list_wrong_notes(services) == []
    with get_db(services).read() as conn:
        for table in ("review_cards", "review_logs", "wrong_notes"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 1  # history kept
    services.shutdown()


def test_fsrs_wrapper() -> None:
    now = utc_now()
    card = new_card(now)
    assert card.due == now and card.state == "learning"
    hard = rate(card.fsrs_json, 2, now)
    easy = rate(card.fsrs_json, 4, now)
    assert now < hard.due < easy.due
    assert easy.state == "review"


def test_learning_handlers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    services, _ = make_services(tmp_path)
    monkeypatch.setattr("studymate.services._services", services)
    store.save_quiz_items(
        services, [quiz_item("q_mc", "8", ["6", "7", "8", "9"]), quiz_item("q_free", "x=8")]
    )
    from studymate.main import app

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "quiz_answer", "id": "a1", "item_id": "q_mc", "answer": "③"})
        assert ws.receive_json() == {
            "type": "quiz_graded",
            "id": "a1",
            "item_id": "q_mc",
            "correct": True,
            "correct_answer": "8",
        }
        ws.send_json({"type": "quiz_answer", "id": "a2", "item_id": "q_free", "answer": "x = -8"})
        graded = ws.receive_json()
        assert graded["correct"] is False and graded["correct_answer"] == "x=8" and graded["note_id"]

        ws.send_json({"type": "quiz_answer", "id": "a3", "item_id": "q_nope", "answer": "1"})
        err = ws.receive_json()
        assert (err["type"], err["id"], err["code"]) == ("error", "a3", "unknown_item")

        ws.send_json({"type": "wrong_notes_get", "id": "w1"})
        notes = ws.receive_json()
        assert notes["type"] == "wrong_notes" and notes["id"] == "w1"
        assert [n["note_id"] for n in notes["notes"]] == [graded["note_id"]]
        assert notes["notes"][0]["item"]["item_id"] == "q_free"
        assert notes["notes"][0]["user_answer"] == "x = -8"

        ws.send_json({"type": "review_due_get", "id": "r1"})
        due = ws.receive_json()
        assert due["type"] == "review_due" and len(due["cards"]) == 1 and "next_due" not in due
        card = due["cards"][0]
        assert card["card_id"] == notes["notes"][0]["card_id"] and card["state"] == "learning"

        ws.send_json({"type": "review_grade", "id": "g1", "card_id": card["card_id"], "rating": 3})
        graded_card = ws.receive_json()
        assert graded_card["type"] == "review_graded" and graded_card["card_id"] == card["card_id"]
        assert parse_iso(graded_card["next_due"]) > utc_now()

        ws.send_json({"type": "review_due_get", "id": "r2"})
        due = ws.receive_json()
        assert due["cards"] == [] and due["next_due"] == graded_card["next_due"]

        ws.send_json({"type": "review_grade", "id": "g2", "card_id": card["card_id"], "rating": 5})
        assert ws.receive_json()["code"] == "invalid_message"
        ws.send_json({"type": "review_grade", "id": "g3", "card_id": "c_nope", "rating": 3})
        assert ws.receive_json()["code"] == "unknown_card"

        ws.send_json({"type": "wrong_note_delete", "id": "x1", "note_id": graded["note_id"]})
        assert ws.receive_json() == {"type": "wrong_notes", "id": "x1", "notes": []}
        ws.send_json({"type": "review_due_get"})
        assert ws.receive_json() == {"type": "review_due", "cards": []}
