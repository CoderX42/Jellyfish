"""视频生成任务（Task）：对接 OpenAI Videos API 与火山引擎（方舟）内容生成任务。

说明：
- 本模块提供 BaseTask 协议实现，便于接入 TaskManager/路由的 async_polling 模式。
- 任务输入支持：文本 prompt，以及可选的首帧/尾帧/关键帧参考图（file_id 或 url）。
- 任务输出为：视频 url 和/或 file_id（若上层将视频落库为 FileItem）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.task_manager.types import BaseTask

ProviderKey = Literal["openai", "volcengine"]


class VideoGenerationInput(BaseModel):
    """视频生成输入：支持文本提示词 + 可选的三种帧参考图。"""

    model_config = ConfigDict(extra="forbid")

    prompt: Optional[str] = Field(None, description="文本提示词；可与参考图二选一或同时存在")

    first_frame_file_id: Optional[str] = Field(None, description="首帧图片 file_id（可选）")
    first_frame_url: Optional[str] = Field(None, description="首帧图片 URL（可选）")
    last_frame_file_id: Optional[str] = Field(None, description="尾帧图片 file_id（可选）")
    last_frame_url: Optional[str] = Field(None, description="尾帧图片 URL（可选）")
    key_frame_file_id: Optional[str] = Field(None, description="关键帧图片 file_id（可选）")
    key_frame_url: Optional[str] = Field(None, description="关键帧图片 URL（可选）")

    # 通用可选参数（供应商可选择支持/忽略）
    model: Optional[str] = Field(None, description="视频模型名称（可选，供应商透传）")
    size: Optional[str] = Field(None, description="分辨率，如 720x1280（可选，供应商透传）")
    seconds: Optional[int] = Field(None, description="时长（秒）（可选，供应商透传）")

    @model_validator(mode="after")
    def require_prompt_or_any_reference(self) -> "VideoGenerationInput":
        has_prompt = bool((self.prompt or "").strip())
        has_ref = any(
            [
                self.first_frame_file_id,
                self.first_frame_url,
                self.last_frame_file_id,
                self.last_frame_url,
                self.key_frame_file_id,
                self.key_frame_url,
            ]
        )
        if not has_prompt and not has_ref:
            raise ValueError("Require prompt or at least one reference frame (file_id/url)")
        return self


class VideoGenerationResult(BaseModel):
    """视频生成结果：返回视频 URL 和/或 file_id。"""

    model_config = ConfigDict(extra="forbid")

    url: Optional[str] = Field(None, description="生成视频可下载 URL")
    file_id: Optional[str] = Field(None, description="落库后的 FileItem.id（type=video）")
    provider_task_id: Optional[str] = Field(None, description="供应商侧任务/视频 ID（用于调试/追踪）")
    provider: Optional[ProviderKey] = Field(None, description="供应商标识")
    status: Optional[str] = Field(None, description="供应商任务状态")

    @model_validator(mode="after")
    def require_url_or_file_id(self) -> "VideoGenerationResult":
        if not self.url and not self.file_id:
            raise ValueError("Either url or file_id must be set")
        return self


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """供应商配置：由调用方注入，避免在 settings 中硬编码。"""

    provider: ProviderKey
    api_key: str
    base_url: str | None = None


def _pick_openai_reference(input_: VideoGenerationInput) -> dict[str, str] | None:
    """将多参考图收敛为 OpenAI 允许的单一 input_reference。

优先级：key_frame > first_frame > last_frame；每类优先 file_id，其次 url。
"""

    if input_.key_frame_file_id:
        return {"file_id": input_.key_frame_file_id}
    if input_.key_frame_url:
        return {"image_url": input_.key_frame_url}
    if input_.first_frame_file_id:
        return {"file_id": input_.first_frame_file_id}
    if input_.first_frame_url:
        return {"image_url": input_.first_frame_url}
    if input_.last_frame_file_id:
        return {"file_id": input_.last_frame_file_id}
    if input_.last_frame_url:
        return {"image_url": input_.last_frame_url}
    return None


class VideoGenerationTask(BaseTask):
    """视频生成任务（async_result 模式）。"""

    def __init__(
        self,
        *,
        provider_config: ProviderConfig,
        input_: VideoGenerationInput,
        poll_interval_s: float = 2.0,
        timeout_s: float = 120.0,
    ) -> None:
        self._cfg = provider_config
        self._input = input_
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s
        self._provider_task_id: str | None = None
        self._result: VideoGenerationResult | None = None
        self._error: str = ""

    async def run(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any] | None:  # type: ignore[override]
        try:
            if self._cfg.provider == "openai":
                self._result = await self._run_openai()
            elif self._cfg.provider == "volcengine":
                self._result = await self._run_volcengine()
            else:
                raise ValueError(f"Unsupported provider: {self._cfg.provider!r}")
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self._result = None
        return None

    async def status(self) -> dict[str, Any]:  # type: ignore[override]
        return {
            "task": "video_generation",
            "provider": self._cfg.provider,
            "provider_task_id": self._provider_task_id,
            "done": await self.is_done(),
            "has_result": self._result is not None,
            "error": self._error,
            "status": self._result.status if self._result else None,
        }

    async def is_done(self) -> bool:  # type: ignore[override]
        return self._result is not None or bool(self._error)

    async def get_result(self) -> VideoGenerationResult | None:  # type: ignore[override]
        return self._result

    async def _run_openai(self) -> VideoGenerationResult:
        """OpenAI Videos API：POST /videos -> 轮询 GET /videos/{id} -> 返回 content endpoint URL。

说明：OpenAI 的 `/videos/{id}/content` 返回视频二进制流；本任务返回该 endpoint URL（需鉴权下载）。
上层若要落库，可自行下载并创建 FileItem(type=video)，再写入 Shot.generated_video_file_id。
"""

        import asyncio

        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("httpx is required for video generation tasks") from e

        base_url = (self._cfg.base_url or "https://api.openai.com/v1").rstrip("/")
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {"prompt": self._input.prompt or ""}
        if self._input.model:
            body["model"] = self._input.model
        if self._input.size:
            body["size"] = self._input.size
        if self._input.seconds:
            body["seconds"] = str(int(self._input.seconds))

        ref = _pick_openai_reference(self._input)
        if ref:
            body["input_reference"] = ref

        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            r = await client.post(f"{base_url}/videos", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            video_id = str(data.get("id") or "")
            if not video_id:
                raise RuntimeError(f"OpenAI /videos missing id: {data!r}")
            self._provider_task_id = video_id

            status_val = ""
            while True:
                rr = await client.get(
                    f"{base_url}/videos/{video_id}",
                    headers={"Authorization": headers["Authorization"]},
                )
                rr.raise_for_status()
                meta = rr.json()
                status_val = str(meta.get("status") or "")
                if status_val in ("completed", "failed"):
                    if status_val == "failed":
                        raise RuntimeError(f"OpenAI video failed: {meta.get('error')!r}")
                    break
                await asyncio.sleep(self._poll_interval_s)

        return VideoGenerationResult(
            url=f"{base_url}/videos/{video_id}/content",
            file_id=None,
            provider_task_id=video_id,
            provider="openai",
            status=status_val or "completed",
        )

    async def _run_volcengine(self) -> VideoGenerationResult:
        """火山引擎（方舟）内容生成任务。

Base URL（Apifox 公开文档）：`https://ark.cn-beijing.volces.com/api/v3`
鉴权：Bearer ARK_API_KEY

说明：不同模型的创建请求体字段可能不同；这里采用最小通用字段：prompt，并将 refs 作为 `references` 透传。
"""

        import asyncio

        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("httpx is required for video generation tasks") from e

        base_url = (self._cfg.base_url or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }

        refs: dict[str, Any] = {}
        if self._input.first_frame_file_id or self._input.first_frame_url:
            refs["first_frame"] = {
                "file_id": self._input.first_frame_file_id,
                "url": self._input.first_frame_url,
            }
        if self._input.last_frame_file_id or self._input.last_frame_url:
            refs["last_frame"] = {
                "file_id": self._input.last_frame_file_id,
                "url": self._input.last_frame_url,
            }
        if self._input.key_frame_file_id or self._input.key_frame_url:
            refs["key_frame"] = {
                "file_id": self._input.key_frame_file_id,
                "url": self._input.key_frame_url,
            }

        body: dict[str, Any] = {"prompt": self._input.prompt or ""}
        if self._input.model:
            body["model"] = self._input.model
        if self._input.size:
            body["size"] = self._input.size
        if self._input.seconds:
            body["seconds"] = int(self._input.seconds)
        if refs:
            body["references"] = refs

        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            r = await client.post(f"{base_url}/contents/generations/tasks", headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            task_id = str(data.get("id") or data.get("task_id") or "")
            if not task_id:
                raise RuntimeError(f"Volcengine create missing id: {data!r}")
            self._provider_task_id = task_id

            status_val = ""
            video_url: str | None = None
            while True:
                rr = await client.get(f"{base_url}/contents/generations/tasks/{task_id}", headers=headers)
                rr.raise_for_status()
                meta = rr.json()
                status_val = str(meta.get("status") or "")
                content = meta.get("content") or {}
                if isinstance(content, dict):
                    vu = content.get("video_url")
                    if isinstance(vu, str) and vu:
                        video_url = vu
                if status_val in ("succeeded", "failed", "cancelled"):
                    if status_val != "succeeded":
                        raise RuntimeError(f"Volcengine task not succeeded: status={status_val!r} meta={meta!r}")
                    break
                await asyncio.sleep(self._poll_interval_s)

        if not video_url:
            # 成功但未返回 video_url：保底返回查询 URL
            video_url = f"{base_url}/contents/generations/tasks/{task_id}"

        return VideoGenerationResult(
            url=video_url,
            file_id=None,
            provider_task_id=task_id,
            provider="volcengine",
            status=status_val or "succeeded",
        )

