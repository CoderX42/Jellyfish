"""影视技能 API：实体抽取、分镜抽取。"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.skills_runtime import (
    FilmEntityExtractor,
    FilmShotlistStoryboarder,
    FilmEntityExtractionResult,
    FilmShotlistResult,
)
from app.core.task_manager import DeliveryMode, SqlAlchemyTaskStore, TaskManager
from app.core.task_manager.types import TaskStatus
from app.core.db import async_session_maker
from app.dependencies import get_llm
from app.dependencies import get_db
from app.models.studio import Chapter, Project, Shot
from app.models.task import GenerationTask
from app.models.task_links import (
    ChapterGenerationTaskLink,
    ProjectGenerationTaskLink,
    ShotGenerationTaskLink,
)
from app.schemas.common import ApiResponse, success_response

router = APIRouter()

# ---------- 请求体 ----------


class TextChunkInput(BaseModel):
    """单个文本块。"""

    chunk_id: str = Field(..., description="块 ID，如 chapter1_p03")
    text: str = Field(..., description="原文内容")


class EntityExtractRequest(BaseModel):
    """实体抽取请求。"""

    source_id: str = Field(..., description="小说/章节标识，如 novel_ch01")
    language: str | None = Field(None, description="语言，如 zh / en")
    chunks: list[TextChunkInput] = Field(..., description="文本块列表")


class ShotlistExtractRequest(BaseModel):
    """分镜抽取请求。"""

    source_id: str = Field(..., description="小说/章节标识")
    source_title: str | None = Field(None, description="书名/章节名")
    language: str | None = Field(None, description="语言，如 zh / en")
    chunks: list[TextChunkInput] = Field(..., description="文本块列表")

class BindTarget(BaseModel):
    """任务绑定对象：三选一。"""

    project_id: str | None = Field(None, description="绑定项目 ID（可选）")
    chapter_id: str | None = Field(None, description="绑定章节 ID（可选）")
    shot_id: str | None = Field(None, description="绑定镜头 ID（可选）")


class EntityExtractTaskRequest(EntityExtractRequest, BindTarget):
    """实体抽取任务请求：创建任务并绑定到 project/chapter/shot。"""


class ShotlistExtractTaskRequest(ShotlistExtractRequest, BindTarget):
    """分镜抽取任务请求：创建任务并绑定到 project/chapter/shot。"""


class TaskCreated(BaseModel):
    task_id: str = Field(..., description="任务 ID")


class TaskStatusRead(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)


class TaskResultRead(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    result: dict | None = None
    error: str = ""


class TaskLinkAdoptRequest(BindTarget):
    """更新采用状态请求：task_id + 三选一绑定对象（project_id/chapter_id/shot_id）。"""

    task_id: str = Field(..., description="任务 ID")


class TaskLinkAdoptRead(BaseModel):
    """采用状态更新结果。"""

    task_id: str
    link_type: str = Field(..., description="project | chapter | shot")
    entity_id: str = Field(..., description="项目/章节/镜头 ID")
    is_adopted: bool = Field(..., description="是否采用（仅可正向变更为 true）")


class _CreateOnlyTask:
    """仅用于 TaskManager.create：提供 __class__.__name__，避免传入 lambda。"""

    async def run(self, *args: object, **kwargs: object):  # noqa: ANN001, ANN003
        return None

    async def status(self) -> dict[str, object]:
        return {}

    async def is_done(self) -> bool:
        return False

    async def get_result(self) -> object:
        return None


# ---------- 端点 ----------


@router.post(
    "/extract/entities",
    response_model=ApiResponse[FilmEntityExtractionResult],
    summary="关键信息抽取",
    description="从小说文本中抽取人物、地点、道具，忠实原文、可追溯证据。",
)
def extract_entities(
    body: EntityExtractRequest,
    llm: Runnable = Depends(get_llm),
) -> ApiResponse[FilmEntityExtractionResult]:
    """FilmEntityExtractor：人物/地点/道具抽取。"""
    extractor = FilmEntityExtractor(llm)
    extractor.load_skill("film_entity_extractor")
    chunks_json = json.dumps(
        [{"chunk_id": c.chunk_id, "text": c.text} for c in body.chunks],
        ensure_ascii=False,
    )
    result = extractor.extract(
        {
            "source_id": body.source_id,
            "language": body.language or "zh",
            "chunks_json": chunks_json,
        }
    )
    return success_response(result)


@router.post(
    "/extract/shotlist",
    response_model=ApiResponse[FilmShotlistResult],
    summary="分镜抽取",
    description="将小说片段转为可拍镜头表（景别/机位/运镜/转场/VFX）。",
)
def extract_shotlist(
    body: ShotlistExtractRequest,
    llm: Runnable = Depends(get_llm),
) -> ApiResponse[FilmShotlistResult]:
    """FilmShotlistStoryboarder：场景/镜头/转场抽取。"""
    storyboarder = FilmShotlistStoryboarder(llm)
    storyboarder.load_skill("film_shotlist")
    chunks_json = json.dumps(
        [{"chunk_id": c.chunk_id, "text": c.text} for c in body.chunks],
        ensure_ascii=False,
    )
    result = storyboarder.extract(
        {
            "source_id": body.source_id,
            "source_title": body.source_title or "",
            "language": body.language or "zh",
            "chunks_json": chunks_json,
        }
    )
    return success_response(result)


def _ensure_single_bind_target(body: BindTarget) -> tuple[str, str]:
    targets = [
        ("project", body.project_id),
        ("chapter", body.chapter_id),
        ("shot", body.shot_id),
    ]
    provided = [(t, v) for (t, v) in targets if v]
    if len(provided) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide exactly one of project_id/chapter_id/shot_id",
        )
    return provided[0][0], provided[0][1]  # type: ignore[return-value]


async def _bind_task(
    db: AsyncSession,
    *,
    task_id: str,
    target_type: str,
    target_id: str,
    relation_type: str,
) -> None:
    if target_type == "project":
        if await db.get(Project, target_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        db.add(ProjectGenerationTaskLink(project_id=target_id, task_id=task_id, relation_type=relation_type))
        return
    if target_type == "chapter":
        if await db.get(Chapter, target_id) is None:
            raise HTTPException(status_code=404, detail="Chapter not found")
        db.add(ChapterGenerationTaskLink(chapter_id=target_id, task_id=task_id, relation_type=relation_type))
        return
    if target_type == "shot":
        if await db.get(Shot, target_id) is None:
            raise HTTPException(status_code=404, detail="Shot not found")
        db.add(ShotGenerationTaskLink(shot_id=target_id, task_id=task_id, relation_type=relation_type))
        return
    raise HTTPException(status_code=400, detail="Invalid bind target type")


@router.post(
    "/tasks/entities",
    response_model=ApiResponse[TaskCreated],
    status_code=status.HTTP_201_CREATED,
    summary="关键信息抽取（任务版）",
)
async def create_entity_extract_task(
    body: EntityExtractTaskRequest,
    llm: Runnable = Depends(get_llm),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    target_type, target_id = _ensure_single_bind_target(body)

    store = SqlAlchemyTaskStore(db)
    tm = TaskManager(
        store=store,
        strategies={},  # create 不依赖策略；执行在后台协程中完成
    )

    chunks_json = json.dumps([{"chunk_id": c.chunk_id, "text": c.text} for c in body.chunks], ensure_ascii=False)
    task_record = await tm.create(
        task=_CreateOnlyTask(),  # BaseTask 仅用于记录 task_class
        mode=DeliveryMode.async_polling,
        run_args={
            "source_id": body.source_id,
            "language": body.language or "zh",
            "chunks_json": chunks_json,
        },
    )
    await _bind_task(db, task_id=task_record.id, target_type=target_type, target_id=target_id, relation_type="entities")

    async def _runner(task_id: str, input_dict: dict) -> None:
        async with async_session_maker() as session:
            try:
                store2 = SqlAlchemyTaskStore(session)
                await store2.set_status(task_id, TaskStatus.running)
                await store2.set_progress(task_id, 10)
                extractor = FilmEntityExtractor(llm)
                extractor.load_skill("film_entity_extractor")
                result = await extractor.aextract(input_dict)
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

    asyncio.create_task(
        _runner(
            task_record.id,
            {"source_id": body.source_id, "language": body.language or "zh", "chunks_json": chunks_json},
        )
    )

    return success_response(TaskCreated(task_id=task_record.id), code=201)


@router.post(
    "/tasks/shotlist",
    response_model=ApiResponse[TaskCreated],
    status_code=status.HTTP_201_CREATED,
    summary="分镜抽取（任务版）",
)
async def create_shotlist_task(
    body: ShotlistExtractTaskRequest,
    llm: Runnable = Depends(get_llm),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    target_type, target_id = _ensure_single_bind_target(body)

    store = SqlAlchemyTaskStore(db)
    tm = TaskManager(store=store, strategies={})

    chunks_json = json.dumps([{"chunk_id": c.chunk_id, "text": c.text} for c in body.chunks], ensure_ascii=False)
    task_record = await tm.create(
        task=_CreateOnlyTask(),  # BaseTask 仅用于记录 task_class
        mode=DeliveryMode.async_polling,
        run_args={
            "source_id": body.source_id,
            "source_title": body.source_title or "",
            "language": body.language or "zh",
            "chunks_json": chunks_json,
        },
    )
    await _bind_task(db, task_id=task_record.id, target_type=target_type, target_id=target_id, relation_type="shotlist")

    async def _runner(task_id: str, input_dict: dict) -> None:
        async with async_session_maker() as session:
            try:
                store2 = SqlAlchemyTaskStore(session)
                await store2.set_status(task_id, TaskStatus.running)
                await store2.set_progress(task_id, 10)
                storyboarder = FilmShotlistStoryboarder(llm)
                storyboarder.load_skill("film_shotlist")
                result = await storyboarder.aextract(input_dict)
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

    asyncio.create_task(
        _runner(
            task_record.id,
            {
                "source_id": body.source_id,
                "source_title": body.source_title or "",
                "language": body.language or "zh",
                "chunks_json": chunks_json,
            },
        )
    )

    return success_response(TaskCreated(task_id=task_record.id), code=201)


@router.get(
    "/tasks/{task_id}/status",
    response_model=ApiResponse[TaskStatusRead],
    summary="查询任务状态/进度（轮询）",
)
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskStatusRead]:
    store = SqlAlchemyTaskStore(db)
    view = await store.get_status_view(task_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return success_response(TaskStatusRead(task_id=view.id, status=view.status, progress=view.progress))


@router.get(
    "/tasks/{task_id}/result",
    response_model=ApiResponse[TaskResultRead],
    summary="获取任务结果",
)
async def get_task_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskResultRead]:
    row = await db.get(GenerationTask, task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    status_value = row.status.value if hasattr(row.status, "value") else str(row.status)
    return success_response(
        TaskResultRead(
            task_id=row.id,
            status=TaskStatus(status_value),
            progress=int(row.progress),
            result=row.result,
            error=row.error or "",
        )
    )


@router.patch(
    "/task-links/adopt",
    response_model=ApiResponse[TaskLinkAdoptRead],
    summary="更新任务关联的采用状态（仅可正向变更）",
    description="将指定任务链接的 is_adopted 设为 true；已采用不可改为未采用。",
)
async def adopt_task_link(
    body: TaskLinkAdoptRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskLinkAdoptRead]:
    target_type, entity_id = _ensure_single_bind_target(body)

    if target_type == "project":
        stmt = select(ProjectGenerationTaskLink).where(
            ProjectGenerationTaskLink.task_id == body.task_id,
            ProjectGenerationTaskLink.project_id == entity_id,
        ).limit(1)
        result = await db.execute(stmt)
        link = result.scalars().first()
    elif target_type == "chapter":
        stmt = select(ChapterGenerationTaskLink).where(
            ChapterGenerationTaskLink.task_id == body.task_id,
            ChapterGenerationTaskLink.chapter_id == entity_id,
        ).limit(1)
        result = await db.execute(stmt)
        link = result.scalars().first()
    else:
        stmt = select(ShotGenerationTaskLink).where(
            ShotGenerationTaskLink.task_id == body.task_id,
            ShotGenerationTaskLink.shot_id == entity_id,
        ).limit(1)
        result = await db.execute(stmt)
        link = result.scalars().first()

    if link is None:
        raise HTTPException(status_code=404, detail="Task link not found")

    if link.is_adopted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="状态只可正向变更，已采用不可改为未采用",
        )

    link.is_adopted = True
    await db.flush()

    return success_response(
        TaskLinkAdoptRead(
            task_id=body.task_id,
            link_type=target_type,
            entity_id=entity_id,
            is_adopted=True,
        )
    )
