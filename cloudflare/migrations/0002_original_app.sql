ALTER TABLE meetings ADD COLUMN starts_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00.000Z';
ALTER TABLE meetings ADD COLUMN duration_minutes INTEGER NOT NULL DEFAULT 30;
ALTER TABLE meetings ADD COLUMN participant_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE meetings ADD COLUMN created_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00.000Z';
UPDATE meetings SET
  starts_at=COALESCE(json_extract(agenda,'$.starts_at'),updated_at),
  duration_minutes=COALESCE(json_extract(agenda,'$.duration_minutes'),30),
  created_at=updated_at;
CREATE INDEX IF NOT EXISTS meetings_owner_start ON meetings(owner, starts_at);
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
  description TEXT, status TEXT NOT NULL CHECK(status IN ('todo','in_progress','done')),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS items_owner ON items(owner, created_at);
