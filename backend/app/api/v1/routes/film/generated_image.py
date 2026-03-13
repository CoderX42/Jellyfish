from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.config import settings
from app.core.task_manager import DeliveryMode, SqlAlchemyTaskStore, TaskManager
from app.core.task_manager.types import TaskStatus
from app.core.tasks import (
    ImageGenerationInput,
    ImageGenerationTask,
    ProviderConfig,
)
from app.dependencies import get_db
from app.schemas.common import ApiResponse, success_response

from .common import TaskCreated, _CreateOnlyTask, bind_task, ensure_single_bind_target
from .image_generation_request import ImageGenerationTaskRequest


router = APIRouter()


@router.post(
    "/tasks/images",
    response_model=ApiResponse[TaskCreated],
    status_code=201,
    summary="图片生成（任务版）",
)
async def create_image_generation_task(
    body: ImageGenerationTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    """创建图片生成任务并后台执行，结果通过 /tasks/{task_id}/result 获取。"""

    store = SqlAlchemyTaskStore(db)
    tm = TaskManager(store=store, strategies={})

    # 优先使用配置中的 IMAGE_API_*；仅在未配置时才允许从请求体回退，便于开发调试。
    provider = settings.image_api_provider or body.provider
    api_key = settings.image_api_key or body.api_key
    base_url = settings.image_api_base_url or body.base_url

    if not provider:
        raise HTTPException(
            status_code=503,
            detail="IMAGE_API_PROVIDER not configured and provider not provided",
        )
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="IMAGE_API_KEY not configured; set it in .env 或在请求体中提供 api_key",
        )

    run_args: dict = {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "input": {
            "prompt": body.prompt,
            "images": [
                {
                    "file_id": ref.file_id,
                    "image_url": ref.image_url,
                }
                for ref in body.images
            ],
            "model": body.model,
            "size": body.size,
            "n": body.n,
            "seed": body.seed,
            "response_format": body.response_format,
        },
    }

    task_record = await tm.create(
        task=_CreateOnlyTask(),
        mode=DeliveryMode.async_polling,
        run_args=run_args,
    )
    # 绑定为可选：仅当提供 project_id/chapter_id/shot_id 中之一时才建立关联。
    try:
        target_type, target_id = ensure_single_bind_target(body)
    except HTTPException:
        target_type = target_id = None  # type: ignore[assignment]
    if target_type and target_id:
        await bind_task(
            db,
            task_id=task_record.id,
            target_type=target_type,
            target_id=target_id,
            relation_type="image",
        )

    # 关键：确保 task_record 已提交，使后台 runner 使用新 session 时能读取到该行并更新状态。
    await db.commit()

    async def _runner(task_id: str, args: dict) -> None:
        async with async_session_maker() as session:
            try:
                store2 = SqlAlchemyTaskStore(session)
                await store2.set_status(task_id, TaskStatus.running)
                await store2.set_progress(task_id, 10)

                provider = str(args.get("provider") or "")
                api_key = str(args.get("api_key") or "")
                base_url = args.get("base_url")
                input_dict = dict(args.get("input") or {})

                task = ImageGenerationTask(
                    provider_config=ProviderConfig(
                        provider=provider,  # type: ignore[arg-type]
                        api_key=api_key,
                        base_url=base_url,
                    ),
                    input_=ImageGenerationInput.model_validate(input_dict),
                )
                await task.run()
                result = await task.get_result()
                if result is None:
                    # 尝试从任务状态中获取更具体的错误信息，便于排查（如供应商 HTTP 错误、配置错误等）。
                    status_dict = await task.status()  # type: ignore[assignment]
                    detailed_error = ""
                    if isinstance(status_dict, dict):
                        detailed_error = str(status_dict.get("error") or "")
                    msg = detailed_error or "Image generation task returned no result"
                    raise RuntimeError(msg)

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

