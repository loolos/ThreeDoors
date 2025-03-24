# server.py
from flask import Flask, render_template, session, request, jsonify
from flask_session import Session
import random, string, os

app = Flask(__name__)
app.secret_key = "SOME_SECRET"  # 用于加密 session
app.config["SESSION_TYPE"] = "filesystem"  # 存储 session 到文件系统
Session(app)

# -------------------------------
# 1) 核心逻辑：玩家、怪物、各场景、控制器等
# -------------------------------

class Player:
    def __init__(self, name="勇士", hp=20, atk=5, gold=0):
        self.name = name
        self.base_hp = hp
        self.hp = hp
        self.base_atk = atk
        self.atk = atk
        self.gold = gold
        self.revive_scroll_count = 0
        self.statuses = {}  # 例如 {"poison":3, "weak":2, "atk_up":4, "immune":5, "stun":1, ...}

    def take_damage(self, dmg):
        self.hp -= dmg

    def heal(self, amt):
        self.hp += amt

    def add_gold(self, amt):
        self.gold += amt

    def try_revive(self):
        if self.hp <= 0 and self.revive_scroll_count > 0:
            self.revive_scroll_count -= 1
            self.hp = self.base_hp
            return True
        return False

    def apply_turn_effects(self):
        immune = ("immune" in self.statuses and self.statuses["immune"] > 0)
        if "poison" in self.statuses and self.statuses["poison"] > 0 and not immune:
            self.hp -= 1
        self.atk = self.base_atk
        if "weak" in self.statuses and self.statuses["weak"] > 0 and not immune:
            self.atk = max(1, self.atk - 2)
        if "atk_up" in self.statuses and self.statuses["atk_up"] > 0:
            self.atk += 2
        expired = []
        for st in self.statuses:
            self.statuses[st] -= 1
            if self.statuses[st] <= 0:
                expired.append(st)
        for r in expired:
            del self.statuses[r]

    def get_status_desc(self):
        if not self.statuses:
            return "无"
        desc = []
        for k, v in self.statuses.items():
            if k == "poison":
                desc.append(f"中毒({v}回合)")
            elif k == "weak":
                desc.append(f"虚弱({v}回合)")
            elif k == "atk_up":
                desc.append(f"攻击力+2({v}回合)")
            elif k == "immune":
                desc.append(f"免疫({v}回合)")
            elif k == "stun":
                desc.append(f"眩晕({v}回合)")
            elif k == "dodge":
                desc.append(f"闪避({v}回合)")
            elif k == "damage_reduction":
                desc.append(f"伤害减免({v}回合)")
            elif k == "trap_resist":
                desc.append(f"陷阱减伤({v}回合)")
            else:
                desc.append(f"{k}({v}回合)")
        return ", ".join(desc)

class Monster:
    def __init__(self, name, hp, atk, tier=1):
        self.name = name
        self.hp = hp
        self.atk = atk
        self.tier = tier

    def take_damage(self, dmg):
        self.hp -= dmg

# 修改后的 get_random_monster：如果传入 max_tier，则只返回符合条件的怪物
def get_random_monster(max_tier=None):
    monster_pool = [
        Monster("史莱姆", 15, 4, 1),
        Monster("哥布林", 20, 5, 1),
        Monster("狼", 18, 6, 1),
        Monster("小恶魔", 25, 7, 2),
        Monster("牛头人", 35, 9, 2),
        Monster("巨龙", 40, 10, 3),
        Monster("暗黑骑士", 50, 12, 3),
        Monster("末日领主", 70, 15, 4),
    ]
    if max_tier is not None:
        filtered = [m for m in monster_pool if m.tier <= max_tier]
        if filtered:
            monster_pool = filtered
    return random.choice(monster_pool)

# DoorScene：三扇门场景
class DoorScene:
    def __init__(self, controller):
        self.controller = controller
        self.door_events = []
        self.has_initialized = False
        self.combo_hints = {
            ("monster", "treasure"): ["有些骚动也许是野兽，也许是财宝", "血腥气中又闪着金光"],
            ("monster", "equip"): ["危机中或许暗藏利器", "低沉咆哮与金属碰撞声交织"],
            ("monster", "shop"): ["猛兽怒吼夹杂着商贩吆喝", "似有咆哮也有人在此做买卖"],
            ("monster", "trap"): ["血腥气与阴森诡异混合", "猛兽或陷阱？都危险重重"],
            ("trap", "treasure"): ["危险气息中似乎闪现宝物光芒", "既像埋伏又像财宝，难料"],
            ("trap", "equip"): ["陷阱暗示与金属声交织", "武器或机关，需要谨慎"],
            ("trap", "shop"): ["也许是陷阱伪装也许是商店", "商贩在此亦有危机气息"],
            ("shop", "treasure"): ["有金光也有吆喝声，或宝藏或商店", "闻到钱币味，也许能大赚一笔"],
            ("shop", "equip"): ["有人吆喝好物便宜卖，也许能捡武器", "商店与装备，也许能武装自己"],
        }

    def on_enter(self):
        if not self.has_initialized:
            self._generate_doors()
            self.has_initialized = True

    def handle_choice(self, index):
        c = self.controller
        p = c.player
        if index < 0 or index >= len(self.door_events):
            return "无效的门选择"
        c.round_count += 1
        ev, hint = self.door_events[index]
        p.apply_turn_effects()
        if ev == "monster":
            c.go_to_scene("battle_scene")
            return f"第{c.round_count}回合：你选择了怪物之门，进入战斗场景!"
        elif ev == "shop":
            c.go_to_scene("shop_scene")
            return f"第{c.round_count}回合：你发现了商店，进去逛逛吧!"
        elif ev == "trap":
            dmg = random.randint(5, 10)
            if "trap_resist" in p.statuses:
                dmg = max(1, int(dmg * 0.5))
            p.take_damage(dmg)
            if p.hp <= 0:
                revived = p.try_revive()
                if revived:
                    msg = f"你踩了陷阱({dmg}伤害)，但复活卷轴救了你(HP={p.hp})!"
                else:
                    msg = f"你踩到陷阱({dmg}伤害)，不幸身亡..."
                self._generate_doors()
                return f"第{c.round_count}回合：{msg}"
            else:
                msg = f"你踩到陷阱，损失{dmg}HP!"
                self._generate_doors()
                return f"第{c.round_count}回合：{msg}"
        elif ev == "treasure":
            g = random.randint(5, 15)
            p.add_gold(g)
            msg = f"你发现宝藏，获得{g}金币!"
            self._generate_doors()
            return f"第{c.round_count}回合：{msg}"
        elif ev == "equip":
            boost = random.randint(1, 3)
            oldatk = p.atk
            p.atk += boost
            p.base_atk += boost
            msg = f"你捡到武器，攻击力从{oldatk}提升到{p.atk}!"
            self._generate_doors()
            return f"第{c.round_count}回合：{msg}"
        else:
            return f"第{c.round_count}回合：未知的门事件"

    def _generate_doors(self):
        config = self.controller.game_config
        combo_list = config.DOOR_COMBOS
        monster_combos = [x for x in combo_list if "monster" in x]
        forced_combo = random.choice(monster_combos)
        comboA = random.choice(combo_list)
        comboB = random.choice(combo_list)
        arr = [forced_combo, comboA, comboB]
        random.shuffle(arr)
        result = []
        for combo in arr:
            ev = random.choice(combo)
            hint_candidates = self.combo_hints.get(combo, ["神秘而未知"])
            hint = random.choice(hint_candidates)
            result.append((ev, hint))
        self.door_events = result

class BattleScene:
    def __init__(self, controller):
        self.controller = controller
        self.monster = None
        self.defending = False

    def on_enter(self):
        # 前20回合只允许生成 tier<=2 的怪物
        if self.controller.round_count < 20:
            self.monster = get_random_monster(max_tier=2)
        else:
            self.monster = get_random_monster()
        self.defending = False
        # 记录遇到的怪物信息，用于日志显示
        self.controller.last_monster_message = f"你遇到了 {self.monster.name} (HP: {self.monster.hp}, ATK: {self.monster.atk}, Tier: {self.monster.tier})"

    def handle_action(self, action):
        p = self.controller.player
        if "stun" in p.statuses and p.statuses["stun"] > 0:
            return "你处于眩晕状态, 无法行动!"
        if action == "attack":
            return self.do_attack(p)
        elif action == "defend":
            return self.do_defend(p)
        elif action == "escape":
            return self.do_escape(p)
        else:
            return "未知战斗指令"

    def do_attack(self, p):
        p.apply_turn_effects()
        dmg = max(1, p.atk - random.randint(0, 1))
        self.monster.hp -= dmg
        msg = [f"你攻击 {self.monster.name} 造成 {dmg} 点伤害."]
        if self.monster.hp <= 0:
            msg.append(f"你击败了 {self.monster.name}!")
            loot = self.controller.monster_loot(self.monster)
            msg.append(loot)
            self.controller.go_to_scene("door_scene")
            return "\n".join(msg)
        mdmg = max(1, self.monster.atk - random.randint(0, 1))
        if self.defending:
            mdmg = mdmg // 2
        if "damage_reduction" in p.statuses:
            mdmg = int(mdmg * 0.7)
        p.take_damage(mdmg)
        msg.append(f"{self.monster.name} 反击造成 {mdmg} 点伤害.")
        if p.hp <= 0:
            revived = p.try_revive()
            if revived:
                msg.append("复活卷轴救了你(HP=1)!")
            else:
                msg.append("你被怪物击倒, 英勇牺牲!")
        p.apply_turn_effects()
        # 为较强怪物增加附带效果
        if self.monster.tier >= 3 and random.random() < 0.3:
            effect = random.choice(["weak", "poison", "stun"])
            duration = random.randint(1, 2)
            p.statuses[effect] = duration
            msg.append(f"{self.monster.name} 附带 {effect} 效果 ({duration}回合)!")
        self.defending = False
        return "\n".join(msg)

    def do_defend(self, p):
        p.apply_turn_effects()
        self.defending = True
        msg = ["你选择防御, 本回合怪物攻击减半!"]
        mdmg = max(1, self.monster.atk - random.randint(0, 1)) // 2
        p.take_damage(mdmg)
        msg.append(f"{self.monster.name} 反击造成 {mdmg} 点伤害.")
        if p.hp <= 0:
            revived = p.try_revive()
            if revived:
                msg.append("复活卷轴救了你!")
            else:
                msg.append("你被怪物击倒, 英勇牺牲!")
        p.apply_turn_effects()
        self.defending = False
        return "\n".join(msg)

    def do_escape(self, p):
        fail_chance = min(1.0, self.monster.tier * 0.2)
        if random.random() < fail_chance:
            mdmg = max(1, self.monster.atk - random.randint(0, 1))
            if self.defending:
                mdmg = mdmg // 2
            p.take_damage(mdmg)
            msg = [f"你试图逃跑, 但失败了！{self.monster.name} 反击造成 {mdmg} 点伤害."]
            if p.hp <= 0:
                revived = p.try_revive()
                if revived:
                    msg.append("复活卷轴救了你(HP=1)!")
                else:
                    msg.append("你被怪物击倒, 英勇牺牲!")
            return "\n".join(msg)
        else:
            msg = "你成功逃跑, 回到门场景!"
            self.controller.go_to_scene("door_scene")
            return msg

class ShopScene:
    def __init__(self, controller):
        self.controller = controller
        self.shop_items = []

    def on_enter(self):
        logic = self.controller.shop_logic
        logic.generate_items(self.controller.player)
        if self.controller.player.gold == 0 or len(logic.shop_items) == 0:
            self.controller.last_shop_message = "你没有钱，于是被商人踢了出来"
            self.controller.door_scene._generate_doors()  # 刷新门
            self.controller.go_to_scene("door_scene")
            self.shop_items = []
        else:
            self.shop_items = logic.shop_items

    def handle_purchase(self, idx):
        logic = self.controller.shop_logic
        msg = logic.purchase_item(idx, self.controller.player)
        self.controller.go_to_scene("door_scene")
        return msg + "\n离开商店, 回到门场景"

# ShopLogic：增加多种新物品
class ShopLogic:
    def __init__(self):
        self.shop_items = []

    def generate_items(self, player):
        self.shop_items = []
        if player.gold == 0:
            return
        has_neg = False
        if "poison" in player.statuses and player.statuses["poison"] > 0:
            has_neg = True
        if "weak" in player.statuses and player.statuses["weak"] > 0:
            has_neg = True
        possible = [
            ("普通治疗药水", "heal", 5, 10),
            ("高级治疗药水", "heal", 10, 20),
            ("超高级治疗药水", "heal", 15, 30),
            ("普通装备", "weapon", 2, 15),
            ("稀有装备", "weapon", 5, 30),
            ("复活卷轴", "revive", 1, 25),
            ("闪避卷轴", "dodge", 2, 15),
            ("减伤卷轴", "damage_reduction", 2, 15),
            ("陷阱减伤药剂", "trap_resist", 2, 10),
            ("解毒药水", "cure_poison", 0, 10),
            ("解除虚弱卷轴", "cure_weak", 0, 10),
            ("攻击力增益卷轴", "atk_up", 5, 20),
            ("免疫卷轴", "immune", 5, 25),
        ]
        if player.gold < 10:
            possible = [item for item in possible if item[3] <= 10 or item[1] in ("atk_up", "immune", "dodge", "damage_reduction", "trap_resist")]
        gold = player.gold
        for _ in range(3):
            name, itype, val, basep = random.choice(possible)
            cost = random.randint(int(basep * 0.8), int(basep * 1.2))
            if gold <= 0:
                cost = 0
            else:
                cost = min(cost, gold)
            self.shop_items.append({
                "name": name,
                "type": itype,
                "value": val,
                "cost": cost
            })

    def purchase_item(self, idx, player):
        if idx < 0 or idx >= len(self.shop_items):
            return "无效的购买选项!"
        item = self.shop_items[idx]
        if player.gold < item["cost"]:
            return "你的金币不足, 无法购买!"
        player.gold -= item["cost"]
        n, t, v, c = item["name"], item["type"], item["value"], item["cost"]
        if t == "heal":
            player.heal(v)
            return f"你花费 {c} 金币, 购买了 {n}, 恢复 {v} HP!"
        elif t == "weapon":
            oldatk = player.atk
            player.atk += v
            player.base_atk += v
            return f"你花费 {c} 金币, 购买了 {n}, 攻击力从 {oldatk} 升到 {player.atk}!"
        elif t == "revive":
            player.revive_scroll_count += 1
            return f"你花费 {c} 金币, 购买了 {n}, 复活卷轴 +1, 现有 {player.revive_scroll_count} 张!"
        elif t == "cure_poison":
            if "poison" in player.statuses:
                player.statuses["poison"] = 0
            return f"你花费 {c} 金币, 购买了 {n}, 解除了中毒!"
        elif t == "cure_weak":
            if "weak" in player.statuses:
                player.statuses["weak"] = 0
            return f"你花费 {c} 金币, 购买了 {n}, 解除了虚弱!"
        elif t == "atk_up":
            player.statuses["atk_up"] = v
            return f"你花费 {c} 金币, 购买了 {n}, 未来 {v} 回合攻击+2!"
        elif t == "immune":
            player.statuses["immune"] = v
            return f"你花费 {c} 金币, 购买了 {n}, 未来 {v} 回合免疫负面!"
        elif t == "dodge":
            player.statuses["dodge"] = v
            return f"你花费 {c} 金币, 购买了 {n}, 未来 {v} 回合闪避提升!"
        elif t == "damage_reduction":
            player.statuses["damage_reduction"] = v
            return f"你花费 {c} 金币, 购买了 {n}, 未来 {v} 回合伤害减免!"
        elif t == "trap_resist":
            player.statuses["trap_resist"] = v
            return f"你花费 {c} 金币, 购买了 {n}, 未来 {v} 回合陷阱伤害减半!"
        else:
            return f"你花费 {c} 金币, 买下 {n}, 不知有何效果..."

# Scene Manager
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
    START_PLAYER_GOLD = 0
    DOOR_COMBOS = [
        ("monster", "treasure"),
        ("monster", "equip"),
        ("monster", "shop"),
        ("monster", "trap"),
        ("trap", "treasure"),
        ("trap", "equip"),
        ("trap", "shop"),
        ("shop", "treasure"),
        ("shop", "equip"),
    ]

class GameController:
    def __init__(self):
        self.game_config = GameConfig()
        self.player = Player("勇士", self.game_config.START_PLAYER_HP,
                             self.game_config.START_PLAYER_ATK,
                             self.game_config.START_PLAYER_GOLD)
        self.round_count = 0
        self.last_scene = None  # 用于记录上一个场景
        self.last_shop_message = ""
        self.last_monster_message = ""
        self.scene_manager = SceneManager()
        self.shop_logic = ShopLogic()

        self.door_scene = DoorScene(self)
        self.battle_scene = BattleScene(self)
        self.shop_scene = ShopScene(self)

        self.scene_manager.add_scene("door_scene", self.door_scene)
        self.scene_manager.add_scene("battle_scene", self.battle_scene)
        self.scene_manager.add_scene("shop_scene", self.shop_scene)
        self.go_to_scene("door_scene")

    def go_to_scene(self, name):
        if self.scene_manager.current_scene is not None:
            self.last_scene = self.scene_manager.current_scene
        self.scene_manager.go_to(name)

    def monster_loot(self, monster):
        tier = monster.tier
        if tier == 1:
            loot_list = ["healing_potion", "weapon", "gold"]
        elif tier == 2:
            loot_list = ["healing_potion", "weapon", "weapon", "gold", "revive_scroll", "armor_piece"]
        elif tier == 3:
            loot_list = ["weapon", "gold", "gold", "revive_scroll", "armor_piece"]
        else:
            loot_list = ["weapon", "weapon", "gold", "gold", "revive_scroll", "armor_piece"]
        choice = random.choice(loot_list)
        msg = ""
        p = self.player
        if choice == "healing_potion":
            heal = random.randint(5, 10)
            p.heal(heal)
            msg = f"怪物掉落治疗药剂, 你恢复 {heal} HP!"
        elif choice == "weapon":
            boost = random.randint(2, 4) + tier
            oldatk = p.atk
            p.atk += boost
            p.base_atk += boost
            msg = f"怪物掉落武器, 攻击力从 {oldatk} 升到 {p.atk}!"
        elif choice == "gold":
            amt = random.randint(8, 20) + 5 * tier
            p.add_gold(amt)
            msg = f"怪物掉落金币, 你获得 {amt} 金币!"
        elif choice == "revive_scroll":
            p.revive_scroll_count += 1
            msg = f"怪物掉落复活卷轴, 现有 {p.revive_scroll_count} 张!"
        elif choice == "armor_piece":
            inc = 5 + 2 * tier
            oldhp = p.hp
            p.hp += inc
            p.base_hp += inc
            msg = f"怪物掉落护甲碎片, HP 从 {oldhp} 变为 {p.hp}!"
        else:
            msg = "怪物似乎没掉落任何东西..."
        return msg

    def reset_game(self):
        self.player = Player("勇士", self.game_config.START_PLAYER_HP,
                             self.game_config.START_PLAYER_ATK,
                             self.game_config.START_PLAYER_GOLD)
        self.round_count = 0
        self.last_scene = None
        self.last_shop_message = ""
        self.last_monster_message = ""
        self.door_scene = DoorScene(self)
        self.battle_scene = BattleScene(self)
        self.shop_scene = ShopScene(self)
        self.scene_manager = SceneManager()
        self.scene_manager.add_scene("door_scene", self.door_scene)
        self.scene_manager.add_scene("battle_scene", self.battle_scene)
        self.scene_manager.add_scene("shop_scene", self.shop_scene)
        self.go_to_scene("door_scene")

# -------------------------------
# 2) Flask 路由及 Session 存储
# -------------------------------

def get_game():
    if "game_id" not in session:
        session["game_id"] = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    gid = session["game_id"]
    if gid not in games_store:
        games_store[gid] = GameController()
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
    scn_name = scn.__class__.__name__ if scn else "None"
    door_data = []
    if scn_name == "DoorScene":
        for ev, hint in scn.door_events:
            door_data.append({"event": ev, "hint": hint})
    elif p.hp <= 0 and hasattr(g, "door_scene"):
        for ev, hint in g.door_scene.door_events:
            door_data.append({"event": ev, "hint": hint})
        scn_name = "GameOver"

    monster_data = None
    if scn_name == "BattleScene" and scn.monster:
        monster_data = {"name": scn.monster.name, "hp": scn.monster.hp,
                        "atk": scn.monster.atk, "tier": scn.monster.tier}
    shop_data = None
    if scn_name == "ShopScene":
        shop_data = scn.shop_items

    state = {
      "scene": scn_name,
      "round": g.round_count,
      "player": {
        "hp": p.hp,
        "atk": p.atk,
        "gold": p.gold,
        "revive_scroll_count": p.revive_scroll_count,
        "status_desc": p.get_status_desc()
      },
      "door_events": door_data,
      "monster": monster_data,
      "shop_items": shop_data
    }
    # 如果有上次商店或战斗的提示，加入返回（例如被商人踢出的提示或遇怪提示）
    if hasattr(g, "last_shop_message") and g.last_shop_message:
        state["last_message"] = g.last_shop_message
        g.last_shop_message = ""
    if hasattr(g, "last_monster_message") and g.last_monster_message:
        state["last_message"] = g.last_monster_message
        g.last_monster_message = ""
    if p.hp <= 0:
        state["scene"] = "GameOver"
    return jsonify(state)

@app.route("/buttonAction", methods=["POST"])
def button_action():
    g = get_game()
    scn = g.scene_manager.current_scene
    data = request.json
    index = data.get("index", 0)
    if g.player.hp <= 0:
        scn_name = "GameOver"
    else:
        scn_name = scn.__class__.__name__ if scn else "None"

    if scn_name == "DoorScene":
        log_msg = scn.handle_choice(index)
    elif scn_name == "BattleScene":
        if index == 0:
            log_msg = scn.handle_action("attack")
        elif index == 1:
            log_msg = scn.handle_action("defend")
        elif index == 2:
            log_msg = scn.handle_action("escape")
        else:
            log_msg = "无效操作"
    elif scn_name == "ShopScene":
        log_msg = scn.handle_purchase(index)
    elif scn_name == "GameOver":
        # GameOver状态下：
        # 0 -> 重启游戏
        # 1 -> 使用复活卷轴（如果有则消费一个，恢复到上一个场景，不刷新门，不增加回合）
        # 2 -> 退出游戏（关闭 Python 进程）
        if index == 0:
            g.reset_game()
            log_msg = "游戏已重启"
        elif index == 1:
            p = g.player
            if p.revive_scroll_count > 0:
                p.revive_scroll_count -= 1
                p.hp = p.base_hp
                if g.last_scene is not None:
                    g.scene_manager.current_scene = g.last_scene
                    log_msg = f"使用复活卷轴成功, 回到上一个场景: {g.last_scene.__class__.__name__}!"
                else:
                    log_msg = "使用复活卷轴成功, 但未记录上一个场景."
            else:
                log_msg = "你没有复活卷轴, 无法复活!"
        elif index == 2:
            log_msg = "退出游戏"
            os._exit(0)
        else:
            log_msg = "无效操作"
    else:
        log_msg = "当前场景无操作"
    return jsonify({"log": log_msg})

# -------------------------------
# 3) 启动 Flask 应用
# -------------------------------

if __name__ == "__main__":
    app.run(debug=True)
