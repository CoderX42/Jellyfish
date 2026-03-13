from __future__ import annotations

"""资产与镜头相关的图片生成任务 API。

通过 TaskManager 调用 `ImageGenerationTask`，并使用 `GenerationTaskLink`
将任务与上层业务实体（演员形象/道具/场景/服装/角色/镜头分镜帧）建立关联。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel, Field

from app.core.db import async_session_maker
from app.core.task_manager import DeliveryMode, SqlAlchemyTaskStore, TaskManager
from app.core.task_manager.types import TaskStatus
from app.core.tasks import ImageGenerationInput, ImageGenerationTask, ProviderConfig
from app.dependencies import get_db
from app.models.llm import Model, ModelCategoryKey, ModelSettings, Provider
from app.models.studio import (
    ActorImage,
    Character,
    Costume,
    Prop,
    Scene,
    ShotDetail,
)
from app.models.task_links import GenerationTaskLink
from app.schemas.common import ApiResponse, success_response
from app.api.v1.routes.film.common import TaskCreated, _CreateOnlyTask


router = APIRouter()


class StudioImageTaskRequest(BaseModel):
    """Studio 专用图片任务请求体：可选模型 ID，不传则用默认图片模型；供应商由模型反查。"""

    model_id: str | None = Field(
        None,
        description="可选模型 ID（models.id）；不传则使用 ModelSettings.default_image_model_id；Provider 由模型关联反查",
    )


def _provider_key_from_db_name(name: str) -> str:
    """将 Provider.name 映射为任务层 ProviderKey（openai | volcengine）。
    规范名称：openai、火山引擎；兼容旧命名（volc/doubao/bytedance）映射为 volcengine。
    无法映射时抛出 503。
    """
    n = (name or "").strip()
    n_lower = n.lower()
    if n_lower == "openai":
        return "openai"
    if n == "火山引擎" or "volc" in n_lower or "doubao" in n_lower or "bytedance" in n_lower:
        return "volcengine"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Unsupported provider name: {name!r}. Expected: openai, 火山引擎.",
    )


async def _resolve_image_model(db: AsyncSession, model_id: str | None) -> Model:
    """根据显式 model_id 或默认图片模型解析 Model。"""
    effective_model_id = model_id
    if not effective_model_id:
        settings_row = await db.get(ModelSettings, 1)
        effective_model_id = settings_row.default_image_model_id if settings_row else None

    if not effective_model_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No image model configured in DB (missing explicit model_id and ModelSettings.default_image_model_id)",
        )

    model = await db.get(Model, effective_model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured model_id not found in DB: {effective_model_id}",
        )
    if model.category != ModelCategoryKey.image:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Configured model is not an image model: {effective_model_id} (category={model.category})",
        )
    return model


async def _load_provider_config(db: AsyncSession, provider_id: str) -> ProviderConfig:
    """根据 provider_id 从 DB 解析 ProviderConfig；仅允许适用于图片生成的供应商（openai、火山引擎）。"""
    provider = await db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Provider not found for provider_id={provider_id}",
        )
    try:
        provider_key = _provider_key_from_db_name(provider.name)
    except HTTPException as e:
        if e.status_code == status.HTTP_503_SERVICE_UNAVAILABLE and (provider.name or "").strip() == "阿里百炼":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该供应商仅适用于文本生成，不支持图片生成（name=阿里百炼）",
            ) from e
        raise
    api_key = (provider.api_key or "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Provider api_key is empty for provider_id={provider.id}",
        )
    base_url = (provider.base_url or "").strip() or None
    return ProviderConfig(provider=provider_key, api_key=api_key, base_url=base_url)  # type: ignore[arg-type]


def _prompt_from_description(description: str, *, not_found_msg: str) -> str:
    prompt = (description or "").strip()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=not_found_msg)
    return prompt


async def _create_image_task_and_link(
    *,
    db: AsyncSession,
    model_id: str | None,
    relation_type: str,
    relation_entity_id: str,
    prompt: str,
) -> TaskCreated:
    """创建图片生成任务，并在 `GenerationTaskLink` 中建立关联；Provider 由解析出的 Model 反查。"""
    store = SqlAlchemyTaskStore(db)
    tm = TaskManager(store=store, strategies={})

    model = await _resolve_image_model(db, model_id)
    provider_cfg = await _load_provider_config(db, model.provider_id)

    run_args: dict = {
        "provider": provider_cfg.provider,
        "api_key": provider_cfg.api_key,
        "base_url": provider_cfg.base_url,
        "input": {
            "prompt": prompt,
            # 生成参数与参考图统一从 DB 侧控制；此接口不接收覆盖参数。
            "model": model.name,
        },
    }

    task_record = await tm.create(
        task=_CreateOnlyTask(),
        mode=DeliveryMode.async_polling,
        run_args=run_args,
    )

    link = GenerationTaskLink(
        task_id=task_record.id,
        resource_type="image",
        relation_type=relation_type,
        relation_entity_id=relation_entity_id,
    )
    db.add(link)
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
                    raise RuntimeError("Image generation task returned no result")

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
    return TaskCreated(task_id=task_record.id)


@router.post(
    "/actor-images/{actor_image_id}/image-tasks",
    response_model=ApiResponse[TaskCreated],
    status_code=status.HTTP_201_CREATED,
    summary="演员形象/立绘图片生成（任务版）",
)
async def create_actor_image_generation_task(
    actor_image_id: str,
    body: StudioImageTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    """为指定演员形象创建图片生成任务，并通过 `GenerationTaskLink` 关联。"""
    actor_image = await db.get(ActorImage, actor_image_id)
    if actor_image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ActorImage not found")
    prompt = _prompt_from_description(actor_image.description, not_found_msg="ActorImage.description is empty")
    created = await _create_image_task_and_link(
        db=db,
        model_id=body.model_id,
        relation_type="actor_image",
        relation_entity_id=actor_image_id,
        prompt=prompt,
    )
    return success_response(created, code=201)


@router.post(
    "/assets/{asset_type}/{asset_id}/image-tasks",
    response_model=ApiResponse[TaskCreated],
    status_code=status.HTTP_201_CREATED,
    summary="道具/场景/服装图片生成（任务版）",
)
async def create_asset_image_generation_task(
    asset_type: str,
    asset_id: str,
    body: StudioImageTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    """为道具/场景/服装创建图片生成任务。

    - asset_type: prop / scene / costume
    """
    asset_type_norm = asset_type.strip().lower()
    if asset_type_norm == "prop":
        asset = await db.get(Prop, asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prop not found")
        relation_type = "prop_image"
        prompt = _prompt_from_description(asset.description, not_found_msg="Prop.description is empty")
    elif asset_type_norm == "scene":
        asset = await db.get(Scene, asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")
        relation_type = "scene_image"
        prompt = _prompt_from_description(asset.description, not_found_msg="Scene.description is empty")
    elif asset_type_norm == "costume":
        asset = await db.get(Costume, asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Costume not found")
        relation_type = "costume_image"
        prompt = _prompt_from_description(asset.description, not_found_msg="Costume.description is empty")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="asset_type must be one of: prop/scene/costume",
        )

    created = await _create_image_task_and_link(
        db=db,
        model_id=body.model_id,
        relation_type=relation_type,
        relation_entity_id=asset_id,
        prompt=prompt,
    )
    return success_response(created, code=201)


@router.post(
    "/characters/{character_id}/image-tasks",
    response_model=ApiResponse[TaskCreated],
    status_code=status.HTTP_201_CREATED,
    summary="角色图片生成（任务版）",
)
async def create_character_image_generation_task(
    character_id: str,
    body: StudioImageTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    """为角色创建图片生成任务（对应 CharacterImage 业务）。"""
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    prompt = _prompt_from_description(character.description, not_found_msg="Character.description is empty")
    created = await _create_image_task_and_link(
        db=db,
        model_id=body.model_id,
        relation_type="character_image",
        relation_entity_id=character_id,
        prompt=prompt,
    )
    return success_response(created, code=201)


@router.post(
    "/shot-details/{shot_detail_id}/frame-image-tasks",
    response_model=ApiResponse[TaskCreated],
    status_code=status.HTTP_201_CREATED,
    summary="镜头分镜帧图片生成（任务版）",
)
async def create_shot_frame_image_generation_task(
    shot_detail_id: str,
    body: StudioImageTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TaskCreated]:
    """为镜头分镜帧（ShotDetail）创建图片生成任务。

    - relation_type 固定为 shot_frame_image
    - relation_entity_id 为 ShotDetail.id
    """
    shot_detail = await db.get(ShotDetail, shot_detail_id)
    if shot_detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ShotDetail not found")
    # ShotDetail 无 description：默认优先 key_frame_prompt，其次 first/last。
    prompt = (
        (shot_detail.key_frame_prompt or "").strip()
        or (shot_detail.first_frame_prompt or "").strip()
        or (shot_detail.last_frame_prompt or "").strip()
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ShotDetail has no frame prompt (key/first/last are all empty)",
        )
    created = await _create_image_task_and_link(
        db=db,
        model_id=body.model_id,
        relation_type="shot_frame_image",
        relation_entity_id=shot_detail_id,
        prompt=prompt,
    )
    return success_response(created, code=201)

