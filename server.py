# server.py
from flask import Flask, render_template, session, request, jsonify, redirect, url_for
from flask_session import Session
import random, string, os, time, threading
from models.door import Door
from models.monster import Monster, get_random_monster
from models.player import Player
from models.status import Status
from models.shop import Shop
from scenes import Scene, DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene, SceneManager
from models.game_config import GameConfig
from models.items import ReviveScroll, FlyingHammer, GiantScroll, Barrier

# -------------------------------
# 1) Flask 应用初始化
# -------------------------------

app = Flask(__name__)
app.secret_key = "SOME_SECRET"  # 用于加密 session
app.config["SESSION_TYPE"] = "filesystem"  # 存储 session 到文件系统
Session(app)

# -------------------------------
# 2) 控制器及辅助类
# -------------------------------


class GameController:
    def __init__(self):
        self.game_config = GameConfig()
        
        # Initialize game state
        self.reset_game()

    def reset_game(self):
        """重置游戏状态"""
        self.current_monster = None
        self.round_count = 0
        self.messages = []
        self.player = Player(self)
        self.player.reset()  # 重置玩家状态
        self.shop = Shop(self.player)
        self.shop.player = self.player
        self.shop.generate_items()
        self.scene_manager = SceneManager()
        self.scene_manager.game_controller = self  # 直接设置 game_controller
        self.scene_manager.initialize_scenes()  # 这会设置当前场景为 DoorScene
        
            
        # 确保当前场景是 DoorScene
        if not isinstance(self.scene_manager.current_scene, DoorScene):
            self.scene_manager.go_to("door_scene")

    def add_message(self, msg):
        """添加消息到消息列表"""
        if isinstance(msg, str):
            self.messages.append(msg)
        elif isinstance(msg, list):
            self.messages.extend(msg)

    def clear_messages(self):
        """清空消息列表"""
        self.messages.clear()

# -------------------------------
# 3) Flask 路由及 Session 存储
# -------------------------------

def get_game():
    if "game_id" not in session:
        session["game_id"] = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    gid = session["game_id"]
    if gid not in games_store:
        games_store[gid] = GameController()  # 这里会调用一次 reset_game
    return games_store[gid]

games_store = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/startOver", methods=["POST"])
def start_over():
    g = get_game()
    g.reset_game()
    return jsonify({"log": "游戏已重置"})

@app.route("/getState")
def get_state():
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
                "status_desc": p.get_status_desc(),
                "inventory": inventory_dict
            },
            "button_texts": scn.get_button_texts() if scn else ["", "", ""]
        }
        
        # 修改消息处理逻辑
        if g.messages:
            state["last_message"] = "\n".join(g.messages)
            # 只有在消息成功发送到前端后才清空
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                g.clear_messages()
        
        return jsonify(state)
    except Exception as e:
        print(f"Error in get_state: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/buttonAction", methods=["POST"])
def button_action():
    g = get_game()
    scn = g.scene_manager.current_scene
    data = request.json
    index = data.get("index", 0)
    
    # 获取当前场景名称
    scn_name = scn.__class__.__name__ if scn else "None"
    
    # 处理按钮选择
    if scn_name in ["DoorScene", "BattleScene", "ShopScene", "UseItemScene", "GameOverScene"]:
        scn.handle_choice(index)
    
    # 获取当前消息并清空
    current_messages = g.messages.copy()
    g.clear_messages()
    
    return jsonify({
        "status": "success",
        "log": "\n".join(current_messages) if current_messages else ""
    })

@app.route("/exitGame", methods=["POST"])
def exit_game():
    g = get_game()
    # 清除游戏会话
    if "game_id" in session:
        game_id = session["game_id"]
        if game_id in games_store:
            del games_store[game_id]
        session.clear()
    
    # 使用定时器在返回响应后关闭服务器
    def shutdown_server():
        time.sleep(2)  # 等待2秒确保响应已发送
        os._exit(0)  # 强制退出进程
    
    # 在新线程中运行关闭操作
    threading.Thread(target=shutdown_server).start()
    
    return jsonify({"log": "游戏已关闭，感谢游玩！"})

# -------------------------------
# 4) 启动 Flask 应用
# -------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)