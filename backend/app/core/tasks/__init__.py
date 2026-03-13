"""Tasks for the skills runtime."""

from app.core.tasks.extra_tasks import FilmEntityExtractionTask, FilmShotlistTask
from app.core.tasks.video_generation_tasks import (
    ProviderConfig,
    VideoGenerationInput,
    VideoGenerationResult,
    VideoGenerationTask,
)
from app.core.tasks.image_generation_tasks import (
    ImageGenerationInput,
    ImageGenerationResult,
    ImageGenerationTask,
)
from app.core.tasks.agent_tasks import (
    FilmEntityExtractionTask2,
    FilmShotlistTask2,
    ShotFramePromptTask,
)

__all__ = [
    "FilmEntityExtractionTask",
    "FilmShotlistTask",
    "ProviderConfig",
    "VideoGenerationInput",
    "VideoGenerationResult",
    "VideoGenerationTask",
    "ImageGenerationInput",
    "ImageGenerationResult",
    "ImageGenerationTask",
    "FilmEntityExtractionTask2",
    "FilmShotlistTask2",
    "ShotFramePromptTask",
]
