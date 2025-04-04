# server.py
from flask import Flask, render_template, session, request, jsonify, redirect, url_for
from flask_session import Session
import random, string, os
from models.door import Door
from models.monster import Monster, get_random_monster
from models.player import Player
from models.status_effect import StatusEffect
from models.shop import ShopLogic

# -------------------------------
# 1) Flask 应用初始化
# -------------------------------

app = Flask(__name__)
app.secret_key = "SOME_SECRET"  # 用于加密 session
app.config["SESSION_TYPE"] = "filesystem"  # 存储 session 到文件系统
Session(app)

# -------------------------------
# 2) 核心逻辑：玩家、怪物、场景等
# -------------------------------

class Scene:
    """场景基类"""
    def __init__(self, controller):
        self.controller = controller
        self.button_texts = ["", "", ""]  # 默认三个空按钮

    def on_enter(self):
        """进入场景时的处理"""
        pass

    def handle_choice(self, index):
        """处理按钮选择"""
        pass

    def get_button_texts(self):
        """获取按钮文本"""
        return self.button_texts

class DoorScene(Scene):
    """选择门的场景"""
    def __init__(self, controller):
        super().__init__(controller)
        self.doors = []
        self.has_initialized = False
        # Initialize default button texts
        self.button_texts = ["门1", "门2", "门3"]

    def on_enter(self):
        if not self.has_initialized:
            self._generate_doors()
            self.has_initialized = True

    def handle_choice(self, index):
        c = self.controller
        p = c.player
        if index < 0 or index >= len(self.doors):
            c.add_message("无效的门选择")
            return
            
        c.round_count += 1
        c.add_message(f"第{c.round_count}回合：")
        
        # 如果选择了非怪物门，清除所有战斗状态
        door = self.doors[index]
        if door.event != "monster":
            StatusEffect.clear_battle_statuses(p)
        p.apply_turn_effects(is_battle_turn=False)  # Adventure turn effects
        
        # 进入门并处理事件
        door.enter(p, c)
            
        # 检查玩家生命值
        if p.hp <= 0:
            self.controller.go_to_scene("game_over_scene")
        
        # 如果不是怪物门，重新生成门
        if door.event != "monster":
            self._generate_doors()

    def _generate_doors(self):
        """生成三扇门，确保至少一扇是怪物门"""
        # 获取可用的门类型
        available_doors = ["trap", "reward", "shop"]
        if self.controller.player.gold > 0:
            available_doors.append("shop")
            
        # 生成一扇怪物门
        monster = get_random_monster(current_round=self.controller.round_count)
        monster_door = Door.generate_monster_door(monster)
        
        # 生成其他两扇门
        other_doors = []
        for _ in range(2):
            door_type = random.choice(available_doors)
            if door_type == "trap":
                door = Door.generate_trap_door()
            elif door_type == "reward":
                door = Door.generate_reward_door()
            elif door_type == "shop":
                door = Door.generate_shop_door()
            other_doors.append(door)
            
        # 随机打乱三扇门的顺序
        self.doors = [monster_door] + other_doors
        random.shuffle(self.doors)
        
        # 更新按钮文本
        if self.doors:
            self.button_texts = [
                f"门1 - {self.doors[0].hint}",
                f"门2 - {self.doors[1].hint}",
                f"门3 - {self.doors[2].hint}"
            ]
        else:
            self.button_texts = ["门1", "门2", "门3"]

class BattleScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.monster = None
        self.button_texts = ["攻击", "使用道具", "逃跑"]

    def on_enter(self):
        # 使用 DoorScene 中提前生成的怪物
        self.monster = self.controller.current_monster
        if self.monster:
            monster_desc = f"你遇到了 {self.monster.name} (HP: {self.monster.hp}, ATK: {self.monster.atk}, Tier: {self.monster.tier})"
            if self.monster.has_status("stun"):
                monster_desc += f" [晕眩{self.monster.statuses['stun']['duration']}回合]"
            self.controller.add_message(monster_desc)
        
    def handle_choice(self, index):
        p = self.controller.player
        if p.is_stunned():
            # 先应用战斗状态效果
            p.apply_turn_effects(is_battle_turn=True)
            # 玩家晕眩时，怪物进行攻击
            self.controller.add_message("你处于眩晕状态, 无法行动!")
            self.monster.attack(p)
            return

        if index == 0:
            self.do_attack(p)
        elif index == 1:
            # 检查是否有可用的主动道具
            active_items = [item for item in p.inventory if item.get("active", False)]
            if not active_items:
                self.controller.add_message("你没有可用的道具！")
                return
            # 保存当前战斗场景作为上一个场景
            self.controller.last_scene = self
            # 跳转到道具使用场景
            self.controller.go_to_scene("use_item_scene")
            self.controller.add_message("进入使用道具界面")
        elif index == 2:
            self.do_escape(p)
        else:
            self.controller.add_message("无效操作")

    def do_attack(self, p):
        # 玩家攻击
        monster_dead = p.attack(self.monster)
        
        # 如果怪物未死亡，怪物反击
        if not monster_dead:
            self.monster.attack(p)
        
        # 如果怪物死亡，处理战利品
        if monster_dead:
            # 处理怪物掉落
            self.monster.process_loot(p)
            # 清除所有战斗状态
            StatusEffect.clear_battle_statuses(p)
            # 重新生成门
            self.controller.door_scene._generate_doors()
            # 返回门场景
            self.controller.go_to_scene("door_scene")

    def do_escape(self, p):
        success = p.try_escape(self.monster)
        if success:
            self.controller.go_to_scene("door_scene")

class ShopScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.shop_items = []

    def on_enter(self):
        logic = self.controller.shop_logic
        logic.generate_items(self.controller.player)
        if self.controller.player.gold == 0 or len(logic.shop_items) == 0:
            self.controller.add_message("你没有钱，于是被商人踢了出来。")
            self.controller.door_scene._generate_doors()  # 刷新门
            self.controller.go_to_scene("door_scene")
            self.shop_items = []
            return  # 确保不再继续处理
        self.shop_items = logic.shop_items
        # 更新按钮文本
        if self.shop_items:
            self.button_texts = [
                f"{self.shop_items[0]['name']} ({self.shop_items[0]['cost']}G)",
                f"{self.shop_items[1]['name']} ({self.shop_items[1]['cost']}G)",
                f"{self.shop_items[2]['name']} ({self.shop_items[2]['cost']}G)"
            ]

    def handle_choice(self, index):
        logic = self.controller.shop_logic
        success = logic.purchase_item(index, self.controller.player)
        if success:
            self.controller.door_scene._generate_doors()  # Ensure doors regenerate
            self.controller.go_to_scene("door_scene")
            self.controller.add_message("离开商店, 回到门场景")

class UseItemScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.active_items = []

    def on_enter(self):
        p = self.controller.player
        # 筛选库存中主动使用的道具，排除复活卷轴（active=False）
        self.active_items = [item for item in p.inventory if item.get("active", False)]
        if not self.active_items:
            self.controller.add_message("你没有可用的道具！返回战斗场景。")
            self.controller.go_to_scene("battle_scene")
            return
        # 更新按钮文本
        self.button_texts = [
            self.active_items[0]['name'] if len(self.active_items) > 0 else "无",
            self.active_items[1]['name'] if len(self.active_items) > 1 else "无",
            self.active_items[2]['name'] if len(self.active_items) > 2 else "无"
        ]

    def handle_choice(self, index):
        p = self.controller.player
        if index < 0 or index >= len(self.active_items):
            self.controller.add_message("无效的道具选择")
            return
        item = self.active_items[index]
        if not item:
            self.controller.add_message("你没有选择任何道具")
            return
        t = item["type"]
        if t == "飞锤":
            # 对当前怪物施加晕眩效果
            if self.controller.current_monster:
                self.controller.current_monster.apply_status("stun", 3)
                effect_msg = "飞锤飞出，怪物被晕眩3回合！"
            else:
                effect_msg = "当前没有怪物，飞锤未产生效果。"
        elif t == "结界":
            p.statuses["barrier"] = {"duration": 3}
            effect_msg = "结界形成，接下来3回合你免受怪物伤害！"
        elif t == "巨大卷轴":
            # 设置一个足够大的持续时间，确保在当前战斗中持续有效
            p.statuses["atk_multiplier"] = {"duration": 999, "value": 2}
            effect_msg = "巨大卷轴激活，当前战斗中你的攻击力翻倍！"
        elif t == "heal":
            heal_amt = item["value"]
            p.heal(heal_amt)
            effect_msg = f"治疗药水生效，恢复 {heal_amt} HP！"
        else:
            effect_msg = f"道具 {item['name']} 未定义效果。"
        if item in p.inventory:
            p.inventory.remove(item)
        # 使用完道具后，恢复上一个战斗场景
        self.controller.resume_scene()
        self.controller.add_message(effect_msg)

class GameOverScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.button_texts = ["重启游戏", "使用复活卷轴", "退出游戏"]

    def on_enter(self):
        """进入游戏结束场景时的处理"""
        pass

    def handle_choice(self, index):
        """处理游戏结束状态下的按钮选择"""
        if index == 0:
            self.controller.reset_game()
            self.controller.add_message("游戏已重置")
        elif index == 1:
            result = self.controller.player.try_revive()
            if result:
                self.controller.add_message(f"使用复活卷轴成功, 回到上一个场景: {self.controller.last_scene.__class__.__name__}!")
                self.controller.scene_manager.current_scene = self.controller.last_scene
            else:
                self.controller.add_message("你没有复活卷轴!")
        elif index == 2:
            os._exit(0)
            self.controller.add_message("游戏结束")

# -------------------------------
# 3) 控制器及辅助类
# -------------------------------

class SceneManager:
    def __init__(self):
        self.scenes = {}
        self.current_scene = None

    def add_scene(self, name, scene):
        self.scenes[name] = scene

    def go_to(self, name):
        if name not in self.scenes:
            raise ValueError(f"场景 {name} 未注册!")
        self.current_scene = self.scenes[name]
        if hasattr(self.current_scene, "on_enter"):
            self.current_scene.on_enter()

class GameConfig:
    START_PLAYER_HP = 20
    START_PLAYER_ATK = 5
    START_PLAYER_GOLD = 50

class GameController:
    def __init__(self):
        self.game_config = GameConfig()
        self.scene_manager = SceneManager()
        self.shop_logic = ShopLogic()
        
        # Reset game state first (this creates the player)
        self.reset_game()
        
        # Create scene instances after player is created
        self.door_scene = DoorScene(self)
        self.battle_scene = BattleScene(self)
        self.shop_scene = ShopScene(self)
        self.use_item_scene = UseItemScene(self)
        self.game_over_scene = GameOverScene(self)
        
        # Register scenes
        self.scene_manager.add_scene("door_scene", self.door_scene)
        self.scene_manager.add_scene("battle_scene", self.battle_scene)
        self.scene_manager.add_scene("shop_scene", self.shop_scene)
        self.scene_manager.add_scene("use_item_scene", self.use_item_scene)
        self.scene_manager.add_scene("game_over_scene", self.game_over_scene)
        
        # Initialize the door scene
        self.door_scene._generate_doors()
        self.scene_manager.current_scene = self.door_scene
        self.door_scene.on_enter()

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
        self.last_scene = None
        self.messages = []
        self.current_monster = None
        
        # Reset door scene if it exists
        if hasattr(self, 'door_scene'):
            self.door_scene.has_initialized = False
            self.door_scene._generate_doors()
            self.scene_manager.current_scene = self.door_scene
            self.door_scene.on_enter()

    def add_message(self, msg):
        """添加消息到消息列表"""
        if isinstance(msg, str):
            self.messages.append(msg)
        elif isinstance(msg, list):
            self.messages.extend(msg)

    def clear_messages(self):
        """清空消息列表"""
        self.messages.clear()

    def go_to_scene(self, name):
        if self.scene_manager.current_scene is not None:
            self.last_scene = self.scene_manager.current_scene
        self.scene_manager.go_to(name)

    def resume_scene(self):
        # 如果上一个场景存在且类型为 BattleScene，则恢复它
        if self.last_scene is not None and self.last_scene.__class__.__name__ == "BattleScene":
            self.scene_manager.current_scene = self.last_scene
        # 否则，默认切换到 battle_scene（但一般UseItemScene只在战斗中使用）
        else:
            self.scene_manager.current_scene = self.battle_scene

# -------------------------------
# 4) Flask 路由及 Session 存储
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
# 5) 启动 Flask 应用
# -------------------------------

if __name__ == "__main__":
    app.run(debug=True)