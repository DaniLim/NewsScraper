# Spain News API

A **free, Spain‑focused News API prototype**. It ingests RSS feeds from Spanish newspapers & blogs, stores them in SQLite with full‑text search (FTS5), and exposes a simple `/search` endpoint via FastAPI. 100 % open‑source and deployable to a \$0 Fly.io or Render instance.

> **Status:** MVP in development — see the [project roadmap](docs/PLAN.md) for milestones.

---

## Features (MVP)

* 🔄  Automatic RSS ingestion (GitHub Actions every 30 min)
* 🏷️  Duplicate detection (URL hash)
* 🗄️  Lightweight storage (SQLite + WAL)
* 🔍  Full‑text search with relevance + recency boost
* 🌐  JSON API: `/search?q=…&since=YYYY‑MM‑DD`

---

## Quick Start

### Windows 10/11 (PowerShell)

```powershell
# clone
git clone https://github.com/DaniLim/NewsScraper
cd NewsScraper

# create & activate virtual‑env (Python 3.11)
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# install deps
pip install -r requirements.txt

# run local ingest (fetches a few feeds)
python ingest.py --max-per-feed 10

# launch API on http://127.0.0.1:8000
uvicorn api:app --reload
```

### Linux / macOS (bash)

```bash
git clone https://github.com/DaniLim/NewsScraper
cd NewsScraper
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python ingest.py --max-per-feed 10
uvicorn api:app --reload
```

---

## Roadmap

The full milestone breakdown lives in [PLAN.md](docs/PLAN.md). Highlights:

| Stage | Focus                                        |
| ----- | -------------------------------------------- |
| 1     | Repo & environment bootstrap                 |
| 2     | Curate ≥ 40 Spanish RSS feeds (`feeds.yaml`) |
| 3     | Async ingestion module (`ingest.py`)         |
| 4     | SQLite schema & FTS5                         |
| 5     | Scheduled ingestion via GitHub Actions       |
| 6     | FastAPI `/search` endpoint                   |
| 7     | Docker + Fly/Render deploy                   |
| 8     | User validation & backlog                    |

---

## Contributing

Pull requests are welcome! Please:

1. Open an issue describing the change.
2. Run `pre-commit run --all-files` (coming soon).
3. Ensure CI is green.

For larger features (e.g. HTML scraping, semantic search), see \`\`\*\* → “Backlog”.\*\*

---

## License

[MIT](LICENSE) © 2025 DaniLim
