# server.py
from flask import Flask, render_template, session, request, jsonify, redirect, url_for
from flask_session import Session
import random, string, os
from models.door import Door
from models.monster import Monster, get_random_monster
from models.player import Player
from models.status_effect import StatusEffect
from models.shop import ShopLogic
from scenes import Scene, DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene, SceneManager, SCENE_DICT

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

class GameConfig:
    START_PLAYER_HP = 20
    START_PLAYER_ATK = 5
    START_PLAYER_GOLD = 50

class GameController:
    def __init__(self):
        self.game_config = GameConfig()
        self.scene_manager = SceneManager()
        self.shop_logic = ShopLogic()
        self.scene_manager.set_game_controller(self)
        
        # Reset game state first (this creates the player)
        self.reset_game()
        
        # Initialize scenes
        self.scene_manager.initialize_scenes()

    def reset_game(self):
        """Reset game state"""
        # Reset player
        self.player = Player("勇士", self.game_config.START_PLAYER_HP,
                           self.game_config.START_PLAYER_ATK,
                           self.game_config.START_PLAYER_GOLD, self)
        
        # Initialize inventory
        self.player.inventory = [
            {"name": "复活卷轴", "type": "revive", "value": 1, "cost": 0, "active": False},
            {"name": "飞锤", "type": "飞锤", "value": 0, "cost": 0, "active": True},
            {"name": "巨大卷轴", "type": "巨大卷轴", "value": 0, "cost": 0, "active": True},
            {"name": "结界", "type": "结界", "value": 0, "cost": 0, "active": True}
        ]
        
        # Reset game state
        self.round_count = 0
        self.messages = []
        self.current_monster = None

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
        games_store[gid] = GameController()
        games_store[gid].reset_game()  # 初始化游戏，设置初始物品
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
    
    state = {
        "round": g.round_count,
        "player": {
            "hp": p.hp,
            "atk": p.atk,
            "gold": p.gold,
            "status_desc": p.get_status_desc(),
            "inventory": p.inventory
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

# -------------------------------
# 4) 启动 Flask 应用
# -------------------------------

if __name__ == "__main__":
    app.run(debug=True)