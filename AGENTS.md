# AGENTS.md

## Cursor Cloud specific instructions

**Product**: ThreeDoors — a text-based roguelike adventure web game (Flask + vanilla JS). Single-service, no external databases or Docker required.

**Story effects**: each `PendingConsequence.effect_key` is handled by `handle_<effect_key>(story, consequence, door)` in `models/story_effects/` (rewards / shop / hunters / story_doors / bosses), auto-registered in `models/story_effects/__init__.py::EFFECT_HANDLERS`; `StorySystem._apply_effect` only dispatches. Door/battle extension runtime (puppet two-phase boss, elf-rival counters, marked rewards) lives in `models/story_extensions.py` (`StoryExtensionsMixin`, mixed into `StorySystem`).

**Story state**: all long-chain state (`elf_relation`, `elf_key_obtained`, `puppet_evil_value`, `puppet_final_outcome`, …) is declared once in `StorySystem.__init__`; read/write it directly (no `getattr(story, "x", default)`). `puppet_evil_value` is `None` until the puppet chain writes it — read it via `story.get_puppet_evil_value()`.

**Story flags**: `models/story_flags.py` centralizes `choice_flags` / `story_tags` string constants and cross-references `docs/storyline.md` §9; use it when adding or grepping narrative state keys (distinct from `models/story_gates.py` gate/consequence config).

**Dev server**: `python3 server.py` starts Flask on `http://127.0.0.1:5000` (debug mode, local dev mode; set `HOST=0.0.0.0` to expose on LAN, `FLASK_DEBUG=0` to disable the debugger). In local dev mode the `/exitGame` endpoint calls `os._exit(0)` for requests from 127.0.0.1 — avoid clicking the in-game "关闭游戏" button during development or the server will terminate. Under gunicorn (production) `/exitGame` only ends the caller's own game. Session secret comes from `SECRET_KEY` env, else `instance/secret_key` (auto-generated, gitignored).

**Tests**: `python3 -m unittest discover test` — runs ~80+ unit tests covering models, scenes, events package (`models/events/`), API endpoints, and fuzz testing. No pytest or additional test dependencies needed.

**Lint**: No linter is configured in the repository. Use standard Python linting tools (e.g., `ruff`, `flake8`) if needed.

**Code layout**: `server.py` is only the Flask app + routes; the per-game controller lives in `game.py` (`GameController`, `parse_test_gate`); `game_store.py` holds games (in-memory LRU + pickled saves).

**Session storage**: Flask-Session uses the filesystem (`flask_session/` directory, auto-created) and only stores the `game_id`. Game state is pickled to `instance/games/<game_id>.pkl` after every request (override with `THREEDOORS_SAVE_DIR`; memory cache size `THREEDOORS_MAX_GAMES_IN_MEMORY`, default 200), so a restart does not lose progress. Keep game objects picklable (no lambdas/closures stored on events — use `functools.partial`). Both directories are gitignored.

**PATH note**: pip installs to `~/.local/bin` which may not be on PATH. Use `export PATH="$HOME/.local/bin:$PATH"` if `flask` or `gunicorn` CLI commands are not found.

**Test gates**: To test specific story gates without playing through the run, start the server with a test flag. On game start or "start over", the game will jump to that gate with the correct state. Example: `python3 server.py --test-gate=puppet_final_boss` or `python3 server.py --test-puppet-final-boss`. Supported values: `puppet_final_boss` (木偶最终 Boss 战，含双阶段与扩展); `stage_curtain_order` (补全谢幕：回合 184，HP 800/ATK 200，飞贼钥匙+木偶已击败+低邪恶值); `stage_curtain_power` / `--test-stage-curtain-power` (接管谢幕：回合 190，飞贼敌对无钥匙、**关系 -5 可触发飞贼清算战**，木偶已击败+高邪恶值；200 回合木偶回声门).
