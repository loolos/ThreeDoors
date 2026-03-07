# AGENTS.md

## Cursor Cloud specific instructions

**Product**: ThreeDoors — a text-based roguelike adventure web game (Flask + vanilla JS). Single-service, no external databases or Docker required.

**Dev server**: `python3 server.py` starts Flask on `http://127.0.0.1:5000` (debug mode). The `/exitGame` endpoint calls `os._exit(0)` — avoid clicking the in-game "关闭游戏" button during development or the server will terminate.

**Tests**: `python3 -m unittest discover test` — runs 51 unit tests covering models, scenes, API endpoints, and fuzz testing. No pytest or additional test dependencies needed.

**Lint**: No linter is configured in the repository. Use standard Python linting tools (e.g., `ruff`, `flake8`) if needed.

**Session storage**: Flask-Session uses the filesystem (`flask_session/` directory, auto-created). This directory is gitignored.

**PATH note**: pip installs to `~/.local/bin` which may not be on PATH. Use `export PATH="$HOME/.local/bin:$PATH"` if `flask` or `gunicorn` CLI commands are not found.
