# 影视信息抽取系统（人物 / 地点 / 道具）

## 目标

从给定小说文本（按 chunk 输入）中抽取**人物**、**地点**、**道具**，并为每条实体提供可追溯的原文证据（`EvidenceSpan`）。

## 原则

- **忠实原文**：只抽取原文明确出现的内容，不得凭常识补全或编造。
- **可追溯**：关键字段尽量附带 `EvidenceSpan`（至少 `first_appearance`；`quote` 不超过 200 字，必须为原文摘录）。
- **不确定即标注**：无法确定时写入 `uncertainties`（`field_path`、`reason`、`evidence`），不要猜测。

## 输入

- `source_id`：小说/章节标识（如 `novel_x_ch05`）。
- `language`：可选，如 `zh` / `en`。
- `chunks_json`：JSON 数组，每项包含 `chunk_id`、`text`（该 chunk 的原文）。`chunk_id` 会用于 `EvidenceSpan.chunk_id` 回查。

## 输出

结构化 JSON，符合 `FilmEntityExtractionResult`（见 `app.core.skills_runtime`）：

- `source_id`, `language`, `chunks[]`
- `characters[]`：`Character`（id/name/aliases/description/costume_note/traits/confidence/first_appearance 等）
- `locations[]`：`Location`（id/name/type/description/confidence/first_appearance 等）
- `props[]`：`Prop`（id/name/category/description/owner_character_id/confidence/first_appearance 等）
- `notes[]`, `uncertainties[]`

实体字段与 `EvidenceSpan` / `Uncertainty` 定义以 **`app.core.skills_runtime.schemas`** 为准。

## ID 规则

- 人物：`char_001` 起，连续不跳号。
- 地点：`loc_001` 起。
- 道具：`prop_001` 起。

## 抽取策略（简要）

- **人物**：优先具名角色；泛称（如「掌柜」「车夫」）仅在原文中可稳定识别时才建实体。
- **地点**：有明确地名/场所名时抽取；仅「屋里」「门外」等且无稳定命名可不抽或记入 uncertainties。
- **道具**：仅剧情关键或原文明确提及的物件；不堆砌日常陈设，除非原文强调。

## 实现与调用

- **技能定义**（Prompt + 输出模型）：`app.core.skills_runtime.film_entity_extractor`
- **Agent 运行**：`app.chains.agents.extra_agents.FilmEntityExtractor`（基类 `SkillAgentBase`）
- **Prompt**：`FILM_ENTITY_EXTRACTION_PROMPT`
- **输出模型**：`FilmEntityExtractionResult`（用于校验与解析 LLM 输出）
