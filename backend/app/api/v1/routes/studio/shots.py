"""Shot 相关 CRUD：Shot / ShotDetail / ShotDialogLine / 资源 Link。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.utils import apply_keyword_filter, apply_order, paginate
from app.dependencies import get_db
from app.models.studio import (
    ActorImage,
    Chapter,
    Character,
    Costume,
    Prop,
    Scene,
    Shot,
    ShotActorImageLink,
    ShotCostumeLink,
    ShotDetail,
    ShotDialogLine,
    ShotFrameImage,
    ShotPropLink,
    ShotSceneLink,
)
from app.schemas.common import ApiResponse, PaginatedData, paginated_response, success_response
from app.schemas.studio.shots import (
    ShotActorImageLinkRead,
    ShotAssetLinkCreate,
    ShotCostumeLinkRead,
    ShotCreate,
    ShotDetailCreate,
    ShotDetailRead,
    ShotDetailUpdate,
    ShotDialogLineCreate,
    ShotDialogLineRead,
    ShotDialogLineUpdate,
    ShotLinkUpdate,
    ShotPropLinkRead,
    ShotRead,
    ShotSceneLinkRead,
    ShotUpdate,
    ShotFrameImageCreate,
    ShotFrameImageRead,
    ShotFrameImageUpdate,
)

router = APIRouter()
details_router = APIRouter()
dialog_router = APIRouter()
links_router = APIRouter()
frames_router = APIRouter()

SHOT_ORDER_FIELDS = {"index", "title", "status", "created_at", "updated_at"}
DETAIL_ORDER_FIELDS = {"id"}
DIALOG_ORDER_FIELDS = {"index", "id", "created_at", "updated_at"}
LINK_ORDER_FIELDS = {"index", "id", "created_at", "updated_at"}
FRAME_IMAGE_ORDER_FIELDS = {"id", "frame_type", "created_at", "updated_at"}


async def _ensure_chapter(db: AsyncSession, chapter_id: str) -> None:
    if await db.get(Chapter, chapter_id) is None:
        raise HTTPException(status_code=400, detail="Chapter not found")


async def _ensure_shot(db: AsyncSession, shot_id: str) -> None:
    if await db.get(Shot, shot_id) is None:
        raise HTTPException(status_code=400, detail="Shot not found")


async def _ensure_scene_optional(db: AsyncSession, scene_id: str | None) -> None:
    if scene_id is None:
        return
    if await db.get(Scene, scene_id) is None:
        raise HTTPException(status_code=400, detail="Scene not found")


async def _ensure_character_optional(db: AsyncSession, character_id: str | None) -> None:
    if character_id is None:
        return
    if await db.get(Character, character_id) is None:
        raise HTTPException(status_code=400, detail="Character not found")


async def _ensure_actor_image(db: AsyncSession, actor_image_id: str) -> None:
    if await db.get(ActorImage, actor_image_id) is None:
        raise HTTPException(status_code=400, detail="ActorImage not found")


async def _ensure_prop(db: AsyncSession, prop_id: str) -> None:
    if await db.get(Prop, prop_id) is None:
        raise HTTPException(status_code=400, detail="Prop not found")


async def _ensure_costume(db: AsyncSession, costume_id: str) -> None:
    if await db.get(Costume, costume_id) is None:
        raise HTTPException(status_code=400, detail="Costume not found")


# ---------- Shot ----------


@router.get(
    "",
    response_model=ApiResponse[PaginatedData[ShotRead]],
    summary="镜头列表（分页）",
)
async def list_shots(
    db: AsyncSession = Depends(get_db),
    chapter_id: str | None = Query(None, description="按章节过滤"),
    q: str | None = Query(None, description="关键字，过滤 title/script_excerpt"),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotRead]]:
    stmt = select(Shot)
    if chapter_id is not None:
        stmt = stmt.where(Shot.chapter_id == chapter_id)
    stmt = apply_keyword_filter(stmt, q=q, fields=[Shot.title, Shot.script_excerpt])
    stmt = apply_order(stmt, model=Shot, order=order, is_desc=is_desc, allow_fields=SHOT_ORDER_FIELDS, default="index")
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response([ShotRead.model_validate(x) for x in items], page=page, page_size=page_size, total=total)


@router.post(
    "",
    response_model=ApiResponse[ShotRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头",
)
async def create_shot(
    body: ShotCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotRead]:
    exists = await db.get(Shot, body.id)
    if exists is not None:
        raise HTTPException(status_code=400, detail=f"Shot with id={body.id} already exists")
    await _ensure_chapter(db, body.chapter_id)
    obj = Shot(**body.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotRead.model_validate(obj), code=201)


@router.get(
    "/{shot_id}",
    response_model=ApiResponse[ShotRead],
    summary="获取镜头",
)
async def get_shot(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotRead]:
    obj = await db.get(Shot, shot_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    return success_response(ShotRead.model_validate(obj))


@router.patch(
    "/{shot_id}",
    response_model=ApiResponse[ShotRead],
    summary="更新镜头",
)
async def update_shot(
    shot_id: str,
    body: ShotUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotRead]:
    obj = await db.get(Shot, shot_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    update_data = body.model_dump(exclude_unset=True)
    if "chapter_id" in update_data:
        await _ensure_chapter(db, update_data["chapter_id"])
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotRead.model_validate(obj))


@router.delete(
    "/{shot_id}",
    response_model=ApiResponse[None],
    summary="删除镜头",
)
async def delete_shot(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(Shot, shot_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)


# ---------- ShotDetail ----------


@details_router.get(
    "",
    response_model=ApiResponse[PaginatedData[ShotDetailRead]],
    summary="镜头细节列表（分页）",
)
async def list_shot_details(
    db: AsyncSession = Depends(get_db),
    shot_id: str | None = Query(None, description="按镜头过滤（id 同 shot_id）"),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotDetailRead]]:
    stmt = select(ShotDetail)
    if shot_id is not None:
        stmt = stmt.where(ShotDetail.id == shot_id)
    stmt = apply_order(stmt, model=ShotDetail, order=order, is_desc=is_desc, allow_fields=DETAIL_ORDER_FIELDS, default="id")
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response([ShotDetailRead.model_validate(x) for x in items], page=page, page_size=page_size, total=total)


@details_router.post(
    "",
    response_model=ApiResponse[ShotDetailRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头细节",
)
async def create_shot_detail(
    body: ShotDetailCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotDetailRead]:
    exists = await db.get(ShotDetail, body.id)
    if exists is not None:
        raise HTTPException(status_code=400, detail="ShotDetail already exists")
    await _ensure_shot(db, body.id)
    await _ensure_scene_optional(db, body.scene_id)
    obj = ShotDetail(**body.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotDetailRead.model_validate(obj), code=201)


@details_router.get(
    "/{shot_id}",
    response_model=ApiResponse[ShotDetailRead],
    summary="获取镜头细节",
)
async def get_shot_detail(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotDetailRead]:
    obj = await db.get(ShotDetail, shot_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotDetail not found")
    return success_response(ShotDetailRead.model_validate(obj))


@details_router.patch(
    "/{shot_id}",
    response_model=ApiResponse[ShotDetailRead],
    summary="更新镜头细节",
)
async def update_shot_detail(
    shot_id: str,
    body: ShotDetailUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotDetailRead]:
    obj = await db.get(ShotDetail, shot_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotDetail not found")
    update_data = body.model_dump(exclude_unset=True)
    if "scene_id" in update_data:
        await _ensure_scene_optional(db, update_data["scene_id"])
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotDetailRead.model_validate(obj))


@details_router.delete(
    "/{shot_id}",
    response_model=ApiResponse[None],
    summary="删除镜头细节",
)
async def delete_shot_detail(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(ShotDetail, shot_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)


# ---------- ShotDialogLine ----------


@dialog_router.get(
    "",
    response_model=ApiResponse[PaginatedData[ShotDialogLineRead]],
    summary="镜头对话行列表（分页）",
)
async def list_shot_dialog_lines(
    db: AsyncSession = Depends(get_db),
    shot_detail_id: str | None = Query(None, description="按镜头细节过滤"),
    q: str | None = Query(None, description="关键字，过滤 text"),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotDialogLineRead]]:
    stmt = select(ShotDialogLine)
    if shot_detail_id is not None:
        stmt = stmt.where(ShotDialogLine.shot_detail_id == shot_detail_id)
    stmt = apply_keyword_filter(stmt, q=q, fields=[ShotDialogLine.text])
    stmt = apply_order(stmt, model=ShotDialogLine, order=order, is_desc=is_desc, allow_fields=DIALOG_ORDER_FIELDS, default="index")
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response([ShotDialogLineRead.model_validate(x) for x in items], page=page, page_size=page_size, total=total)


@dialog_router.post(
    "",
    response_model=ApiResponse[ShotDialogLineRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头对话行",
)
async def create_shot_dialog_line(
    body: ShotDialogLineCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotDialogLineRead]:
    if await db.get(ShotDetail, body.shot_detail_id) is None:
        raise HTTPException(status_code=400, detail="ShotDetail not found")
    await _ensure_character_optional(db, body.speaker_character_id)
    await _ensure_character_optional(db, body.target_character_id)
    obj = ShotDialogLine(**body.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotDialogLineRead.model_validate(obj), code=201)


@dialog_router.patch(
    "/{line_id}",
    response_model=ApiResponse[ShotDialogLineRead],
    summary="更新镜头对话行",
)
async def update_shot_dialog_line(
    line_id: int,
    body: ShotDialogLineUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotDialogLineRead]:
    obj = await db.get(ShotDialogLine, line_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotDialogLine not found")
    update_data = body.model_dump(exclude_unset=True)
    if "speaker_character_id" in update_data:
        await _ensure_character_optional(db, update_data["speaker_character_id"])
    if "target_character_id" in update_data:
        await _ensure_character_optional(db, update_data["target_character_id"])
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotDialogLineRead.model_validate(obj))


@dialog_router.delete(
    "/{line_id}",
    response_model=ApiResponse[None],
    summary="删除镜头对话行",
)
async def delete_shot_dialog_line(
    line_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(ShotDialogLine, line_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)


# ---------- ShotFrameImage ----------


@frames_router.get(
    "",
    response_model=ApiResponse[PaginatedData[ShotFrameImageRead]],
    summary="镜头分镜帧图片列表（分页）",
)
async def list_shot_frame_images(
    db: AsyncSession = Depends(get_db),
    shot_detail_id: str | None = Query(None, description="按镜头细节过滤"),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotFrameImageRead]]:
    stmt = select(ShotFrameImage)
    if shot_detail_id is not None:
        stmt = stmt.where(ShotFrameImage.shot_detail_id == shot_detail_id)
    stmt = apply_order(
        stmt,
        model=ShotFrameImage,
        order=order,
        is_desc=is_desc,
        allow_fields=FRAME_IMAGE_ORDER_FIELDS,
        default="id",
    )
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response(
        [ShotFrameImageRead.model_validate(x) for x in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@frames_router.post(
    "",
    response_model=ApiResponse[ShotFrameImageRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头分镜帧图片",
)
async def create_shot_frame_image(
    body: ShotFrameImageCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotFrameImageRead]:
    if await db.get(ShotDetail, body.shot_detail_id) is None:
        raise HTTPException(status_code=400, detail="ShotDetail not found")
    obj = ShotFrameImage(**body.model_dump())
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotFrameImageRead.model_validate(obj), code=201)


@frames_router.patch(
    "/{image_id}",
    response_model=ApiResponse[ShotFrameImageRead],
    summary="更新镜头分镜帧图片",
)
async def update_shot_frame_image(
    image_id: int,
    body: ShotFrameImageUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotFrameImageRead]:
    obj = await db.get(ShotFrameImage, image_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotFrameImage not found")
    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotFrameImageRead.model_validate(obj))


@frames_router.delete(
    "/{image_id}",
    response_model=ApiResponse[None],
    summary="删除镜头分镜帧图片",
)
async def delete_shot_frame_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(ShotFrameImage, image_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)


# ---------- Links（镜头引用资产） ----------


@links_router.get(
    "/actor-image",
    response_model=ApiResponse[PaginatedData[ShotActorImageLinkRead]],
    summary="镜头-演员形象关联列表（分页）",
)
async def list_shot_actor_image_links(
    db: AsyncSession = Depends(get_db),
    shot_id: str | None = Query(None),
    actor_image_id: str | None = Query(None),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotActorImageLinkRead]]:
    stmt = select(ShotActorImageLink)
    if shot_id is not None:
        stmt = stmt.where(ShotActorImageLink.shot_id == shot_id)
    if actor_image_id is not None:
        stmt = stmt.where(ShotActorImageLink.actor_image_id == actor_image_id)
    stmt = apply_order(stmt, model=ShotActorImageLink, order=order, is_desc=is_desc, allow_fields=LINK_ORDER_FIELDS, default="index")
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response([ShotActorImageLinkRead.model_validate(x) for x in items], page=page, page_size=page_size, total=total)


@links_router.post(
    "/actor-image",
    response_model=ApiResponse[ShotActorImageLinkRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头-演员形象关联",
)
async def create_shot_actor_image_link(
    body: ShotAssetLinkCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotActorImageLinkRead]:
    await _ensure_shot(db, body.shot_id)
    await _ensure_actor_image(db, body.asset_id)
    obj = ShotActorImageLink(
        shot_id=body.shot_id,
        actor_image_id=body.asset_id,
        index=body.index,
        note=body.note,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotActorImageLinkRead.model_validate(obj), code=201)


@links_router.patch(
    "/actor-image/{link_id}",
    response_model=ApiResponse[ShotActorImageLinkRead],
    summary="更新镜头-演员形象关联",
)
async def update_shot_actor_image_link(
    link_id: int,
    body: ShotLinkUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotActorImageLinkRead]:
    obj = await db.get(ShotActorImageLink, link_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotActorImageLink not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotActorImageLinkRead.model_validate(obj))


@links_router.delete(
    "/actor-image/{link_id}",
    response_model=ApiResponse[None],
    summary="删除镜头-演员形象关联",
)
async def delete_shot_actor_image_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(ShotActorImageLink, link_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)


@links_router.get(
    "/scene",
    response_model=ApiResponse[PaginatedData[ShotSceneLinkRead]],
    summary="镜头-场景关联列表（分页）",
)
async def list_shot_scene_links(
    db: AsyncSession = Depends(get_db),
    shot_id: str | None = Query(None),
    scene_id: str | None = Query(None),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotSceneLinkRead]]:
    stmt = select(ShotSceneLink)
    if shot_id is not None:
        stmt = stmt.where(ShotSceneLink.shot_id == shot_id)
    if scene_id is not None:
        stmt = stmt.where(ShotSceneLink.scene_id == scene_id)
    stmt = apply_order(stmt, model=ShotSceneLink, order=order, is_desc=is_desc, allow_fields=LINK_ORDER_FIELDS, default="index")
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response([ShotSceneLinkRead.model_validate(x) for x in items], page=page, page_size=page_size, total=total)


@links_router.post(
    "/scene",
    response_model=ApiResponse[ShotSceneLinkRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头-场景关联",
)
async def create_shot_scene_link(
    body: ShotAssetLinkCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotSceneLinkRead]:
    await _ensure_shot(db, body.shot_id)
    await _ensure_scene_optional(db, body.asset_id)
    obj = ShotSceneLink(
        shot_id=body.shot_id,
        scene_id=body.asset_id,
        index=body.index,
        note=body.note,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotSceneLinkRead.model_validate(obj), code=201)


@links_router.patch(
    "/scene/{link_id}",
    response_model=ApiResponse[ShotSceneLinkRead],
    summary="更新镜头-场景关联",
)
async def update_shot_scene_link(
    link_id: int,
    body: ShotLinkUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotSceneLinkRead]:
    obj = await db.get(ShotSceneLink, link_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotSceneLink not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotSceneLinkRead.model_validate(obj))


@links_router.delete(
    "/scene/{link_id}",
    response_model=ApiResponse[None],
    summary="删除镜头-场景关联",
)
async def delete_shot_scene_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(ShotSceneLink, link_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)


@links_router.get(
    "/prop",
    response_model=ApiResponse[PaginatedData[ShotPropLinkRead]],
    summary="镜头-道具关联列表（分页）",
)
async def list_shot_prop_links(
    db: AsyncSession = Depends(get_db),
    shot_id: str | None = Query(None),
    prop_id: str | None = Query(None),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotPropLinkRead]]:
    stmt = select(ShotPropLink)
    if shot_id is not None:
        stmt = stmt.where(ShotPropLink.shot_id == shot_id)
    if prop_id is not None:
        stmt = stmt.where(ShotPropLink.prop_id == prop_id)
    stmt = apply_order(stmt, model=ShotPropLink, order=order, is_desc=is_desc, allow_fields=LINK_ORDER_FIELDS, default="index")
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response([ShotPropLinkRead.model_validate(x) for x in items], page=page, page_size=page_size, total=total)


@links_router.post(
    "/prop",
    response_model=ApiResponse[ShotPropLinkRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头-道具关联",
)
async def create_shot_prop_link(
    body: ShotAssetLinkCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotPropLinkRead]:
    await _ensure_shot(db, body.shot_id)
    await _ensure_prop(db, body.asset_id)
    obj = ShotPropLink(
        shot_id=body.shot_id,
        prop_id=body.asset_id,
        index=body.index,
        note=body.note,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotPropLinkRead.model_validate(obj), code=201)


@links_router.patch(
    "/prop/{link_id}",
    response_model=ApiResponse[ShotPropLinkRead],
    summary="更新镜头-道具关联",
)
async def update_shot_prop_link(
    link_id: int,
    body: ShotLinkUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotPropLinkRead]:
    obj = await db.get(ShotPropLink, link_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotPropLink not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotPropLinkRead.model_validate(obj))


@links_router.delete(
    "/prop/{link_id}",
    response_model=ApiResponse[None],
    summary="删除镜头-道具关联",
)
async def delete_shot_prop_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(ShotPropLink, link_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)


@links_router.get(
    "/costume",
    response_model=ApiResponse[PaginatedData[ShotCostumeLinkRead]],
    summary="镜头-服装关联列表（分页）",
)
async def list_shot_costume_links(
    db: AsyncSession = Depends(get_db),
    shot_id: str | None = Query(None),
    costume_id: str | None = Query(None),
    order: str | None = Query(None),
    is_desc: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
) -> ApiResponse[PaginatedData[ShotCostumeLinkRead]]:
    stmt = select(ShotCostumeLink)
    if shot_id is not None:
        stmt = stmt.where(ShotCostumeLink.shot_id == shot_id)
    if costume_id is not None:
        stmt = stmt.where(ShotCostumeLink.costume_id == costume_id)
    stmt = apply_order(stmt, model=ShotCostumeLink, order=order, is_desc=is_desc, allow_fields=LINK_ORDER_FIELDS, default="index")
    items, total = await paginate(db, stmt=stmt, page=page, page_size=page_size)
    return paginated_response([ShotCostumeLinkRead.model_validate(x) for x in items], page=page, page_size=page_size, total=total)


@links_router.post(
    "/costume",
    response_model=ApiResponse[ShotCostumeLinkRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建镜头-服装关联",
)
async def create_shot_costume_link(
    body: ShotAssetLinkCreate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotCostumeLinkRead]:
    await _ensure_shot(db, body.shot_id)
    await _ensure_costume(db, body.asset_id)
    obj = ShotCostumeLink(
        shot_id=body.shot_id,
        costume_id=body.asset_id,
        index=body.index,
        note=body.note,
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotCostumeLinkRead.model_validate(obj), code=201)


@links_router.patch(
    "/costume/{link_id}",
    response_model=ApiResponse[ShotCostumeLinkRead],
    summary="更新镜头-服装关联",
)
async def update_shot_costume_link(
    link_id: int,
    body: ShotLinkUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ShotCostumeLinkRead]:
    obj = await db.get(ShotCostumeLink, link_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ShotCostumeLink not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.flush()
    await db.refresh(obj)
    return success_response(ShotCostumeLinkRead.model_validate(obj))


@links_router.delete(
    "/costume/{link_id}",
    response_model=ApiResponse[None],
    summary="删除镜头-服装关联",
)
async def delete_shot_costume_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    obj = await db.get(ShotCostumeLink, link_id)
    if obj is None:
        return success_response(None)
    await db.delete(obj)
    await db.flush()
    return success_response(None)

