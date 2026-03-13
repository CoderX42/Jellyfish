"""FilmEntityExtractor 与 FilmShotlistStoryboarder 实现类的单元测试。"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.chains.agents import FilmEntityExtractor, FilmShotlistStoryboarder
from app.core.skills_runtime import (
    FilmEntityExtractionResult,
    FilmShotlistResult,
    SKILL_REGISTRY,
)


# ---------- Mock agents ----------


def _mock_entity_response(_: object) -> AIMessage:
    return AIMessage(
        content='{"source_id": "novel_ch01", "chunks": ["c1"], "characters": [], '
        '"locations": [], "props": [], "notes": [], "uncertainties": []}'
    )


def _mock_shotlist_response(_: object) -> AIMessage:
    return AIMessage(
        content='{"breakdown": {"source_id": "novel_ch01", "chunks": [], '
        '"characters": [], "locations": [], "props": [], "scenes": [], '
        '"shots": [], "transitions": [], "notes": [], "uncertainties": []}}'
    )


# ---------- FilmEntityExtractor ----------


class TestFilmEntityExtractor:
    """FilmEntityExtractor 单元测试。"""

    def test_load_skill_success(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        extractor.load_skill("film_entity_extractor")
        assert extractor.skill_id == "film_entity_extractor"

    def test_load_skill_invalid_id_raises(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        with pytest.raises(ValueError, match="Unknown or invalid key-info skill_id"):
            extractor.load_skill("film_shotlist")
        with pytest.raises(ValueError, match="Unknown or invalid key-info skill_id"):
            extractor.load_skill("unknown_skill")

    def test_run_without_load_skill_raises(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        with pytest.raises(RuntimeError, match="Skill not loaded"):
            extractor.run({"source_id": "x", "language": "zh", "chunks_json": "[]"})

    def test_format_output_without_load_skill_raises(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        with pytest.raises(RuntimeError, match="Skill not loaded"):
            extractor.format_output('{"source_id":"x","chunks":[],"characters":[],"locations":[],"props":[],"notes":[],"uncertainties":[]}')

    def test_format_output_plain_json(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        extractor.load_skill("film_entity_extractor")
        raw = '{"source_id": "e1", "chunks": [], "characters": [], "locations": [], "props": [], "notes": [], "uncertainties": []}'
        result = extractor.format_output(raw)
        assert isinstance(result, FilmEntityExtractionResult)
        assert result.source_id == "e1"
        assert result.characters == []
        assert result.locations == []
        assert result.props == []

    def test_format_output_markdown_wrapped_json(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        extractor.load_skill("film_entity_extractor")
        raw = '```json\n{"source_id": "e2", "chunks": [], "characters": [], "locations": [], "props": [], "notes": [], "uncertainties": []}\n```'
        result = extractor.format_output(raw)
        assert isinstance(result, FilmEntityExtractionResult)
        assert result.source_id == "e2"

    def test_format_output_invalid_json_raises(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        extractor.load_skill("film_entity_extractor")
        with pytest.raises((ValueError, Exception)):  # json.JSONDecodeError or pydantic.ValidationError
            extractor.format_output("not valid json")

    def test_extract_end_to_end(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        extractor.load_skill("film_entity_extractor")
        result = extractor.extract(
            {"source_id": "novel_ch01", "language": "zh", "chunks_json": "[{\"chunk_id\":\"c1\",\"text\":\"张三走进客厅\"}]"}
        )
        assert isinstance(result, FilmEntityExtractionResult)
        assert result.source_id == "novel_ch01"
        assert result.chunks == ["c1"]

    @pytest.mark.asyncio
    async def test_aextract_end_to_end(self) -> None:
        agent = RunnableLambda(_mock_entity_response)
        extractor = FilmEntityExtractor(agent)
        extractor.load_skill("film_entity_extractor")
        result = await extractor.aextract(
            {"source_id": "novel_ch01", "language": "zh", "chunks_json": "[]"}
        )
        assert isinstance(result, FilmEntityExtractionResult)
        assert result.source_id == "novel_ch01"


# ---------- FilmShotlistStoryboarder ----------


class TestFilmShotlistStoryboarder:
    """FilmShotlistStoryboarder 单元测试。"""

    def test_load_skill_success(self) -> None:
        agent = RunnableLambda(_mock_shotlist_response)
        storyboarder = FilmShotlistStoryboarder(agent)
        storyboarder.load_skill("film_shotlist")
        assert storyboarder.skill_id == "film_shotlist"

    def test_load_skill_invalid_id_raises(self) -> None:
        agent = RunnableLambda(_mock_shotlist_response)
        storyboarder = FilmShotlistStoryboarder(agent)
        with pytest.raises(ValueError, match="Unknown or invalid shotlist skill_id"):
            storyboarder.load_skill("film_entity_extractor")
        with pytest.raises(ValueError, match="Unknown or invalid shotlist skill_id"):
            storyboarder.load_skill("unknown_skill")

    def test_run_without_load_skill_raises(self) -> None:
        agent = RunnableLambda(_mock_shotlist_response)
        storyboarder = FilmShotlistStoryboarder(agent)
        with pytest.raises(RuntimeError, match="Skill not loaded"):
            storyboarder.run(
                {"source_id": "x", "source_title": "", "language": "zh", "chunks_json": "[]"}
            )

    def test_format_output_valid_breakdown(self) -> None:
        agent = RunnableLambda(_mock_shotlist_response)
        storyboarder = FilmShotlistStoryboarder(agent)
        storyboarder.load_skill("film_shotlist")
        raw = (
            '{"breakdown": {"source_id": "ch01", "chunks": [], "characters": [], '
            '"locations": [], "props": [], "scenes": [], "shots": [], '
            '"transitions": [], "notes": [], "uncertainties": []}}'
        )
        result = storyboarder.format_output(raw)
        assert isinstance(result, FilmShotlistResult)
        assert result.breakdown.source_id == "ch01"
        assert result.breakdown.shots == []
        assert result.breakdown.scenes == []

    def test_extract_end_to_end(self) -> None:
        agent = RunnableLambda(_mock_shotlist_response)
        storyboarder = FilmShotlistStoryboarder(agent)
        storyboarder.load_skill("film_shotlist")
        result = storyboarder.extract(
            {
                "source_id": "novel_ch01",
                "source_title": "第一章",
                "language": "zh",
                "chunks_json": "[]",
            }
        )
        assert isinstance(result, FilmShotlistResult)
        assert result.breakdown.source_id == "novel_ch01"
        assert result.breakdown.scenes == []
        assert result.breakdown.shots == []

    @pytest.mark.asyncio
    async def test_aextract_end_to_end(self) -> None:
        agent = RunnableLambda(_mock_shotlist_response)
        storyboarder = FilmShotlistStoryboarder(agent)
        storyboarder.load_skill("film_shotlist")
        result = await storyboarder.aextract(
            {"source_id": "novel_ch01", "source_title": "", "language": "zh", "chunks_json": "[]"}
        )
        assert isinstance(result, FilmShotlistResult)
        assert result.breakdown.source_id == "novel_ch01"


# ---------- SKILL_REGISTRY ----------


class TestSkillRegistry:
    """技能注册表与实现类对应关系。"""

    def test_registry_has_expected_skills(self) -> None:
        assert "film_entity_extractor" in SKILL_REGISTRY
        assert "film_shotlist" in SKILL_REGISTRY
        prompt_entity, model_entity = SKILL_REGISTRY["film_entity_extractor"]
        assert model_entity is FilmEntityExtractionResult
        assert "source_id" in prompt_entity.input_variables
        prompt_shot, model_shot = SKILL_REGISTRY["film_shotlist"]
        assert model_shot is FilmShotlistResult
        assert "source_id" in prompt_shot.input_variables and "source_title" in prompt_shot.input_variables
