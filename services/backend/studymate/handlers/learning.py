"""quiz_answer / wrong_notes_get / wrong_note_delete / review_due_get / review_grade."""

from __future__ import annotations

import asyncio

from studymate.errors import UserFacingError
from studymate.learning import store
from studymate.learning.grade import display_answer, grade
from studymate.protocol.backend import (
    QuizAnswer,
    QuizGraded,
    ReviewDue,
    ReviewDueGet,
    ReviewGrade,
    ReviewGraded,
    WrongNoteDelete,
    WrongNotes,
    WrongNotesGet,
)
from studymate.router import Context, router
from studymate.services import Services, get_services


async def _wrong_notes(services: Services, request_id: str | None) -> WrongNotes:
    notes = await asyncio.to_thread(store.list_wrong_notes, services)
    return WrongNotes(type="wrong_notes", id=request_id, notes=notes)


@router.on("quiz_answer", QuizAnswer)
async def quiz_answer(ctx: Context, msg: QuizAnswer) -> None:
    services = get_services()
    item = await asyncio.to_thread(store.get_quiz_item, services, msg.item_id)
    if item is None:
        raise UserFacingError("unknown_item", "문항을 찾을 수 없습니다. 문제를 다시 받아주세요.")
    correct = await asyncio.to_thread(grade, item, msg.answer)
    note_id = await asyncio.to_thread(store.record_answer, services, item, msg.answer, correct)
    await ctx.send(
        QuizGraded(
            type="quiz_graded",
            id=msg.id,
            item_id=item.item_id,
            correct=correct,
            correct_answer=display_answer(item),
            note_id=note_id,
        )
    )


@router.on("wrong_notes_get", WrongNotesGet)
async def wrong_notes_get(ctx: Context, msg: WrongNotesGet) -> None:
    await ctx.send(await _wrong_notes(get_services(), msg.id))


@router.on("wrong_note_delete", WrongNoteDelete)
async def wrong_note_delete(ctx: Context, msg: WrongNoteDelete) -> None:
    services = get_services()
    await asyncio.to_thread(store.delete_wrong_note, services, msg.note_id)  # idempotent
    await ctx.send(await _wrong_notes(services, msg.id))


@router.on("review_due_get", ReviewDueGet)
async def review_due_get(ctx: Context, msg: ReviewDueGet) -> None:
    cards, next_due = await asyncio.to_thread(store.due_cards, get_services())
    await ctx.send(ReviewDue(type="review_due", id=msg.id, cards=cards, next_due=next_due))


@router.on("review_grade", ReviewGrade)
async def review_grade(ctx: Context, msg: ReviewGrade) -> None:
    next_due = await asyncio.to_thread(store.grade_card, get_services(), msg.card_id, msg.rating)
    await ctx.send(ReviewGraded(type="review_graded", id=msg.id, card_id=msg.card_id, next_due=next_due))
