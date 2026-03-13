from __future__ import annotations

from pydantic import BaseModel, Field

from .common import BindTarget


class ImageInputRef(BaseModel):
    """参考图片：与 ImageGenerationInput.InputImageRef 对齐。"""

    file_id: str | None = Field(
        None,
        description="文件 ID（用于 OpenAI File API；火山可忽略）",
    )
    image_url: str | None = Field(
        None,
        description="完整 URL 或 base64 data URL；火山 image[] 建议使用该字段",
    )


class ImageGenerationTaskRequest(BindTarget):
    """图片生成任务请求：可选绑定到 project/chapter/shot。"""

    provider: str = Field(..., description="供应商：openai | volcengine")
    api_key: str | None = Field(
        None,
        description="供应商 API Key（可选）；不传则使用配置 IMAGE_API_KEY",
    )
    base_url: str | None = Field(
        None,
        description="供应商 base_url（可选）；不传则使用配置 IMAGE_API_BASE_URL",
    )

    # 输入（与 ImageGenerationInput 对齐）
    prompt: str = Field(..., description="文本提示词")
    images: list[ImageInputRef] = Field(
        default_factory=list,
        description="参考图片列表；存在时 OpenAI 走 /images/edits，火山 ImageGenerations 使用 image[]",
    )

    model: str = Field(..., description="图片模型名称（必填）")
    size: str | None = Field(None, description="分辨率（可选），如 1024x1024")
    n: int = Field(1, description="生成图片数量；部分模型仅支持 n=1")
    seed: int | None = Field(None, description="随机种子（火山 ImageGenerations 支持）")
    response_format: str = Field(
        "url",
        description="OpenAI 返回格式：url 或 b64_json；火山一般仅支持 url",
    )

