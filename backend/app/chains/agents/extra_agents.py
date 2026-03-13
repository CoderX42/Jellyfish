"""提取类 Agent：实体抽取、分镜抽取，含影视专用规范化。"""

from __future__ import annotations

from typing import Any

from app.core.skills_runtime import SKILL_REGISTRY
from app.core.skills_runtime.film_entity_extractor import FilmEntityExtractionResult
from app.core.skills_runtime.film_shotlist_storyboarder import FilmShotlistResult

from app.chains.agents.base import SkillAgentBase


# ---------------------------------------------------------------------------
# 影视实体/分镜结果规范化（供 FilmEntityExtractor / FilmShotlistStoryboarder 使用）
# ---------------------------------------------------------------------------


def _normalize_entity_result(data: dict[str, Any]) -> dict[str, Any]:
    """将 LLM 常见字段名/结构映射为 FilmEntityExtractionResult 所需。"""
    data = dict(data)
    for key in ("characters", "locations", "props"):
        if key not in data or not isinstance(data[key], list):
            continue
        out = []
        for item in list(data[key]):
            item = dict(item)
            if "name" not in item and item.get("normalized_name"):
                item["name"] = item["normalized_name"]
            if "evidence" in item:
                ev = item.pop("evidence", [])
                if ev and "first_appearance" not in item:
                    item["first_appearance"] = ev[0] if isinstance(ev[0], dict) else None
            if key != "characters":
                item.pop("aliases", None)
            out.append(item)
        data[key] = out
    if "chunks" not in data:
        data["chunks"] = []
    return data


def _norm_character(c: dict[str, Any]) -> dict[str, Any]:
    c = dict(c)
    if "id" not in c and c.get("character_id"):
        c["id"] = c.pop("character_id")
    return c


def _norm_scene(s: dict[str, Any]) -> dict[str, Any]:
    s = dict(s)
    if "id" not in s and s.get("scene_id"):
        s["id"] = s.pop("scene_id")
    if "summary" not in s and s.get("description"):
        s["summary"] = s.pop("description")
    return s


def _norm_shot(s: dict[str, Any], index: int = 0) -> dict[str, Any]:
    s = dict(s)
    if "id" not in s and s.get("shot_id"):
        s["id"] = s.pop("shot_id")
    if "order" not in s:
        s["order"] = index + 1
    if "evidence_spans" in s:
        s["evidence"] = s.pop("evidence_spans", [])
    if "vfx_type" in s and "vfx" not in s:
        vfx_type = s.pop("vfx_type", "NONE")
        s["vfx"] = [{"vfx_type": vfx_type}]
    return s


def _norm_transition(
    t: dict[str, Any], index: int = 0, shot_ids: list[str] | None = None
) -> dict[str, Any]:
    t = dict(t)
    t.pop("transition_id", None)
    t.pop("evidence_spans", None)
    if "transition" not in t and t.get("transition_type"):
        t["transition"] = t.pop("transition_type")
    if "from_shot_id" not in t or "to_shot_id" not in t:
        shot_ids = shot_ids or []
        if index + 1 < len(shot_ids):
            t.setdefault("from_shot_id", shot_ids[index])
            t.setdefault("to_shot_id", shot_ids[index + 1])
    return t


def _normalize_shotlist_result(data: dict[str, Any]) -> dict[str, Any]:
    """将 LLM 常见字段名/结构映射为 FilmShotlistResult(ProjectCinematicBreakdown) 所需。"""
    if "breakdown" not in data:
        return data
    b = dict(data["breakdown"])
    if "characters" in b:
        b["characters"] = [_norm_character(c) for c in b["characters"]]
    if "scenes" in b:
        b["scenes"] = [_norm_scene(s) for s in b["scenes"]]
    if "shots" in b:
        b["shots"] = [_norm_shot(s, i) for i, s in enumerate(b["shots"])]
    if "transitions" in b:
        shots = b.get("shots") or []
        shot_ids = [
            s.get("id") or (s.get("shot_id") if isinstance(s, dict) else None)
            for s in shots
        ]
        shot_ids = [x for x in shot_ids if x]
        b["transitions"] = [
            _norm_transition(t, i, shot_ids) for i, t in enumerate(b["transitions"])
        ]
    data["breakdown"] = b
    return data


# ---------------------------------------------------------------------------
# 提取类 Agent 实现
# ---------------------------------------------------------------------------


class FilmEntityExtractor(SkillAgentBase[FilmEntityExtractionResult]):
    """关键信息提取：使用 film_entity_extractor skill，输出人物/地点/道具。"""

    KEY_INFO_SKILL_IDS = ("film_entity_extractor",)

    def load_skill(self, skill_id: str) -> None:
        if skill_id not in self.KEY_INFO_SKILL_IDS or skill_id not in SKILL_REGISTRY:
            raise ValueError(
                f"Unknown or invalid key-info skill_id: {skill_id}. "
                f"Allowed: {self.KEY_INFO_SKILL_IDS}"
            )
        self._prompt, self._output_model = SKILL_REGISTRY[skill_id]
        self._skill_id = skill_id
        self._structured_chain = None

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        return _normalize_entity_result(data)


class FilmShotlistStoryboarder(SkillAgentBase[FilmShotlistResult]):
    """分镜提取：使用 film_shotlist skill，输出场景/镜头/转场（ProjectCinematicBreakdown）。"""

    SHOTLIST_SKILL_IDS = ("film_shotlist",)

    def load_skill(self, skill_id: str) -> None:
        if skill_id not in self.SHOTLIST_SKILL_IDS or skill_id not in SKILL_REGISTRY:
            raise ValueError(
                f"Unknown or invalid shotlist skill_id: {skill_id}. "
                f"Allowed: {self.SHOTLIST_SKILL_IDS}"
            )
        self._prompt, self._output_model = SKILL_REGISTRY[skill_id]
        self._skill_id = skill_id
        self._structured_chain = None

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        return _normalize_shotlist_result(data)
