ALTER TABLE runs ADD COLUMN recipe_id TEXT;
ALTER TABLE runs ADD COLUMN recipe_version TEXT;
ALTER TABLE runs ADD COLUMN parameters_json TEXT;
ALTER TABLE runs ADD COLUMN isolation_kind TEXT;
