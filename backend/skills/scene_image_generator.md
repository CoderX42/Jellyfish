# 场景图片生成

## 目标

根据场景名称、描述、风格等生成**场景图片**（一张或多张），用于项目/章节下的场景视觉资产，可与 `app.models.studio.Scene`、`SceneImage` 对应存储。

## 原则

- **风格一致**：同一场景多张图需保持画风一致；`visual_style` 需在生成中体现。
- **符合描述**：严格依据 `name`、`description`、`tags` 生成。
- **多角度对应**：若请求多个 `view_angles`，输出与视角对应，便于写入 `SceneImage`。

## 输入

字段与 `app.models.studio.Scene` 对齐：

- `name`（必填）、`description`（必填）、`tags`（可选）、`project_id`、`chapter_id`（可选）
- `visual_style`（可选）、`quality_level`（可选）、`view_angles`（可选）

## 输出

结构化结果 `images: list[SceneImageGenerationItem]`，每项含 `url` 或 `file_id`、可选 `quality_level`、`view_angle`、`is_primary`，便于写入 `SceneImage`。

## 实现与调用

- **技能定义**：`app.core.skills_runtime.scene_image_generator`
- **Agent**：`app.chains.agents.asset_image_agents.SceneImageGeneratorAgent`
