-- 2026-04-03
-- 为分镜提取确认流程新增中间状态结构：
-- 1. shots.skip_extraction
-- 2. shots.last_extracted_at
-- 3. shot_extracted_candidates 表

BEGIN;

SET @skip_extraction_exists = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shots'
    AND COLUMN_NAME = 'skip_extraction'
);
SET @sql = IF(
  @skip_extraction_exists = 0,
  'ALTER TABLE shots ADD COLUMN skip_extraction BOOLEAN NOT NULL DEFAULT 0',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @last_extracted_at_exists = (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shots'
    AND COLUMN_NAME = 'last_extracted_at'
);
SET @sql = IF(
  @last_extracted_at_exists = 0,
  'ALTER TABLE shots ADD COLUMN last_extracted_at DATETIME NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS shot_extracted_candidates (
  id INTEGER PRIMARY KEY AUTO_INCREMENT,
  shot_id VARCHAR(64) NOT NULL,
  candidate_type VARCHAR(32) NOT NULL,
  candidate_name VARCHAR(255) NOT NULL,
  candidate_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  linked_entity_id VARCHAR(64) NULL,
  source VARCHAR(32) NOT NULL DEFAULT 'extraction',
  payload JSON NULL,
  confirmed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_shot_extracted_candidates_shot
    FOREIGN KEY (shot_id) REFERENCES shots(id) ON DELETE CASCADE,
  CONSTRAINT uq_shot_extracted_candidates_shot_type_name
    UNIQUE (shot_id, candidate_type, candidate_name),
  CONSTRAINT ck_shot_extracted_candidates_type
    CHECK (candidate_type IN ('character', 'scene', 'prop', 'costume')),
  CONSTRAINT ck_shot_extracted_candidates_status
    CHECK (candidate_status IN ('pending', 'linked', 'ignored'))
);

SET @shot_id_index_exists = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shot_extracted_candidates'
    AND INDEX_NAME = 'ix_shot_extracted_candidates_shot_id'
);
SET @sql = IF(
  @shot_id_index_exists = 0,
  'CREATE INDEX ix_shot_extracted_candidates_shot_id ON shot_extracted_candidates (shot_id)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @status_index_exists = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shot_extracted_candidates'
    AND INDEX_NAME = 'ix_shot_extracted_candidates_status'
);
SET @sql = IF(
  @status_index_exists = 0,
  'CREATE INDEX ix_shot_extracted_candidates_status ON shot_extracted_candidates (candidate_status)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @type_index_exists = (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shot_extracted_candidates'
    AND INDEX_NAME = 'ix_shot_extracted_candidates_type'
);
SET @sql = IF(
  @type_index_exists = 0,
  'CREATE INDEX ix_shot_extracted_candidates_type ON shot_extracted_candidates (candidate_type)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

COMMIT;
