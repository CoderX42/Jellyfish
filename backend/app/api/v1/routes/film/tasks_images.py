from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.runnables import Runnable
from sqlalchemy.ext.asyncio import AsyncSession

from app.chains.agents import (
    ShotFirstFramePromptAgent,
    ShotKeyFramePromptAgent,
    ShotLastFramePromptAgent,
)
from app.core.db import async_session_maker
from app.core.task_manager import DeliveryMode, SqlAlchemyTaskStore, TaskManager
from app.core.task_manager.types import TaskStatus
from app.dependencies import get_db, get_llm
from app.schemas.common import ApiResponse, success_response

from .common import (
    ShotFramePromptRequest,
    TaskCreated,
    _CreateOnlyTask,
    bind_task,
    ensure_single_bind_target,
)
from .image_requests import ShotFrameImageTaskRequest

router = APIRouter()


@router.post(
    "/tasks/shot-frame-prompts",
    response_model=ApiResponse[TaskCreated],
    status_code=201,
    summary="镜头分镜帧提示词生成（任务版）",
)
async def create_shot_frame_prompt_task(
    body: ShotFramePromptRequest,
    llm: Runnable = Depends(get_llm),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    target_type, target_id = ensure_single_bind_target(body)

    frame_type = (body.frame_type or "").strip().lower()
    if frame_type not in {"first", "last", "key"}:
        raise HTTPException(status_code=400, detail="frame_type must be one of first/last/key")
    skill_id = f"shot_{frame_type}_frame_prompt" if frame_type in {"first", "last"} else "shot_key_frame_prompt"
    if frame_type == "first":
        relation_type = "shot_first_frame_prompt"
    elif frame_type == "last":
        relation_type = "shot_last_frame_prompt"
    else:
        relation_type = "shot_key_frame_prompt"

    store = SqlAlchemyTaskStore(db)
    tm = TaskManager(store=store, strategies={})

    input_dict = body.model_dump(exclude={"project_id", "chapter_id", "shot_id", "frame_type"})
    run_args: dict = {"frame_type": frame_type, "skill_id": skill_id, "input": input_dict}

    task_record = await tm.create(task=_CreateOnlyTask(), mode=DeliveryMode.async_polling, run_args=run_args)
    await bind_task(db, task_id=task_record.id, target_type=target_type, target_id=target_id, relation_type=relation_type)

    async def _runner(task_id: str, args: dict) -> None:
        async with async_session_maker() as session:
            try:
                store2 = SqlAlchemyTaskStore(session)
                await store2.set_status(task_id, TaskStatus.running)
                await store2.set_progress(task_id, 10)

                ft = str(args.get("frame_type") or "")
                sid = str(args.get("skill_id") or "")
                inp = dict(args.get("input") or {})

                if ft == "first":
                    agent = ShotFirstFramePromptAgent(llm)
                elif ft == "last":
                    agent = ShotLastFramePromptAgent(llm)
                else:
                    agent = ShotKeyFramePromptAgent(llm)
                agent.load_skill(sid)
                result = await agent.aextract(inp)

                await store2.set_result(task_id, result.model_dump())
                await store2.set_progress(task_id, 100)
                await store2.set_status(task_id, TaskStatus.succeeded)
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                async with async_session_maker() as s2:
                    store3 = SqlAlchemyTaskStore(s2)
                    await store3.set_error(task_id, str(exc))
                    await store3.set_status(task_id, TaskStatus.failed)
                    await s2.commit()

    import asyncio

    asyncio.create_task(_runner(task_record.id, run_args))
    return success_response(TaskCreated(task_id=task_record.id), code=201)


