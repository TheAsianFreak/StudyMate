"""ask_request -> ask_answer (study questions and casual voice conversation)."""

from __future__ import annotations

from studymate.protocol.backend import AskAnswer, AskRequest
from studymate.router import Context, router
from studymate.services import get_services
from studymate.solve.ask import answer


@router.on("ask_request", AskRequest)
async def ask_request(ctx: Context, msg: AskRequest) -> None:
    steps, _mode = await answer(get_services(), msg)
    await ctx.send(AskAnswer(type="ask_answer", id=msg.id, steps=steps))
