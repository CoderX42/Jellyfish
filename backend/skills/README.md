# 影视类 Skills 说明文档

本目录仅存放 **skill 的说明文档**（`.md`），便于产品、策划与开发统一查阅。

## 文档列表

| 文档 | 说明 |
|------|------|
| [film_entity_extractor.md](film_entity_extractor.md) | 信息抽取：从小说文本抽取人物、地点、道具，忠实原文、可追溯证据 |
| [film_shotlist_storyboarder.md](film_shotlist_storyboarder.md) | 分镜师：将小说片段转为可拍镜头表（景别/机位/运镜/转场/VFX） |
| [actor_image_generator.md](actor_image_generator.md) | 演员形象/立绘生成：根据名称、描述、风格生成一张或多张角色立绘图片 |
| [character_image_generator.md](character_image_generator.md) | 角色图片生成：根据角色名称、描述、风格生成一张或多张角色图片 |
| [prop_image_generator.md](prop_image_generator.md) | 道具图片生成：根据道具名称、描述、风格生成一张或多张道具图片 |
| [scene_image_generator.md](scene_image_generator.md) | 场景图片生成：根据场景名称、描述、风格生成一张或多张场景图片 |
| [costume_image_generator.md](costume_image_generator.md) | 服装图片生成：根据服装名称、描述、风格生成一张或多张服装图片 |
| [shot_first_frame_prompt_generator.md](shot_first_frame_prompt_generator.md) | 镜头分镜首帧提示词生成 |
| [shot_last_frame_prompt_generator.md](shot_last_frame_prompt_generator.md) | 镜头分镜尾帧提示词生成 |
| [shot_key_frame_prompt_generator.md](shot_key_frame_prompt_generator.md) | 镜头分镜关键帧提示词生成 |
| [shot_frame_image_generator.md](shot_frame_image_generator.md) | （已废弃）镜头分镜帧图片生成（通过 frame_type 控制首/尾/关键帧） |

## 代码与调用

- **数据结构与枚举**：`app.core.skills_runtime.schemas`
- **技能定义**（Prompt + 输出模型，仅维护）：`app.core.skills_runtime`
  - 信息抽取：`film_entity_extractor` → `FILM_ENTITY_EXTRACTION_PROMPT`、`FilmEntityExtractionResult`
  - 分镜师：`film_shotlist_storyboarder` → `FILM_SHOTLIST_PROMPT`、`FilmShotlistResult`
  - 演员形象/立绘生成：`actor_image_generator` → `ACTOR_IMAGE_GENERATION_PROMPT`、`ActorImageGenerationResult`
  - 角色图片生成：`character_image_generator` → `CHARACTER_IMAGE_GENERATION_PROMPT`、`CharacterImageGenerationResult`
  - 道具/场景/服装图片生成：`prop_image_generator`、`scene_image_generator`、`costume_image_generator` → 对应 PROMPT 与 Result
  - 镜头分镜帧提示词：`shot_first_frame_prompt`、`shot_last_frame_prompt`、`shot_key_frame_prompt` → 对应 PROMPT、`ShotFramePromptResult`
  - 镜头分镜帧图片：`shot_frame_image_generator`（已废弃）
- **Skill 加载与 Agent 运行**：`app.chains.agents`（提取类见 `extra_agents.py`，生成类见 `actor_image_agent.py`、`character_image_agent.py`、`asset_image_agents.py`、`shot_frame_prompt_agents.py`、`shot_frame_image_agent.py`）

从应用层引用技能定义与结果类型：

```python
from app.core.skills_runtime import (
    FILM_ENTITY_EXTRACTION_PROMPT,
    FilmEntityExtractionResult,
    FILM_SHOTLIST_PROMPT,
    FilmShotlistResult,
    ACTOR_IMAGE_GENERATION_PROMPT,
    ActorImageGenerationResult,
    CHARACTER_IMAGE_GENERATION_PROMPT,
    CharacterImageGenerationResult,
)
```

使用提取类 Agent（需先 load_skill，再 extract/aextract）：

```python
from app.chains.agents import FilmEntityExtractor, FilmShotlistStoryboarder
```

使用演员形象/立绘生成 Agent（需先 load_skill，再 generate/agenerate）：

```python
from app.chains.agents import (
    ActorImageGeneratorAgent,
    CharacterImageGeneratorAgent,
    PropImageGeneratorAgent,
    SceneImageGeneratorAgent,
    CostumeImageGeneratorAgent,
    ShotFirstFramePromptAgent,
    ShotLastFramePromptAgent,
    ShotKeyFramePromptAgent,
    ShotFrameImageGeneratorAgent,
)
```
