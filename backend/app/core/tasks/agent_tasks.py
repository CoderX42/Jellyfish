"""将 chains/agents 的能力封装为 BaseTask 任务。

说明：
- 这些 Task 采用 async_result 模式：run() 返回 None，结果通过 get_result() 获取。
- 目的：让上层可以用统一的 TaskManager/存储模型编排生成任务。
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from app.chains.agents import (
    FilmEntityExtractor,
    FilmShotlistStoryboarder,
    ShotFirstFramePromptAgent,
    ShotKeyFramePromptAgent,
    ShotLastFramePromptAgent,
)
from app.core.skills_runtime import (
    FilmEntityExtractionResult,
    FilmShotlistResult,
    ShotFramePromptResult,
)
from app.core.task_manager.types import BaseTask


class _BaseAsyncResultTask(BaseTask):
    """通用基类：保存 _result/_error，并提供通用 status/is_done/get_result。"""

    TASK_KEY: str = ""

    def __init__(self) -> None:
        self._error: str = ""

    async def status(self) -> dict[str, Any]:  # type: ignore[override]
        return {
            "task": self.TASK_KEY,
            "done": await self.is_done(),
            "has_result": (await self.get_result()) is not None,
            "error": self._error,
        }

    async def is_done(self) -> bool:  # type: ignore[override]
        return (await self.get_result()) is not None or bool(self._error)


class FilmEntityExtractionTask2(_BaseAsyncResultTask):
    """人物/地点/道具抽取任务（基于 FilmEntityExtractor）。"""

    TASK_KEY = "film_entity_extraction"

    def __init__(
        self,
        extractor: FilmEntityExtractor,
        *,
        input_dict: dict[str, Any],
        skill_id: str = "film_entity_extractor",
    ) -> None:
        super().__init__()
        self._extractor = extractor
        self._input_dict = input_dict
        self._skill_id = skill_id
        self._result: FilmEntityExtractionResult | None = None

    async def run(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any] | None:  # type: ignore[override]
        try:
            self._extractor.load_skill(self._skill_id)
            self._result = await self._extractor.aextract(self._input_dict)
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self._result = None
        return None

    async def get_result(self) -> FilmEntityExtractionResult | None:  # type: ignore[override]
        return self._result


class FilmShotlistTask2(_BaseAsyncResultTask):
    """分镜/镜头表抽取任务（基于 FilmShotlistStoryboarder）。"""

    TASK_KEY = "film_shotlist"

    def __init__(
        self,
        storyboarder: FilmShotlistStoryboarder,
        *,
        input_dict: dict[str, Any],
        skill_id: str = "film_shotlist",
    ) -> None:
        super().__init__()
        self._storyboarder = storyboarder
        self._input_dict = input_dict
        self._skill_id = skill_id
        self._result: FilmShotlistResult | None = None

    async def run(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any] | None:  # type: ignore[override]
        try:
            self._storyboarder.load_skill(self._skill_id)
            self._result = await self._storyboarder.aextract(self._input_dict)
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self._result = None
        return None

    async def get_result(self) -> FilmShotlistResult | None:  # type: ignore[override]
        return self._result


class ShotFramePromptTask(_BaseAsyncResultTask):
    """镜头分镜帧提示词生成任务（首帧/尾帧/关键帧共用）。"""

    TASK_KEY = "shot_frame_prompt"

    def __init__(
        self,
        agent: ShotFirstFramePromptAgent | ShotLastFramePromptAgent | ShotKeyFramePromptAgent,
        *,
        input_dict: dict[str, Any],
        skill_id: str,
    ) -> None:
        super().__init__()
        self._agent = agent
        self._input_dict = input_dict
        self._skill_id = skill_id
        self._result: ShotFramePromptResult | None = None

    async def run(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any] | None:  # type: ignore[override]
        try:
            self._agent.load_skill(self._skill_id)
            self._result = await self._agent.aextract(self._input_dict)
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self._result = None
        return None

    async def status(self) -> dict[str, Any]:  # type: ignore[override]
        base = await super().status()
        base["skill_id"] = self._skill_id
        return base

    async def get_result(self) -> ShotFramePromptResult | None:  # type: ignore[override]
        return self._result

