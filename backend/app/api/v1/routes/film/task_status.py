from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.task_manager import SqlAlchemyTaskStore
from app.core.task_manager.types import TaskStatus
from app.dependencies import get_db
from app.models.task import GenerationTask
from app.models.task_links import GenerationTaskLink
from app.schemas.common import ApiResponse, success_response

from .common import TaskLinkAdoptRead, TaskLinkAdoptRequest, TaskResultRead, TaskStatusRead, ensure_single_bind_target

router = APIRouter()


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
    target_type, entity_id = ensure_single_bind_target(body)

    # 关联表已统一为 GenerationTaskLink，不再区分 project/chapter/shot，直接用 relation_entity_id 反查
    stmt = select(GenerationTaskLink).where(
        GenerationTaskLink.task_id == body.task_id,
        GenerationTaskLink.relation_entity_id == entity_id,
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

