# 演员形象/立绘生成

## 目标

根据名称、描述、风格等生成**演员形象/立绘**图片（一张或多张），用于项目/章节下的角色视觉资产，可与 `app.models.studio.ActorImage`、`ActorImageImage` 对应存储。

## 原则

- **风格一致**：同一角色多张图需保持画风、造型一致；`visual_style`（真人/动漫）需在生成中体现。
- **符合描述**：严格依据 `name`、`description`、`tags` 生成，不擅自增删特征。
- **多角度对应**：若请求多个 `view_angles`，输出图片顺序或元数据应与视角对应，便于写入 `ActorImageImage`。

## 输入

字段与 `app.models.studio.ActorImage`、`Character`、`Actor` 对齐，供 API/服务层从库表组装的 dict 传入：

- `name`（必填）：名称，对应 ActorImage.name / Character.name。
- `description`（必填）：描述，对应 ActorImage.description / Character.description。
- `tags`（可选）：标签列表，对应 ActorImage.tags。
- `project_id`（可选）：归属项目 ID。
- `chapter_id`（可选）：归属章节 ID。
- `visual_style`（可选）：画面风格，对应 `ProjectVisualStyle`：`live_action`（真人）/ `anime`（动漫）。
- `quality_level`（可选）：精度等级，对应 `AssetQualityLevel`：`LOW` / `MEDIUM` / `HIGH` / `ULTRA`。
- `view_angles`（可选）：请求的视角列表，对应 `AssetViewAngle`：`FRONT`、`LEFT`、`RIGHT`、`BACK`、`THREE_QUARTER`、`TOP`、`DETAIL`；空或不传时默认生成一张（如正面）。

## 输出

结构化结果，包含 `images` 列表，便于写入 `ActorImage` + `ActorImageImage`：

- `images`：`list[ActorImageGenerationItem]`
  - `url` 或 `file_id`：图片地址或文件 ID。
  - `quality_level`（可选）：与请求或默认一致。
  - `view_angle`（可选）：与请求的视角对应。
  - `is_primary`（可选）：是否主图；应用层保证同一 ActorImage 下至多一张主图。

## 实现与调用

- **技能定义**（Prompt + 输入/输出模型）：`app.core.skills_runtime.actor_image_generator`
- **Agent 运行**：`app.chains.agents.actor_image_agent.ActorImageGeneratorAgent`
- **Prompt**：`ACTOR_IMAGE_GENERATION_PROMPT`（供图像模型使用的文本 prompt）
- **输入模型**：`ActorImageGeneratorInput`
- **输出模型**：`ActorImageGenerationResult`（含 `ActorImageGenerationItem`）
