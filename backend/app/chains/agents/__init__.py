"""Skill 加载与 Agent 运行：通用基类与提取类/提示词类 agent。"""

from app.chains.agents.base import SkillAgentBase, STRUCTURED_OUTPUT_METHOD
from app.chains.agents.extra_agents import FilmEntityExtractor, FilmShotlistStoryboarder
from app.chains.agents.shot_frame_prompt_agents import (
    ShotFirstFramePromptAgent,
    ShotLastFramePromptAgent,
    ShotKeyFramePromptAgent,
)

__all__ = [
    "SkillAgentBase",
    "STRUCTURED_OUTPUT_METHOD",
    "FilmEntityExtractor",
    "FilmShotlistStoryboarder",
    "ShotFirstFramePromptAgent",
    "ShotLastFramePromptAgent",
    "ShotKeyFramePromptAgent",
]
