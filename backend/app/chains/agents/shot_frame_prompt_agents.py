"""镜头分镜首帧/尾帧/关键帧提示词生成 Agent：根据镜头信息生成对应帧的画面提示词。"""

from __future__ import annotations

import json
from typing import Any

from app.core.skills_runtime import SKILL_REGISTRY
from app.core.skills_runtime.shot_frame_prompt_generator import ShotFramePromptResult
from app.chains.agents.base import SkillAgentBase, _extract_json_from_text


def _prepare_shot_frame_input(input_dict: dict[str, Any]) -> dict[str, Any]:
    """将 input_dict 转为 prompt 模板所需格式，mood_tags 转为字符串。"""
    out = dict(input_dict)
    if "mood_tags" in out and isinstance(out["mood_tags"], list):
        out["mood_tags"] = ", ".join(str(t) for t in out["mood_tags"])
    else:
        out.setdefault("mood_tags", "")
    for key in ("camera_shot", "angle", "movement", "atmosphere", "vfx_type", "vfx_note", "duration", "scene_id", "dialog_summary"):
        if key not in out or out[key] is None:
            out[key] = ""
    out.setdefault("title", "")
    return out


class ShotFirstFramePromptAgent(SkillAgentBase[ShotFramePromptResult]):
    """镜头首帧提示词生成 Agent，输出可写入 ShotDetail.first_frame_prompt。"""

    SKILL_ID = "shot_first_frame_prompt"

    def load_skill(self, skill_id: str = "shot_first_frame_prompt") -> None:
        if skill_id not in (self.SKILL_ID,) or skill_id not in SKILL_REGISTRY:
            raise ValueError(f"Invalid skill_id: {skill_id}. Allowed: ({self.SKILL_ID},)")
        self._prompt, self._output_model = SKILL_REGISTRY[skill_id]
        self._skill_id = skill_id
        self._structured_chain = None

    def format_output(self, raw: str) -> ShotFramePromptResult:
        self._ensure_loaded()
        json_str = _extract_json_from_text(raw)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return ShotFramePromptResult(prompt=raw.strip())
        if isinstance(data, dict) and "prompt" in data:
            return ShotFramePromptResult(prompt=str(data["prompt"]).strip())
        return ShotFramePromptResult(prompt=raw.strip())

    def extract(self, input_dict: dict[str, Any]) -> ShotFramePromptResult:
        inp = _prepare_shot_frame_input(input_dict)
        raw = self.run(inp)
        return self.format_output(raw)

    async def aextract(self, input_dict: dict[str, Any]) -> ShotFramePromptResult:
        inp = _prepare_shot_frame_input(input_dict)
        raw = await self.arun(inp)
        return self.format_output(raw)


class ShotLastFramePromptAgent(SkillAgentBase[ShotFramePromptResult]):
    """镜头尾帧提示词生成 Agent，输出可写入 ShotDetail.last_frame_prompt。"""

    SKILL_ID = "shot_last_frame_prompt"

    def load_skill(self, skill_id: str = "shot_last_frame_prompt") -> None:
        if skill_id not in (self.SKILL_ID,) or skill_id not in SKILL_REGISTRY:
            raise ValueError(f"Invalid skill_id: {skill_id}. Allowed: ({self.SKILL_ID},)")
        self._prompt, self._output_model = SKILL_REGISTRY[skill_id]
        self._skill_id = skill_id
        self._structured_chain = None

    def format_output(self, raw: str) -> ShotFramePromptResult:
        self._ensure_loaded()
        json_str = _extract_json_from_text(raw)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return ShotFramePromptResult(prompt=raw.strip())
        if isinstance(data, dict) and "prompt" in data:
            return ShotFramePromptResult(prompt=str(data["prompt"]).strip())
        return ShotFramePromptResult(prompt=raw.strip())

    def extract(self, input_dict: dict[str, Any]) -> ShotFramePromptResult:
        inp = _prepare_shot_frame_input(input_dict)
        raw = self.run(inp)
        return self.format_output(raw)

    async def aextract(self, input_dict: dict[str, Any]) -> ShotFramePromptResult:
        inp = _prepare_shot_frame_input(input_dict)
        raw = await self.arun(inp)
        return self.format_output(raw)


class ShotKeyFramePromptAgent(SkillAgentBase[ShotFramePromptResult]):
    """镜头关键帧提示词生成 Agent，输出可写入 ShotDetail.key_frame_prompt。"""

    SKILL_ID = "shot_key_frame_prompt"

    def load_skill(self, skill_id: str = "shot_key_frame_prompt") -> None:
        if skill_id not in (self.SKILL_ID,) or skill_id not in SKILL_REGISTRY:
            raise ValueError(f"Invalid skill_id: {skill_id}. Allowed: ({self.SKILL_ID},)")
        self._prompt, self._output_model = SKILL_REGISTRY[skill_id]
        self._skill_id = skill_id
        self._structured_chain = None

    def format_output(self, raw: str) -> ShotFramePromptResult:
        self._ensure_loaded()
        json_str = _extract_json_from_text(raw)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return ShotFramePromptResult(prompt=raw.strip())
        if isinstance(data, dict) and "prompt" in data:
            return ShotFramePromptResult(prompt=str(data["prompt"]).strip())
        return ShotFramePromptResult(prompt=raw.strip())

    def extract(self, input_dict: dict[str, Any]) -> ShotFramePromptResult:
        inp = _prepare_shot_frame_input(input_dict)
        raw = self.run(inp)
        return self.format_output(raw)

    async def aextract(self, input_dict: dict[str, Any]) -> ShotFramePromptResult:
        inp = _prepare_shot_frame_input(input_dict)
        raw = await self.arun(inp)
        return self.format_output(raw)
