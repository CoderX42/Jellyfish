"""影视技能 API：实体抽取、分镜抽取。"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter

from app.api.v1.routes.film import extract, tasks_entities, generated_video, generated_image, tasks_images, task_status

router = APIRouter()
router.include_router(extract.router)
router.include_router(tasks_entities.router)
router.include_router(generated_video.router)
router.include_router(generated_image.router)
router.include_router(tasks_images.router)
router.include_router(task_status.router)

__all__ = ["router"]
