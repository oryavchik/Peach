CREATE TABLE IF NOT EXISTS meetings (
  id TEXT PRIMARY KEY,
  owner TEXT NOT NULL,
  title TEXT NOT NULL,
  agenda TEXT,
  ai_suggestion TEXT,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS meetings_owner ON meetings(owner, updated_at);
CREATE TABLE IF NOT EXISTS quotas (
  bucket TEXT PRIMARY KEY,
  count INTEGER NOT NULL
);
