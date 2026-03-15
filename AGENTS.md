# AGENTS.md

## Cursor Cloud specific instructions

**Product**: ThreeDoors — a text-based roguelike adventure web game (Flask + vanilla JS). Single-service, no external databases or Docker required.

**Dev server**: `python3 server.py` starts Flask on `http://127.0.0.1:5000` (debug mode). The `/exitGame` endpoint calls `os._exit(0)` — avoid clicking the in-game "关闭游戏" button during development or the server will terminate.

**Tests**: `python3 -m unittest discover test` — runs ~80 unit tests covering models, scenes, events, API endpoints, and fuzz testing. No pytest or additional test dependencies needed.

**Lint**: No linter is configured in the repository. Use standard Python linting tools (e.g., `ruff`, `flake8`) if needed.

**Session storage**: Flask-Session uses the filesystem (`flask_session/` directory, auto-created). This directory is gitignored.

**PATH note**: pip installs to `~/.local/bin` which may not be on PATH. Use `export PATH="$HOME/.local/bin:$PATH"` if `flask` or `gunicorn` CLI commands are not found.

**Test gates**: To test specific story gates (e.g. puppet final boss) without playing through the run, start the server with a test flag. On game start or "start over", the game will jump directly to that gate with the correct state and extensions. Example: `python3 server.py --test-gate=puppet_final_boss` or `python3 server.py --test-puppet-final-boss`. Supported values: `puppet_final_boss` (木偶最终 Boss 战，含双阶段与扩展).
