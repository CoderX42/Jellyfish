"""通用 Skill Agent 基类：按 skill_id 加载 skill、调用 agent、格式化输出。

不局限于信息提取；子类通过 load_skill 与可选 _normalize 钩子绑定具体技能与规范化逻辑。
当 agent 支持 with_structured_output 时优先使用，否则走「原始字符串 → JSON 解析 → 规范化 → 校验」。
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, cast

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from app.core.skills_runtime import SKILL_REGISTRY

STRUCTURED_OUTPUT_METHOD = "function_calling"

T = TypeVar("T", bound=BaseModel)


def _extract_json_from_text(raw: str) -> str:
    """从 LLM 原始输出中剥离 markdown 代码块并提取 JSON 字符串。"""
    text = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


class SkillAgentBase(ABC, Generic[T]):
    """通用 Skill Agent 基类：加载 skill、调用 agent、格式化输出。"""

    def __init__(
        self,
        agent: Runnable,
        *,
        structured_output_method: str = STRUCTURED_OUTPUT_METHOD,
    ) -> None:
        self._agent = agent
        self._structured_output_method = structured_output_method
        self._prompt: PromptTemplate | None = None
        self._output_model: type[BaseModel] | None = None
        self._skill_id: str | None = None
        self._structured_chain: Runnable | None = None

    @property
    def skill_id(self) -> str | None:
        return self._skill_id

    @abstractmethod
    def load_skill(self, skill_id: str) -> None:
        """按 skill_id 加载 skill（设置 prompt 与 output_model）。"""
        ...

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        """子类可覆盖：将 LLM 返回的 dict 规范化为 output_model 所需结构。默认 identity。"""
        return data

    def _ensure_loaded(self) -> None:
        if self._prompt is None or self._output_model is None:
            raise RuntimeError(
                "Skill not loaded; call load_skill(skill_id) first. "
                f"Available: {list(SKILL_REGISTRY.keys())}"
            )

    def _build_structured_chain(self) -> Runnable | None:
        """若 agent 支持 with_structured_output，则构建 prompt | agent.with_structured_output(schema)。"""
        self._ensure_loaded()
        with_structured = getattr(self._agent, "with_structured_output", None)
        if not callable(with_structured):
            return None
        assert self._prompt is not None and self._output_model is not None
        structured_llm = cast(
            Runnable,
            with_structured(
                self._output_model,
                method=self._structured_output_method,
            ),
        )
        return self._prompt | structured_llm

    def _get_structured_chain(self) -> Runnable | None:
        if self._structured_chain is not None:
            return self._structured_chain
        self._structured_chain = self._build_structured_chain()
        return self._structured_chain

    def run(self, input_dict: dict[str, Any]) -> str:
        """调用 agent，返回原始字符串（通常为 JSON）。"""
        self._ensure_loaded()
        assert self._prompt is not None
        chain: Runnable = self._prompt | self._agent
        result = chain.invoke(input_dict)
        if hasattr(result, "content"):
            return getattr(result, "content", str(result))
        return str(result)

    async def arun(self, input_dict: dict[str, Any]) -> str:
        """异步调用 agent。"""
        self._ensure_loaded()
        assert self._prompt is not None
        chain: Runnable = self._prompt | self._agent
        result = await chain.ainvoke(input_dict)
        if hasattr(result, "content"):
            return getattr(result, "content", str(result))
        return str(result)

    def format_output(self, raw: str) -> T:
        """将 agent 原始输出解析为结构化结果（JSON → 规范化 → Pydantic）。"""
        self._ensure_loaded()
        assert self._output_model is not None
        json_str = _extract_json_from_text(raw)
        data = json.loads(json_str)
        if isinstance(data, dict):
            data = self._normalize(data)
        return self._output_model.model_validate(data)  # type: ignore[return-value]

    def extract(self, input_dict: dict[str, Any]) -> T:
        """执行：优先 with_structured_output，否则 run + format_output。"""
        chain = self._get_structured_chain()
        if chain is not None:
            result = chain.invoke(input_dict)
            if isinstance(result, BaseModel):
                return result  # type: ignore[return-value]
            if isinstance(result, dict):
                data = self._normalize(result)
                return self._output_model.model_validate(data)  # type: ignore[return-value]
        raw = self.run(input_dict)
        return self.format_output(raw)

    async def aextract(self, input_dict: dict[str, Any]) -> T:
        """异步执行。"""
        chain = self._get_structured_chain()
        if chain is not None:
            result = await chain.ainvoke(input_dict)
            if isinstance(result, BaseModel):
                return result  # type: ignore[return-value]
            if isinstance(result, dict):
                data = self._normalize(result)
                return self._output_model.model_validate(data)  # type: ignore[return-value]
        raw = await self.arun(input_dict)
        return self.format_output(raw)
