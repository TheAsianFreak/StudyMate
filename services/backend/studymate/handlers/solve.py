"""solve_request -> solve_progress* -> solve_script."""

from __future__ import annotations

from studymate.protocol.backend import SolveProgress, SolveRequest, SolveScriptMessage
from studymate.router import Context, router
from studymate.services import get_services
from studymate.solve.memory import SolvedProblem
from studymate.solve.pipeline import Stage, solve


@router.on("solve_request", SolveRequest)
async def solve_request(ctx: Context, msg: SolveRequest) -> None:
    async def progress(stage: Stage, attempt: int | None, detail: str | None) -> None:
        await ctx.send(
            SolveProgress(type="solve_progress", id=msg.id, stage=stage, attempt=attempt, detail=detail)
        )

    services = get_services()
    outcome = await solve(
        services,
        image_base64=msg.image_base64,
        problem_text=msg.problem_text,
        subject_hint=msg.subject_hint,
        progress=progress,
    )
    script = outcome.script
    if not outcome.flagged and script.final_answer:
        problem = SolvedProblem(
            outcome.problem.text, script.final_answer, is_math=script.subject in (None, "math")
        )
        script = script.model_copy(update={"problem_id": services.solved.add(problem)})
    await ctx.send(SolveScriptMessage(type="solve_script", id=msg.id, script=script))
