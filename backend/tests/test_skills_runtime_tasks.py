from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.chains.agents import FilmEntityExtractor, FilmShotlistStoryboarder
from app.core.tasks.extra_tasks import FilmEntityExtractionTask, FilmShotlistTask


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


@pytest.mark.asyncio
async def test_film_entity_extraction_task_async_result() -> None:
    agent = RunnableLambda(_mock_entity_response)
    extractor = FilmEntityExtractor(agent)
    task = FilmEntityExtractionTask(
        extractor,
        input_dict={"source_id": "novel_ch01", "language": "zh", "chunks_json": "[]"},
    )

    assert await task.is_done() is False
    assert await task.get_result() is None

    await task.run()
    assert await task.is_done() is True
    result = await task.get_result()
    assert result is not None
    assert result.source_id == "novel_ch01"

    st = await task.status()
    assert st["done"] is True
    assert st["has_result"] is True
    assert st["error"] == ""


@pytest.mark.asyncio
async def test_film_shotlist_task_async_result() -> None:
    agent = RunnableLambda(_mock_shotlist_response)
    storyboarder = FilmShotlistStoryboarder(agent)
    task = FilmShotlistTask(
        storyboarder,
        input_dict={"source_id": "novel_ch01", "source_title": "", "language": "zh", "chunks_json": "[]"},
    )

    await task.run()
    result = await task.get_result()
    assert result is not None
    assert result.breakdown.source_id == "novel_ch01"


@pytest.mark.asyncio
async def test_task_records_error_when_skill_invalid() -> None:
    agent = RunnableLambda(_mock_entity_response)
    extractor = FilmEntityExtractor(agent)
    task = FilmEntityExtractionTask(
        extractor,
        input_dict={"source_id": "novel_ch01", "language": "zh", "chunks_json": "[]"},
        skill_id="invalid_skill",
    )

    await task.run()
    assert await task.get_result() is None
    st = await task.status()
    assert st["done"] is True
    assert st["has_result"] is False
    assert st["error"]

