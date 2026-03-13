# 影视分镜师（Shot List / Storyboard）

## 目标

将小说片段转为可执行的**镜头表（shot list）**：场景划分、每个镜头的景别/机位/镜头运动、转场方式、以及需要的 VFX 类型。严格忠实原文，不编造情节与画面。

## 原则

- **忠实原文**：不新增原文不存在的人物、地点、道具、动作、对白或情节；不确定时使用 `UNKNOWN`/空值或写入 `uncertainties`。
- **可拍性**：镜头描述使用行业口吻，明确画面内容与动作，避免抽象文学化表达。
- **枚举严格**：景别、机位、运镜、转场、VFX 类型仅使用 `schemas` 中定义的枚举值。

## 输入

- `source_id`：小说/章节标识。
- `source_title`：可选，书名/章节名。
- `language`：可选。
- `chunks_json`：JSON 数组，每项含 `chunk_id`、`text`。用于 `EvidenceSpan.chunk_id` 与回查。

## 输出

结构化 JSON，符合 `FilmShotlistResult`，内含 `breakdown: ProjectCinematicBreakdown`（见 `app.core.skills_runtime.schemas`）：

- 元信息：`source_id`, `source_title`, `source_author`, `language`, `chunks[]`
- 实体表：`characters[]`, `locations[]`, `props[]`
- 场景与镜头：`scenes[]`, `shots[]`, `transitions[]`
- 备注与不确定项：`notes[]`, `uncertainties[]`

每个镜头（`Shot`）需包含：景别（ShotType）、机位（CameraAngle）、镜头运动（CameraMovement）、画面描述、对白列表（DialogueLine）、音效/VFX 等；转场（Transition）指定 `from_shot_id`、`to_shot_id`、`transition` 类型。

## 行业术语（枚举）

- **景别 ShotType**：ECU, CU, MCU, MS, MLS, LS, ELS
- **机位 CameraAngle**：EYE_LEVEL, HIGH_ANGLE, LOW_ANGLE, BIRD_EYE, DUTCH, OVER_SHOULDER
- **镜头运动 CameraMovement**：STATIC, PAN, TILT, DOLLY_IN, DOLLY_OUT, TRACK, CRANE, HANDHELD, STEADICAM, ZOOM_IN, ZOOM_OUT
- **转场 TransitionType**：CUT, DISSOLVE, WIPE, FADE_IN, FADE_OUT, MATCH_CUT, J_CUT, L_CUT
- **VFX 类型 VFXType**：NONE, PARTICLES, VOLUMETRIC_FOG, CG_DOUBLE, DIGITAL_ENVIRONMENT, MATTE_PAINTING, FIRE_SMOKE, WATER_SIM, DESTRUCTION, ENERGY_MAGIC, COMPOSITING_CLEANUP, SLOW_MOTION_TIME, OTHER

具体中文映射见 `schemas` 中的 `*_ZH` 字典。

## 拆解原则（简要）

- 先按叙事推进划分 **scenes**（依据：地点/时间/人物组合或明显段落转折）；每场景建议 2–8 个镜头。
- **对白**：原文引号对白拆入 `DialogueLine.text`；旁白/心理独白用 `VOICE_OVER`；画外音 `OFF_SCREEN`；电话音 `PHONE`。
- **转场**：同场景内多为 CUT；时间跳跃/回忆可用 DISSOLVE/FADE；仅在原文支撑时使用 J_CUT/L_CUT。
- **VFX**：仅当原文明确出现超自然/烟火/水效/破碎/慢动作等时填写；否则 `vfx_type=NONE`。
- **时长**：`duration_sec` 可选，仅在原文节奏/动作明确时给出。

## ID 规则

- `scene_id`：`scene_001` 起。
- `shot_id`：`shot_{sceneIndex3}_{order3}`，例如 scene_001 的第 3 镜为 `shot_001_003`。
- `transitions` 的 `from_shot_id` / `to_shot_id` 必须引用已存在的 `shot_id`。

## 实现与调用

- **技能定义**（Prompt + 输出模型）：`app.core.skills_runtime.film_shotlist_storyboarder`
- **Agent 运行**：`app.chains.agents.extra_agents.FilmShotlistStoryboarder`（基类 `SkillAgentBase`）
- **Prompt**：`FILM_SHOTLIST_PROMPT`
- **输出模型**：`FilmShotlistResult`（内含 `ProjectCinematicBreakdown`，用于校验与解析 LLM 输出）
