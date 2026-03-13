"""影视技能定义：数据结构（schemas）、技能实现（prompt + 输出模型）与技能注册表。

- 数据结构与枚举见 schemas。
- 技能说明文档在 backend/skills/*.md。
- 仅维护 skill 定义与 SKILL_REGISTRY；skill 加载与 agent 运行逻辑在 app.chains.agents。
"""

from pydantic import BaseModel

from app.core.skills_runtime.schemas import (
    Character,
    EvidenceSpan,
    Location,
    Prop,
    ProjectCinematicBreakdown,
    Scene,
    Shot,
    Transition,
    Uncertainty,
)
from app.core.skills_runtime.film_entity_extractor import (
    FILM_ENTITY_EXTRACTION_PROMPT,
    FilmEntityExtractionResult,
    TextChunk,
)
from app.core.skills_runtime.film_shotlist_storyboarder import (
    FILM_SHOTLIST_PROMPT,
    FilmShotlistResult,
)
from app.core.skills_runtime.shot_frame_prompt_generator import (
    SHOT_FIRST_FRAME_PROMPT,
    SHOT_LAST_FRAME_PROMPT,
    SHOT_KEY_FRAME_PROMPT,
    ShotFramePromptInput,
    ShotFramePromptResult,
)

from langchain_core.prompts import PromptTemplate

# 技能注册表：skill_id -> (PromptTemplate, 输出 Pydantic 类型)
SKILL_REGISTRY: dict[str, tuple[PromptTemplate, type[BaseModel]]] = {
    "film_entity_extractor": (FILM_ENTITY_EXTRACTION_PROMPT, FilmEntityExtractionResult),
    "film_shotlist": (FILM_SHOTLIST_PROMPT, FilmShotlistResult),
    "shot_first_frame_prompt": (SHOT_FIRST_FRAME_PROMPT, ShotFramePromptResult),
    "shot_last_frame_prompt": (SHOT_LAST_FRAME_PROMPT, ShotFramePromptResult),
    "shot_key_frame_prompt": (SHOT_KEY_FRAME_PROMPT, ShotFramePromptResult),
}

__all__ = [
    # schemas
    "Character",
    "EvidenceSpan",
    "Location",
    "Prop",
    "ProjectCinematicBreakdown",
    "Scene",
    "Shot",
    "Transition",
    "Uncertainty",
    # film entity extraction
    "FILM_ENTITY_EXTRACTION_PROMPT",
    "FilmEntityExtractionResult",
    "TextChunk",
    # film shotlist
    "FILM_SHOTLIST_PROMPT",
    "FilmShotlistResult",
    # shot frame prompt generator
    "SHOT_FIRST_FRAME_PROMPT",
    "SHOT_LAST_FRAME_PROMPT",
    "SHOT_KEY_FRAME_PROMPT",
    "ShotFramePromptInput",
    "ShotFramePromptResult",
    # registry
    "SKILL_REGISTRY",
]
