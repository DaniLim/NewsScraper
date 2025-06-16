PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE VIRTUAL TABLE IF NOT EXISTS articles USING fts5(
  title,
  summary,
  url        UNINDEXED,
  source     UNINDEXED,
  published_iso UNINDEXED
);

CREATE TABLE IF NOT EXISTS article_hashes (
  url_hash TEXT PRIMARY KEY
);
