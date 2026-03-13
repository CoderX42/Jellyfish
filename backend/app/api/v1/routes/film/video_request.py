from __future__ import annotations

from pydantic import BaseModel, Field

from .common import BindTarget


class VideoGenerationTaskRequest(BindTarget):
    """视频生成任务请求：可选绑定到 project/chapter/shot。"""

    provider: str = Field(..., description="供应商：openai | volcengine")
    api_key: str = Field(..., description="供应商 API Key（Bearer）")
    base_url: str | None = Field(None, description="供应商 base_url（可选）")

    # 输入（与 VideoGenerationInput 对齐）
    prompt: str | None = Field(None, description="文本提示词（可选）")
    first_frame_file_id: str | None = Field(None, description="首帧图片 file_id（可选）")
    first_frame_url: str | None = Field(None, description="首帧图片 URL（可选）")
    last_frame_file_id: str | None = Field(None, description="尾帧图片 file_id（可选）")
    last_frame_url: str | None = Field(None, description="尾帧图片 URL（可选）")
    key_frame_file_id: str | None = Field(None, description="关键帧图片 file_id（可选）")
    key_frame_url: str | None = Field(None, description="关键帧图片 URL（可选）")

    model: str | None = Field(None, description="视频模型名称（可选）")
    size: str | None = Field(None, description="分辨率（可选），如 720x1280")
    seconds: int | None = Field(None, description="时长（秒）（可选）")

