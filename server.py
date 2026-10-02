# server.py
"""ThreeDoors 服务端：Flask 应用与 API 路由（对局逻辑见 game.py，对局存储见 game_store.py）。"""
from flask import Flask, render_template, session, request, jsonify, g as request_ctx
from flask_session import Session
import os, time, threading, secrets
import sys
from ending_roll import build_ending_roll_lines
from game import GameController, parse_test_gate
from game_store import GameStore, is_valid_game_id

# -------------------------------
# 1) Flask 应用初始化
# -------------------------------

app = Flask(__name__)


def _load_secret_key() -> str:
    """优先读环境变量 SECRET_KEY；否则使用（必要时生成）instance 目录下的本地密钥文件。"""
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key:
        return env_key
    key_path = os.path.join(app.instance_path, "secret_key")
    try:
        with open(key_path, "r", encoding="utf-8") as fh:
            stored = fh.read().strip()
        if stored:
            return stored
    except OSError:
        pass
    new_key = secrets.token_hex(32)
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        with open(key_path, "w", encoding="utf-8") as fh:
            fh.write(new_key)
    except OSError:
        pass
    return new_key


app.secret_key = _load_secret_key()  # 用于加密 session
app.config["SESSION_TYPE"] = "filesystem"  # 存储 session 到文件系统
# 本地开发模式：仅 `python3 server.py` 直接启动（或设置 THREEDOORS_DEV=1）时开启；gunicorn 部署时关闭。
app.config["DEV_MODE"] = os.environ.get("THREEDOORS_DEV", "").strip() == "1"
Session(app)

LOCAL_ADDRS = {"127.0.0.1", "::1"}


def is_local_dev_request() -> bool:
    """是否为本地开发模式下来自本机的请求（只有此时允许关闭服务器进程）。"""
    return bool(app.config.get("DEV_MODE")) and request.remote_addr in LOCAL_ADDRS

# 测试用 gate：启动时通过 --test-gate=<name> 指定，进入/重置游戏后直接进入对应事件门（如木偶最终 Boss 战）
TEST_GATE = parse_test_gate(sys.argv[1:])

# -------------------------------
# 2) 对局存储与 Flask 路由
# -------------------------------

# 对局存储：内存 LRU + instance/games 下的磁盘存档（服务重启后可继续游戏）
games_store = GameStore(
    persist_dir=os.environ.get("THREEDOORS_SAVE_DIR") or os.path.join(app.instance_path, "games"),
    max_in_memory=int(os.environ.get("THREEDOORS_MAX_GAMES_IN_MEMORY", "200")),
)


def get_game():
    """根据 session 获取或创建当前对局对应的 GameController；请求结束后自动存档。"""
    gid = session.get("game_id")
    if not is_valid_game_id(gid):
        gid = secrets.token_urlsafe(12)
        session["game_id"] = gid
    game = games_store.get(gid)
    if game is None:
        game = GameController(test_gate=TEST_GATE)  # 这里会调用一次 reset_game
        games_store[gid] = game
    request_ctx.active_game_id = gid
    return game


@app.after_request
def _save_active_game(response):
    gid = getattr(request_ctx, "active_game_id", None)
    if gid:
        games_store.save(gid)
    return response


@app.route("/")
def index():
    """渲染游戏主页面。"""
    return render_template("index.html", test_gate=TEST_GATE, dev_mode=bool(app.config.get("DEV_MODE")))


@app.route("/startOver", methods=["POST"])
def start_over():
    """重置当前对局并返回确认。"""
    g = get_game()
    g.reset_game()
    return jsonify({"log": "游戏已重置"})


@app.route("/getState")
def get_state():
    """返回当前游戏状态（回合、玩家、按钮、场景、消息等）。仅对 AJAX 请求在返回后清空消息。"""
    g = get_game()
    p = g.player
    scn = g.scene_manager.current_scene
    
    try:
        # 转换inventory为可序列化的格式
        inventory_dict = {}
        for item_type, items in p.inventory.items():
            inventory_dict[item_type.value] = [
                {"name": item.name, "type": item.item_type.value} 
                for item in items
            ]
            
        state = {
            "round": g.round_count,
            "player": {
                "hp": p.hp,
                "atk": p.atk,
                "gold": p.gold,
                "moral": g.story.moral_score,
                "status_desc": p.get_status_desc(),
                "inventory": inventory_dict
            },
            "button_texts": scn.get_button_texts() if scn else ["", "", ""],
            "scene_info": {
                "type": scn.enum.name if scn and scn.enum else "UNKNOWN",
                "monster_name": getattr(scn.monster, "name", "") if hasattr(scn, "monster") and scn.monster else "",
                "monster_sprite_key": getattr(scn.monster, "sprite_key", "monster_default") if hasattr(scn, "monster") and scn.monster else "",
                "choices": scn.get_button_texts() if scn else []
            },
            "event_info": {
                "title": getattr(g.current_event, "title", ""),
                "description": getattr(g.current_event, "description", ""),
                "choices": g.current_event.get_choices() if g.current_event else []
            } if scn and scn.enum.name == 'EVENT' else None
        }
        if scn and scn.enum and scn.enum.name == "DOOR" and hasattr(scn, "doors"):
            state["scene_info"]["doors"] = [
                {
                    "hint": door.hint,
                    "texture_key": getattr(door, "texture_key", "door_oak"),
                }
                for door in scn.doors
            ]
        if scn and scn.enum and scn.enum.name == "ENDING_SUMMARY":
            clear_info = getattr(g, "game_clear_info", None) or {}
            state["ending_summary"] = {
                "title": str(clear_info.get("ending_title", "")).strip(),
                "description": str(clear_info.get("ending_description", "")).strip(),
            }
        if scn and scn.enum and scn.enum.name == "ENDING_ROLL":
            state["ending_roll_lines"] = build_ending_roll_lines(g)
        if scn and scn.enum and scn.enum.name == "GAME_OVER":
            state["game_clear"] = bool(getattr(g, "game_clear_info", None))

        # 修改消息处理逻辑
        if g.messages:
            state["last_message"] = "\n".join(g.messages)
            # 只有在消息成功发送到前端后才清空
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                g.clear_messages()
        
        return jsonify(state)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/buttonAction", methods=["POST"])
def button_action():
    """处理前端按钮点击：解析 index，交给当前场景处理并返回结果与日志。"""
    g = get_game()
    scn = g.scene_manager.current_scene
    if not scn:
        return jsonify({"status": "error", "outcome": None, "log": "当前无场景"}), 400
    data = request.json or {}
    raw_index = data.get("index", 0)
    try:
        index = int(raw_index) if raw_index is not None else 0
    except (TypeError, ValueError):
        index = 0
    index = max(0, min(2, index))

    scn_name = scn.__class__.__name__
    outcome = None
    if scn_name in ["DoorScene", "BattleScene", "ShopScene", "UseItemScene", "EndingSummaryScene", "EndingRollScene", "GameOverScene", "EventScene"]:
        outcome = scn.handle_choice(index)
    
    # 获取当前消息并清空
    current_messages = g.messages.copy()
    g.clear_messages()
    
    return jsonify({
        "status": "success",
        "outcome": outcome,
        "log": "\n".join(current_messages) if current_messages else ""
    })

@app.route("/exitGame", methods=["POST"])
def exit_game():
    """退出当前对局。仅本地开发模式下来自本机的请求会额外关闭服务器进程；线上部署只结束自己的对局。"""
    if "game_id" in session:
        games_store.pop(session["game_id"], None)
    session.clear()

    if not is_local_dev_request():
        return jsonify({"log": "你已退出本局，感谢游玩！", "server_stopped": False})

    def shutdown_server():
        time.sleep(2)  # 等待2秒确保响应已发送
        os._exit(0)  # 强制退出进程

    threading.Thread(target=shutdown_server, daemon=True).start()
    return jsonify({"log": "游戏已关闭，感谢游玩！", "server_stopped": True})

# -------------------------------
# 4) 启动 Flask 应用
# -------------------------------

if __name__ == "__main__":
    app.config["DEV_MODE"] = True
    port = int(os.environ.get("PORT", 5000))
    # 默认只监听本机：debug 模式的 Werkzeug 调试器可执行任意代码，不应暴露到局域网
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "1").strip() != "0"
    app.run(debug=debug, host=host, port=port)
