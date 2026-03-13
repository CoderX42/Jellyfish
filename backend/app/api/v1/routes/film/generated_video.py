from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.config import settings
from app.core.task_manager import DeliveryMode, SqlAlchemyTaskStore, TaskManager
from app.core.task_manager.types import TaskStatus
from app.core.tasks import ProviderConfig, VideoGenerationInput, VideoGenerationTask
from app.dependencies import get_db
from app.schemas.common import ApiResponse, success_response

from .common import TaskCreated, _CreateOnlyTask, bind_task, ensure_single_bind_target
from .video_request import VideoGenerationTaskRequest

router = APIRouter()


@router.post(
    "/tasks/video",
    response_model=ApiResponse[TaskCreated],
    status_code=201,
    summary="视频生成（任务版）",
)
async def create_video_generation_task(
    body: VideoGenerationTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    """创建视频生成任务并后台执行，结果通过 /tasks/{task_id}/result 获取。"""

    store = SqlAlchemyTaskStore(db)
    tm = TaskManager(store=store, strategies={})

    # 视频生成：优先使用配置中的 VIDEO_API_*，未配置时回退到请求体字段。
    provider = settings.video_api_provider or body.provider
    api_key = settings.video_api_key or body.api_key
    base_url = settings.video_api_base_url or body.base_url

    run_args: dict = {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "input": {
            "prompt": body.prompt,
            "first_frame_file_id": body.first_frame_file_id,
            "first_frame_url": body.first_frame_url,
            "last_frame_file_id": body.last_frame_file_id,
            "last_frame_url": body.last_frame_url,
            "key_frame_file_id": body.key_frame_file_id,
            "key_frame_url": body.key_frame_url,
            "model": body.model,
            "size": body.size,
            "seconds": body.seconds,
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
    except Exception:  # noqa: BLE001
        target_type = target_id = None  # type: ignore[assignment]
    if target_type and target_id:
        await bind_task(
            db,
            task_id=task_record.id,
            target_type=target_type,
            target_id=target_id,
            relation_type="video",
        )

    # 确保任务记录已提交，避免后台 runner 新 session 查询不到任务行而无法更新状态。
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

                task = VideoGenerationTask(
                    provider_config=ProviderConfig(
                        provider=provider,  # type: ignore[arg-type]
                        api_key=api_key,
                        base_url=base_url,
                    ),
                    input_=VideoGenerationInput.model_validate(input_dict),
                )
                await task.run()
                result = await task.get_result()
                if result is None:
                    # 同步透传底层任务中的具体错误，便于排查。
                    status_dict = await task.status()  # type: ignore[assignment]
                    detailed_error = ""
                    if isinstance(status_dict, dict):
                        detailed_error = str(status_dict.get("error") or "")
                    msg = detailed_error or "Video generation task returned no result"
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

