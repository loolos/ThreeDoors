# server.py
from flask import Flask, render_template, session, request, jsonify, redirect, url_for
from flask_session import Session
import random, string, os, time, threading
from models.door import Door
from models.monster import Monster, get_random_monster
from models.player import Player
from models.status import Status
from models.shop import Shop
from models.story_system import StorySystem
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
        self.current_battle_extensions = []
        self.current_event = None
        self.round_count = 0
        self.messages = []
        self.recent_event_classes = []  # 最近触发的事件类名，用于非后续事件门去重
        self.event_trigger_counts = {}  # 事件触发计数，用于权重衰减与单次事件控制
        self.player = Player(self)
        self.player.reset()  # 重置玩家状态
        self.story = StorySystem(self)
        self.current_shop = Shop(self.player)
        self.scene_manager = SceneManager()
        self.scene_manager.game_controller = self  # 直接设置 game_controller
        self.scene_manager.initialize_scenes()  # 这会设置当前场景为 DoorScene
        self.unlocked_monster_tier = GameConfig.START_UNLOCKED_MONSTER_TIER
        self.player_peak_hp = self.player.hp
        self.player_peak_atk = self.player.atk

    def add_message(self, msg):
        """添加消息到消息列表"""
        if isinstance(msg, str):
            self.messages.append(msg)
        elif isinstance(msg, list):
            self.messages.extend(msg)

    def clear_messages(self):
        """清空消息列表"""
        self.messages.clear()

    def clear_battle_extensions(self):
        """清空当前战斗扩展。"""
        self.current_battle_extensions = []

    def apply_battle_extensions(self, trigger, attacker, defender, damage):
        """仅对当前怪物门声明的扩展执行战斗修正。"""
        extensions = getattr(self, "current_battle_extensions", []) or []
        if not extensions:
            return damage
        story = getattr(self, "story", None)
        if story is None or not hasattr(story, "apply_battle_extension"):
            return damage
        adjusted = damage
        for ext in extensions:
            adjusted = story.apply_battle_extension(
                extension=ext,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=adjusted,
            )
        return adjusted

    def on_player_attack_resolved(self, target):
        """玩家攻击后执行扩展后处理（例如阶段切换）。"""
        extensions = getattr(self, "current_battle_extensions", []) or []
        if not extensions:
            return
        story = getattr(self, "story", None)
        if story is None or not hasattr(story, "handle_battle_extension_post_player_attack"):
            return
        for ext in extensions:
            story.handle_battle_extension_post_player_attack(extension=ext, target=target)

    def update_player_power_peaks(self):
        """记录玩家历史最高生命与攻击，用于 tier 解锁判定。"""
        self.player_peak_hp = max(self.player_peak_hp, self.player.hp)
        self.player_peak_atk = max(self.player_peak_atk, self.player.atk)

    def check_and_unlock_monster_tier(self):
        """每隔固定回合检查怪物 tier 解锁进度，并输出日志。"""
        if self.round_count <= 0:
            return
        if self.round_count % GameConfig.MONSTER_TIER_CHECK_INTERVAL != 0:
            return

        self.update_player_power_peaks()
        # 有效战力 = min(攻击, 生命/2)，用于 tier 解锁判定
        effective_power = min(self.player_peak_atk, self.player_peak_hp // 2)
        old_tier = self.unlocked_monster_tier
        max_tier = GameConfig.MONSTER_MAX_TIER
        new_tier = old_tier

        for tier in range(old_tier + 1, max_tier + 1):
            requirement = GameConfig.MONSTER_TIER_UNLOCK_REQUIREMENTS.get(tier)
            if requirement is None:
                continue
            if effective_power >= requirement:
                new_tier = tier
            else:
                break

        tier_unlock_messages = {
            2: "【威胁升级】阴影里多了细碎脚步声——潜伏者开始在门后徘徊。",
            3: "【威胁升级】你听见铁甲彼此摩擦的回响，重装猎手也加入了追逐。",
            4: "【威胁升级】空气里浮起血与硫磺的味道，凶暴巨兽已被惊醒。",
            5: "【威胁升级】远处传来低沉吟唱，古老而狡诈的强敌正在靠近。",
            6: "【威胁升级】整座迷宫都在震颤，传说中的掠食者已锁定你的气息。",
        }

        tier_warning_messages = {
            2: "【威胁侦测】墙上的抓痕越来越新，像是有猎手在试探你的脚步。",
            3: "【威胁侦测】风里夹着金属味，前方似乎有披甲敌人在巡猎。",
            4: "【威胁侦测】地面偶尔传来闷响，更沉重的脚步正在向你逼近。",
            5: "【威胁侦测】你听见断续低语，某些危险存在已经开始注意你。",
            6: "【威胁侦测】连火把都在发颤，最顶层的威胁正从黑暗深处苏醒。",
        }

        if new_tier > old_tier:
            self.unlocked_monster_tier = new_tier
            for tier in range(old_tier + 1, new_tier + 1):
                self.add_message(
                    tier_unlock_messages.get(
                        tier,
                        f"【威胁升级】更凶险的敌人现身了（已解锁 Tier {tier}）。",
                    )
                )
            return

        if old_tier >= max_tier:
            self.add_message("【威胁侦测】你已触及最高威胁层级，前方皆是传说级敌手。")
            return

        next_tier = old_tier + 1
        self.add_message(
            tier_warning_messages.get(
                next_tier,
                "【威胁侦测】黑暗中的敌意仍在增长，你能感觉到下一波威胁快到了。",
            )
        )

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
    data = request.json or {}
    raw_index = data.get("index", 0)
    try:
        index = int(raw_index) if raw_index is not None else 0
    except (TypeError, ValueError):
        index = 0
    index = max(0, min(2, index))
    
    # 获取当前场景名称
    scn_name = scn.__class__.__name__ if scn else "None"
    
    # 处理按钮选择
    outcome = None
    if scn_name in ["DoorScene", "BattleScene", "ShopScene", "UseItemScene", "GameOverScene", "EventScene"]:
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