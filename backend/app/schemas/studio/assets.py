"""资产（ActorImage/Scene/Prop/Costume）及其图片表的 schemas。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.studio import AssetQualityLevel, AssetViewAngle


class AssetBase(BaseModel):
    id: str = Field(..., description="资产 ID")
    project_id: str | None = Field(None, description="归属项目 ID（可空=全局资产）")
    chapter_id: str | None = Field(None, description="归属章节 ID（可空）")
    name: str = Field(..., description="名称")
    description: str = Field("", description="描述")
    thumbnail: str = Field("", description="缩略图 URL")
    tags: list[str] = Field(default_factory=list, description="标签")
    prompt_template_id: str | None = Field(None, description="提示词模板 ID（可空）")


class AssetCreate(BaseModel):
    id: str
    project_id: str | None = None
    chapter_id: str | None = None
    name: str
    description: str = ""
    thumbnail: str = ""
    tags: list[str] = Field(default_factory=list)
    prompt_template_id: str | None = None


class AssetUpdate(BaseModel):
    project_id: str | None = None
    chapter_id: str | None = None
    name: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    tags: list[str] | None = None
    prompt_template_id: str | None = None


class AssetRead(AssetBase):
    class Config:
        from_attributes = True


class AssetImageBase(BaseModel):
    id: int = Field(..., description="图片行 ID")
    quality_level: AssetQualityLevel = Field(AssetQualityLevel.low, description="精度等级")
    view_angle: AssetViewAngle = Field(AssetViewAngle.front, description="视角")
    file_id: str = Field(..., description="关联的 FileItem ID")
    width: int | None = Field(None, description="宽(px)")
    height: int | None = Field(None, description="高(px)")
    format: str = Field("png", description="格式")
    is_primary: bool = Field(False, description="是否主图")


class AssetImageCreate(BaseModel):
    quality_level: AssetQualityLevel = AssetQualityLevel.low
    view_angle: AssetViewAngle = AssetViewAngle.front
    file_id: str
    width: int | None = None
    height: int | None = None
    format: str = "png"
    is_primary: bool = False


class AssetImageUpdate(BaseModel):
    quality_level: AssetQualityLevel | None = None
    view_angle: AssetViewAngle | None = None
    file_id: str | None = None
    width: int | None = None
    height: int | None = None
    format: str | None = None
    is_primary: bool | None = None


class ActorImageRead(AssetRead):
    pass


class SceneRead(AssetRead):
    pass


class PropRead(AssetRead):
    pass


class CostumeRead(AssetRead):
    pass


class ActorImageImageRead(AssetImageBase):
    actor_image_id: str

    class Config:
        from_attributes = True


class SceneImageRead(AssetImageBase):
    scene_id: str

    class Config:
        from_attributes = True


class PropImageRead(AssetImageBase):
    prop_id: str

    class Config:
        from_attributes = True


class CostumeImageRead(AssetImageBase):
    costume_id: str

    class Config:
        from_attributes = True


class CharacterImageRead(AssetImageBase):
    character_id: str

    class Config:
        from_attributes = True

