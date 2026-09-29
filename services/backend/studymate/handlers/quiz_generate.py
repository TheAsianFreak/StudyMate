"""generate_quiz -> quiz_progress* -> quiz_items (verified items only)."""

from __future__ import annotations

from studymate.errors import UserFacingError
from studymate.protocol.backend import GenerateQuiz, QuizItems, QuizProgress
from studymate.quiz.generate import generate_quiz
from studymate.router import Context, router
from studymate.services import get_services
from studymate.solve.safety import is_unsafe, is_unsafe_request


@router.on("generate_quiz", GenerateQuiz)
async def generate_quiz_handler(ctx: Context, msg: GenerateQuiz) -> None:
    async def progress(done: int, total: int) -> None:
        await ctx.send(QuizProgress(type="quiz_progress", id=msg.id, done=done, total=total))

    topic = f"{msg.subject} {msg.unit or ''}"
    if is_unsafe_request(topic) or is_unsafe(topic):
        raise UserFacingError("unsafe_request", "학습 목적이 아닌 요청은 도와드릴 수 없어요.")
    await progress(0, msg.count)
    items = await generate_quiz(get_services(), msg, progress)
    await ctx.send(QuizItems(type="quiz_items", id=msg.id, items=items))
