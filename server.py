# server.py
from flask import Flask, render_template, session, request, jsonify
from flask_session import Session
import random, string, os

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

class Player:
    def __init__(self, name="勇士", hp=20, atk=5, gold=0):
        self.name = name
        self.base_hp = hp
        self.hp = hp
        self.base_atk = atk
        self.atk = atk
        self.gold = gold
        self.statuses = {}  # 如 {"poison":3, "weak":2, ...}
        self.inventory = []  # 最多可存10个道具，每个道具为字典

    def take_damage(self, dmg):
        self.hp -= dmg

    def heal(self, amt):
        self.hp += amt

    def add_gold(self, amt):
        self.gold += amt

    def try_revive(self):
        # 检查库存中是否有复活卷轴
        for item in self.inventory:
            if item["type"] == "revive":
                self.inventory.remove(item)  # 消耗复活卷轴
                self.hp = self.base_hp
                return True
        return False

    def apply_turn_effects(self, is_battle_turn=False):
        immune = ("immune" in self.statuses and self.statuses["immune"] > 0)
        if "poison" in self.statuses and self.statuses["poison"] > 0 and not immune:
            self.hp -= 1
        self.atk = self.base_atk
        if "atk_multiplier" in self.statuses and self.statuses.get("atk_multiplier_duration", 0) > 0:
            self.atk *= self.statuses["atk_multiplier"]
        if "weak" in self.statuses and self.statuses["weak"] > 0 and not immune:
            self.atk = max(1, self.atk - 2)
        if "atk_up" in self.statuses and self.statuses["atk_up"] > 0:
            self.atk += 2
            
        # 处理恢复卷轴效果
        if "healing_scroll" in self.statuses and self.statuses["healing_scroll"] > 0:
            heal_amount = self.statuses.get("healing_scroll_amount", 0)
            if heal_amount > 0:
                self.heal(heal_amount)

        expired = []
        for st in self.statuses:
            # Reduce duration based on turn type
            if st == "barrier" and is_battle_turn:
                self.statuses[st] -= 1
            elif st != "barrier":
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
            elif k == "barrier":
                desc.append(f"结界({v}回合)")
            elif k == "dodge":
                desc.append(f"闪避({v}回合)")
            elif k == "damage_reduction":
                desc.append(f"伤害减免({v}回合)")
            elif k == "trap_resist":
                desc.append(f"陷阱减伤({v}回合)")
            elif k == "atk_multiplier":
                # 此状态持续时间另有 atk_multiplier_duration
                desc.append(f"攻击翻倍({self.statuses.get('atk_multiplier_duration', '?')}回合)")
            elif k == "healing_scroll":
                # 此状态效果值另有 healing_scroll_amount
                desc.append(f"每回合恢复{self.statuses.get('healing_scroll_amount', '?')}HP({v}回合)")
            else:
                desc.append(f"{k}({v}回合)")
        return ", ".join(desc)

class Monster:
    def __init__(self, name, hp, atk, tier=1):
        self.name = name
        self.hp = hp
        self.atk = atk
        self.tier = tier
        self.stunned_rounds = 0  # 新增：怪物晕眩回合

    def take_damage(self, dmg):
        self.hp -= dmg

# 如果传入 max_tier，则只生成符合条件的怪物
def get_random_monster(max_tier=None):
    monster_pool = [
        # Tier 1 - 新手怪物
        Monster("史莱姆", 15, 4, 1),
        Monster("哥布林", 20, 5, 1),
        Monster("狼", 18, 6, 1),
        Monster("蜘蛛", 16, 5, 1),
        Monster("蝙蝠", 14, 4, 1),
        Monster("小骷髅", 17, 5, 1),
        
        # Tier 2 - 中级怪物
        Monster("小恶魔", 25, 7, 2),
        Monster("牛头人", 35, 9, 2),
        Monster("食人花", 30, 8, 2),
        Monster("蜥蜴人", 28, 7, 2),
        Monster("石像鬼", 32, 8, 2),
        Monster("半人马", 38, 10, 2),
        
        # Tier 3 - 高级怪物
        Monster("巨龙", 40, 10, 3),
        Monster("暗黑骑士", 50, 12, 3),
        Monster("九头蛇", 45, 11, 3),
        Monster("独眼巨人", 48, 13, 3),
        Monster("地狱犬", 42, 12, 3),
        Monster("巫妖", 55, 14, 3),
        
        # Tier 4 - 精英怪物
        Monster("末日领主", 70, 15, 4),
        Monster("深渊魔王", 75, 18, 4),
        Monster("混沌使者", 65, 16, 4),
        Monster("虚空领主", 80, 20, 4),
        Monster("死亡骑士", 72, 17, 4),
        Monster("远古巨龙", 85, 22, 4),
    ]
    
    # 根据回合数限制怪物等级
    if max_tier is None:
        # 获取当前回合数
        current_round = get_game().round_count
        if current_round <= 5:
            max_tier = 1  # 前5回合只出现Tier 1怪物
        elif current_round <= 10:
            max_tier = 2  # 6-10回合可能出现Tier 2怪物
        elif current_round <= 15:
            max_tier = 3  # 11-15回合可能出现Tier 3怪物
        else:
            max_tier = 4  # 15回合后可能出现所有怪物
    
    # 过滤出符合条件的怪物
    filtered = [m for m in monster_pool if m.tier <= max_tier]
    if filtered:
        monster_pool = filtered
    
    return random.choice(monster_pool)

class DoorScene:
    def __init__(self, controller):
        self.controller = controller
        self.door_events = []
        self.has_initialized = False
        self.combo_hints = {
            # 基础组合提示
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
        
        # 怪物等级相关提示
        self.monster_tier_hints = {
            1: [
                "似乎有轻微的骚动...",
                "隐约听到细小的声响...",
                "有什么东西在暗处蠢蠢欲动...",
                "空气中飘来一丝危险的气息...",
                "好像有什么小东西在活动..."
            ],
            2: [
                "明显感觉到一股威胁...",
                "有生物的气息在靠近...",
                "危险的气息越来越浓...",
                "似乎有什么强大的存在...",
                "空气中弥漫着紧张的气氛..."
            ],
            3: [
                "一股强大的气息扑面而来...",
                "危险的气息令人窒息...",
                "有什么可怕的东西在等待...",
                "空气中充满了压迫感...",
                "似乎遇到了不得了的对手..."
            ],
            4: [
                "恐怖的气息笼罩着这里...",
                "空气中弥漫着死亡的气息...",
                "有什么可怕的存在在等待...",
                "危险的气息令人战栗...",
                "似乎遇到了传说中的存在..."
            ]
        }
        
        # 怪物种类相关提示
        self.monster_type_hints = {
            "史莱姆": ["黏糊糊的声音...", "有什么东西在蠕动...", "滑溜溜的声响..."],
            "哥布林": ["粗重的喘息声...", "矮小的身影闪过...", "野蛮的嚎叫..."],
            "狼": ["狼嚎声传来...", "野兽的脚步声...", "凶猛的咆哮..."],
            "蜘蛛": ["窸窸窣窣的声音...", "蛛网在颤动...", "八条腿的声响..."],
            "蝙蝠": ["翅膀拍打声...", "尖锐的叫声...", "黑暗中有什么在飞..."],
            "小骷髅": ["骨头摩擦声...", "阴森的笑声...", "亡灵的气息..."],
            "小恶魔": ["邪恶的笑声...", "地狱的气息...", "恶魔的低语..."],
            "牛头人": ["沉重的脚步声...", "愤怒的咆哮...", "牛角碰撞声..."],
            "食人花": ["植物摩擦声...", "花瓣的沙沙声...", "饥饿的嘶嘶声..."],
            "蜥蜴人": ["鳞片摩擦声...", "嘶嘶的吐信声...", "爬行动物的声响..."],
            "石像鬼": ["石头摩擦声...", "雕像的移动声...", "石头的碎裂声..."],
            "半人马": ["马蹄声...", "弓箭的弦声...", "半人半兽的嘶鸣..."],
            "巨龙": ["龙吟声...", "火焰的咆哮...", "龙翼的拍打声..."],
            "暗黑骑士": ["铠甲碰撞声...", "黑暗的气息...", "骑士的马蹄声..."],
            "九头蛇": ["多个头的嘶鸣...", "毒液的滴落声...", "蛇鳞的摩擦声..."],
            "独眼巨人": ["沉重的脚步声...", "愤怒的咆哮...", "大地的震动..."],
            "地狱犬": ["地狱的咆哮...", "火焰的嘶鸣...", "三头犬的吠叫..."],
            "巫妖": ["魔法的波动...", "死亡的气息...", "巫妖的咒语声..."],
            "末日领主": ["末日的低语...", "毁灭的气息...", "领主的咆哮..."],
            "深渊魔王": ["深渊的呼唤...", "魔王的威压...", "黑暗的咆哮..."],
            "混沌使者": ["混沌的波动...", "使者的低语...", "混乱的气息..."],
            "虚空领主": ["虚空的回响...", "空间扭曲声...", "领主的低语..."],
            "死亡骑士": ["死亡的气息...", "骑士的咆哮...", "亡灵的嘶鸣..."],
            "远古巨龙": ["远古的龙吟...", "时间的波动...", "巨龙的咆哮..."]
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
        p.apply_turn_effects(is_battle_turn=False)  # Adventure turn effects
        event_details = self.door_events[index]
        ev = event_details["event"]
        if ev == "monster":
            monster_info = event_details["monster"]
            monster = Monster(
                monster_info["name"],
                monster_info["hp"],
                monster_info["atk"],
                monster_info["tier"]
            )
            c.current_monster = monster
            monster_desc = f"你遇到了 {monster.name} (HP: {monster.hp}, ATK: {monster.atk}, Tier: {monster.tier})"
            c.go_to_scene("battle_scene")
            return f"第{c.round_count}回合：你选择了怪物之门，进入战斗场景! {monster_desc}"
        elif ev == "trap":
            dmg = event_details["trap"]["damage"]
            if "trap_resist" in p.statuses:
                dmg = max(1, int(dmg * 0.5))
            p.take_damage(dmg)
            extra_msg = ""
            if random.random() < 0.3:
                extra = random.randint(1, 5)
                p.add_gold(extra)
                extra_msg = f" 你意外发现了 {extra} 金币！"
            if p.hp <= 0:
                revived = p.try_revive()
                if revived:
                    msg = f"你踩了陷阱({dmg}伤害){extra_msg}，但复活卷轴救了你(HP={p.hp})!"
                else:
                    msg = f"你踩到陷阱({dmg}伤害){extra_msg}，不幸身亡..."
                self._generate_doors()
                return f"第{c.round_count}回合：{msg}"
            else:
                msg = f"你踩到陷阱，损失{dmg}HP!{extra_msg}"
                self._generate_doors()
                return f"第{c.round_count}回合：{msg}"
        elif ev == "treasure":
            g = event_details["treasure"]["gold"]
            p.add_gold(g)
            msg = f"你发现宝藏，获得{g}金币!"
            self._generate_doors()
            return f"第{c.round_count}回合：{msg}"
        elif ev == "equip":
            boost = event_details["equip"]["boost"]
            oldatk = p.atk
            p.atk += boost
            p.base_atk += boost
            msg = f"你捡到武器，攻击力从{oldatk}提升到{p.atk}!"
            self._generate_doors()
            return f"第{c.round_count}回合：{msg}"
        elif ev == "shop":
            if p.gold == 0:
                # 玩家金币为 0，显示被踢出消息并进入下一回合
                self._generate_doors()
                return f"第{c.round_count}回合：你没有钱，于是被商人踢了出来，进入下一回合的三扇门。"
            else:
                c.go_to_scene("shop_scene")
                return f"第{c.round_count}回合：你发现了商店，进去逛逛吧!"
        else:
            return f"第{c.round_count}回合：未知的门事件"

    def _generate_doors(self):
        config = self.controller.game_config
        combo_list = config.DOOR_COMBOS
        # 如果玩家金币为0，则过滤掉含"shop"的组合
        if self.controller.player.gold == 0:
            filtered = [combo for combo in combo_list if "shop" not in combo]
            if filtered:
                combo_list = filtered
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
            event_details = {"event": ev, "hint": hint}
            if ev == "monster":
                # 提前生成怪物并存储到事件详情
                monster = get_random_monster()
                event_details["monster"] = {
                    "name": monster.name,
                    "hp": monster.hp,
                    "atk": monster.atk,
                    "tier": monster.tier
                }
                # 根据怪物等级和种类生成更详细的提示
                tier_hint = random.choice(self.monster_tier_hints.get(monster.tier, ["危险的气息..."]))
                type_hint = random.choice(self.monster_type_hints.get(monster.name, ["未知生物的声响..."]))
                event_details["hint"] = f"{hint} {tier_hint} {type_hint}"
            elif ev == "trap":
                # 提前生成陷阱伤害
                dmg = random.randint(5, 10)
                event_details["trap"] = {"damage": dmg}
            elif ev == "treasure":
                # 提前生成宝藏金币
                g = random.randint(5, 15)
                event_details["treasure"] = {"gold": g}
            elif ev == "equip":
                # 提前生成装备提升
                boost = random.randint(1, 3)
                event_details["equip"] = {"boost": boost}
            elif ev == "shop":
                # 提前生成商店物品
                logic = self.controller.shop_logic
                logic.generate_items(self.controller.player)
                event_details["shop_items"] = logic.shop_items
            result.append(event_details)
        self.door_events = result

class BattleScene:
    def __init__(self, controller):
        self.controller = controller
        self.monster = None
        self.defending = False

    def on_enter(self):
        # 使用 DoorScene 中提前生成的怪物
        self.monster = self.controller.current_monster
        self.defending = False
        if self.monster:
            self.controller.last_monster_message = f"你遇到了 {self.monster.name} (HP: {self.monster.hp}, ATK: {self.monster.atk}, Tier: {self.monster.tier})"
        
    def handle_action(self, action):
        p = self.controller.player
        if "stun" in p.statuses and p.statuses["stun"] > 0:
            # 玩家晕眩时，怪物进行攻击
            msg = ["你处于眩晕状态, 无法行动!"]
            if "barrier" in p.statuses and p.statuses["barrier"] > 0:
                msg.append(f"{self.monster.name} 攻击被结界阻挡，未造成伤害!")
            else:
                mdmg = max(1, self.monster.atk - random.randint(0, 1))
                if self.defending:
                    mdmg = mdmg // 2
                if "damage_reduction" in p.statuses:
                    mdmg = int(mdmg * 0.7)
                p.take_damage(mdmg)
                msg.append(f"{self.monster.name} 攻击造成 {mdmg} 点伤害.")

            if p.hp <= 0:
                revived = p.try_revive()
                if revived:
                    msg.append("复活卷轴救了你(HP=1)!")
                else:
                    msg.append("你被怪物击倒, 英勇牺牲!")

            # 较强怪物可能附带负面效果
            if self.monster.tier >= 3 and random.random() < 0.3:
                effect = random.choice(["weak", "poison", "stun"])
                duration = random.randint(1, 2)
                p.statuses[effect] = duration
                msg.append(f"{self.monster.name} 附带 {effect} 效果 ({duration}回合)!")
            
            self.defending = False
            return "\n".join(msg)

        if action == "attack":
            return self.do_attack(p)
        elif action == "use_item":
            self.controller.go_to_scene("use_item_scene")
            return "进入使用道具界面"
        elif action == "escape":
            return self.do_escape(p)
        else:
            return "未知战斗指令"

    def do_attack(self, p):
        p.apply_turn_effects(is_battle_turn=True)
        # 如果有 atk_multiplier 状态则计算翻倍效果
        multiplier = p.statuses.get("atk_multiplier", 1)
        dmg = max(1, p.atk * multiplier - random.randint(0, 1))
        self.monster.hp -= dmg
        msg = [f"你攻击 {self.monster.name} 造成 {dmg} 点伤害."]
        if self.monster.hp <= 0:
            msg.append(f"你击败了 {self.monster.name}!")
            loot = self.controller.monster_loot(self.monster)
            msg.append(loot)
            self.controller.door_scene._generate_doors()  # 添加这行，确保战斗胜利后重新生成门
            self.controller.go_to_scene("door_scene")
            return "\n".join(msg)

        # 检查怪物是否晕眩
        if self.monster.stunned_rounds > 0:
            self.monster.stunned_rounds -= 1
            msg.append(f"{self.monster.name} 被晕眩，无法反击!")
        else:
            if "barrier" in p.statuses and p.statuses["barrier"] > 0:
                msg.append(f"{self.monster.name} 攻击被结界阻挡，未造成伤害!")
            else:
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

        # 较强怪物可能附带负面效果
        if self.monster.tier >= 3 and random.random() < 0.3:
            effect = random.choice(["weak", "poison", "stun"])
            duration = random.randint(1, 2)
            p.statuses[effect] = duration
            msg.append(f"{self.monster.name} 附带 {effect} 效果 ({duration}回合)!")
        self.defending = False
        return "\n".join(msg)

    def do_escape(self, p):
        fail_chance = min(1.0, self.monster.tier * 0.2)
        if random.random() < fail_chance:
            # 检查怪物是否晕眩
            if self.monster.stunned_rounds > 0:
                self.monster.stunned_rounds -= 1
                return "你试图逃跑, 怪物被晕眩，未能反击!"

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
            # 设置被踢出的日志消息
            self.controller.last_shop_message = "你没有钱，于是被商人踢了出来。"
            self.controller.door_scene._generate_doors()  # 刷新门
            self.controller.go_to_scene("door_scene")
            self.shop_items = []
            return  # 确保不再继续处理
        self.shop_items = logic.shop_items

    def handle_purchase(self, idx):
        logic = self.controller.shop_logic
        msg = logic.purchase_item(idx, self.controller.player)
        self.controller.door_scene._generate_doors()  # Ensure doors regenerate
        self.controller.go_to_scene("door_scene")
        return msg + "\n离开商店, 回到门场景"

class UseItemScene:
    def __init__(self, controller):
        self.controller = controller
        self.active_items = []

    def on_enter(self):
        p = self.controller.player
        # 只筛选主动使用的道具
        self.active_items = [item for item in p.inventory if item.get("active", False)]
        # 如果没有可用道具，则记录提示并返回战斗界面
        if not self.active_items:
            self.controller.last_use_item_message = "你没有可使用的道具"
            self.controller.go_to_scene("battle_scene")


    def handle_use(self, index):
        p = self.controller.player
        if index < 0 or index >= len(self.active_items):
            return "无效的道具选择"
        item = self.active_items[index]
        if item is None:
            return "你没有选择任何道具"
        t = item["type"]
        if t == "飞锤":
            # 使怪物晕眩3回合
            current_scene = self.controller.scene_manager.current_scene
            if current_scene.__class__.__name__ == "BattleScene" and current_scene.monster:
                current_scene.monster.stunned_rounds = 3
                effect_msg = "飞锤飞出，怪物被晕眩3回合！"
            else:
                effect_msg = "飞锤只能在战斗中使用。"
        elif t == "结界":
            p.statuses["barrier"] = 3
            effect_msg = "结界形成，接下来3回合你免受怪物伤害！"
        elif t == "巨大卷轴":
            p.statuses["atk_multiplier"] = 2
            p.statuses["atk_multiplier_duration"] = 3
            effect_msg = "巨大卷轴激活，当前战斗中你的攻击力翻倍！"
        elif t == "heal":
            heal_amt = item["value"]
            p.heal(heal_amt)
            effect_msg = f"治疗药水生效，恢复 {heal_amt} HP！"
        else:
            effect_msg = f"道具 {item['name']} 未定义效果。"
        if item in p.inventory:
            p.inventory.remove(item)
        self.controller.go_to_scene("battle_scene")
        return effect_msg

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
        # 每个元组：名称, 类型, 效果值, 基准价格, 是否主动使用
        possible = [
            ("普通治疗药水", "heal", 5, 10, False),
            ("高级治疗药水", "heal", 10, 20, False),
            ("超高级治疗药水", "heal", 15, 30, False),
            ("普通装备", "weapon", 2, 15, False),
            ("稀有装备", "weapon", 5, 30, False),
            ("复活卷轴", "revive", 1, 25, False),
            ("闪避卷轴", "dodge", 2, 15, False),
            ("减伤卷轴", "damage_reduction", 2, 15, False),
            ("陷阱减伤药剂", "trap_resist", 2, 10, False),
            ("解毒药水", "cure_poison", 0, 10, False),
            ("解除虚弱卷轴", "cure_weak", 0, 10, False),
            ("攻击力增益卷轴", "atk_up", 5, 20, False),
            ("免疫卷轴", "immune", 5, 25, False),
            ("恢复卷轴", "healing_scroll", 0, 30, False),
            ("飞锤", "飞锤", 0, 20, True),
            ("结界", "结界", 0, 20, True),
            ("巨大卷轴", "巨大卷轴", 0, 20, True),
        ]
        # 如果金币不足10，则只显示低价物品或增益类（注意：主动使用的物品仍保留）
        if player.gold < 10:
            possible = [item for item in possible if item[3] <= 10 or item[1] in ("atk_up", "immune", "dodge", "damage_reduction", "trap_resist")]
        # 使用 random.sample 生成不重复的三件商品
        if len(possible) >= 3:
            items = random.sample(possible, 3)
        else:
            items = [random.choice(possible) for _ in range(3)]
        gold = player.gold
        for item in items:
            name, t, val, basep, active = item
            cost = random.randint(int(basep * 0.8), int(basep * 1.2))
            if gold <= 0:
                cost = 0
            else:
                cost = min(cost, gold)
            self.shop_items.append({
                "name": name,
                "type": t,
                "value": val,
                "cost": cost,
                "active": active
            })

    def purchase_item(self, idx, player):
        if idx < 0 or idx >= len(self.shop_items):
            return "无效的购买选项!"
        item = self.shop_items[idx]
        if player.gold < item["cost"]:
            return "你的金币不足, 无法购买!"
        # 如果物品为主动使用类型，检查库存是否已满（最多10个）
        if item["active"] and len(player.inventory) >= 10:
            return "你的道具栏已满, 无法购买!"
        player.gold -= item["cost"]
        n, t, v, cost, active = item["name"], item["type"], item["value"], item["cost"], item["active"]
        if active:
            # 主动使用物品加入库存
            player.inventory.append(item.copy())
            # 修改复活卷轴的提示信息
            if t == "revive":
                effect = "已购买复活卷轴"
            else:
                effect = f"{n} +1, 已存入道具栏"
            return f"你花费 {cost} 金币, {effect}!"
        else:
            # 非主动使用物品立即生效
            if t == "heal":
                player.heal(v)
                effect = f"恢复 {v} HP"
            elif t == "weapon":
                oldatk = player.atk
                player.atk += v
                player.base_atk += v
                effect = f"攻击力从 {oldatk} 升到 {player.atk}"
            elif t == "revive":
                # 复活卷轴加入库存，但不显示+1
                player.inventory.append({"name": n, "type": t, "value": v, "cost": cost, "active": False})
                effect = "已获得复活卷轴"
            elif t == "cure_poison":
                if "poison" in player.statuses:
                    player.statuses["poison"] = 0
                effect = "解除了中毒"
            elif t == "cure_weak":
                if "weak" in player.statuses:
                    player.statuses["weak"] = 0
                effect = "解除了虚弱"
            elif t == "atk_up":
                duration = random.randint(5, 10)
                atk_boost = random.randint(10, 20)
                player.statuses["atk_up"] = duration
                player.atk += atk_boost
                effect = f"未来 {duration} 回合攻击力增加 {atk_boost}"
            elif t == "immune":
                duration = random.randint(5, 10)
                player.statuses["immune"] = duration
                effect = f"未来 {duration} 回合免疫负面"
            elif t == "dodge":
                duration = random.randint(5, 10)
                player.statuses["dodge"] = duration
                effect = f"未来 {duration} 回合闪避提升"
            elif t == "damage_reduction":
                duration = random.randint(5, 10)
                player.statuses["damage_reduction"] = duration
                effect = f"未来 {duration} 回合伤害减免"
            elif t == "trap_resist":
                duration = random.randint(5, 10)
                player.statuses["trap_resist"] = duration
                effect = f"未来 {duration} 回合陷阱伤害减半"
            elif t == "healing_scroll":  # 新增恢复卷轴处理
                duration = random.randint(10, 20)
                heal_per_turn = random.randint(3, 7)
                player.statuses["healing_scroll"] = duration
                player.statuses["healing_scroll_amount"] = heal_per_turn
                effect = f"未来 {duration} 回合每回合恢复 {heal_per_turn} 点生命"
            else:
                effect = "无效果"
            return f"你花费 {cost} 金币, 购买了 {n}, {effect}!"

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
        self.player.inventory = []  # 初始化道具栏
        self.round_count = 0
        self.last_scene = None  # 记录上一个场景
        self.last_shop_message = ""
        self.last_monster_message = ""
        self.current_monster = None  # 当前回合的怪物
        self.scene_manager = SceneManager()
        self.shop_logic = ShopLogic()

        self.door_scene = DoorScene(self)
        self.battle_scene = BattleScene(self)
        self.shop_scene = ShopScene(self)
        self.use_item_scene = UseItemScene(self)  # 新增使用道具场景

        self.scene_manager.add_scene("door_scene", self.door_scene)
        self.scene_manager.add_scene("battle_scene", self.battle_scene)
        self.scene_manager.add_scene("shop_scene", self.shop_scene)
        self.scene_manager.add_scene("use_item_scene", self.use_item_scene)
        self.go_to_scene("door_scene")

    def go_to_scene(self, name):
        if self.scene_manager.current_scene is not None:
            self.last_scene = self.scene_manager.current_scene
        self.scene_manager.go_to(name)

    def monster_loot(self, monster):
        tier = monster.tier
        p = self.player
        # 必定掉落金币
        gold_amt = random.randint(8, 20) + 5 * tier
        p.add_gold(gold_amt)
        msg = f"怪物掉落金币, 你获得 {gold_amt} 金币!"
        # 额外掉落（30% 概率）
        extra_drops = [
            ("healing_potion", lambda: f"治疗药剂, 恢复 {random.randint(5,10)} HP!"),
            ("weapon", lambda: f"武器, 攻击力提升 {random.randint(2,4)+tier}!"),
            ("revive_scroll", lambda: f"复活卷轴 +1 (现有 {p.revive_scroll_count} 张)"),
            ("armor_piece", lambda: f"护甲碎片, HP增加 {random.randint(5,10)}!")
        ]
        if random.random() < 0.3:
            drop = random.choice(extra_drops)
            if drop[0] == "revive_scroll":
                p.revive_scroll_count += 1
            extra_msg = drop[1]()
            msg += " " + extra_msg
        return msg

    def reset_game(self):
        self.player = Player("勇士", self.game_config.START_PLAYER_HP,
                             self.game_config.START_PLAYER_ATK,
                             self.game_config.START_PLAYER_GOLD)
        # 初始化道具栏，添加默认物品
        self.player.inventory = [
            {"name": "复活卷轴", "type": "revive", "value": 1, "cost": 0, "active": False},
            {"name": "飞锤", "type": "飞锤", "value": 0, "cost": 0, "active": True},
            {"name": "巨大卷轴", "type": "巨大卷轴", "value": 0, "cost": 0, "active": True},
            {"name": "结界", "type": "结界", "value": 0, "cost": 0, "active": True}
        ]
        self.round_count = 0
        self.last_scene = None
        self.last_shop_message = ""
        self.last_monster_message = ""
        self.door_scene = DoorScene(self)
        self.battle_scene = BattleScene(self)
        self.shop_scene = ShopScene(self)
        self.use_item_scene = UseItemScene(self)
        self.scene_manager = SceneManager()
        self.scene_manager.add_scene("door_scene", self.door_scene)
        self.scene_manager.add_scene("battle_scene", self.battle_scene)
        self.scene_manager.add_scene("shop_scene", self.shop_scene)
        self.scene_manager.add_scene("use_item_scene", self.use_item_scene)
        self.door_scene._generate_doors()  # Ensure doors regenerate
        self.go_to_scene("door_scene")
    def resume_scene(self):
        # 如果上一个场景存在且类型为 BattleScene，则恢复它
        if self.last_scene is not None and self.last_scene.__class__.__name__ == "BattleScene":
            self.scene_manager.current_scene = self.last_scene
        # 否则，默认切换到 battle_scene（但一般UseItemScene只在战斗中使用）
        else:
            self.scene_manager.current_scene = self.battle_scene

# -------------------------------
# 3) 新增： 使用道具场景
# -------------------------------
class UseItemScene:
    def __init__(self, controller):
        self.controller = controller
        self.active_items = []

    def on_enter(self):
        p = self.controller.player
        # 筛选库存中主动使用的道具，排除复活卷轴（active=False）
        self.active_items = [item for item in p.inventory if item.get("active", False)]
        if not self.active_items:
            # 如果没有可用道具，则返回战斗界面，并记录提示
            self.controller.last_use_item_message = "你没有可使用的道具"
            self.controller.go_to_scene("battle_scene")
    def handle_use(self, index):
        p = self.controller.player
        if index < 0 or index >= len(self.active_items):
            return "无效的道具选择"
        item = self.active_items[index]
        if not item:
            return "你没有选择任何道具"
        t = item["type"]
        if t == "飞锤":
            # 对当前怪物施加晕眩效果
            if self.controller.current_monster:
                self.controller.current_monster.stunned_rounds = 3
                effect_msg = "飞锤飞出，怪物被晕眩3回合！"
            else:
                effect_msg = "当前没有怪物，飞锤未产生效果。"
        elif t == "结界":
            p.statuses["barrier"] = 3
            effect_msg = "结界形成，接下来3回合你免受怪物伤害！"
        elif t == "巨大卷轴":
            p.statuses["atk_multiplier"] = 2
            p.statuses["atk_multiplier_duration"] = 3
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
        return effect_msg

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
    scn_name = scn.__class__.__name__ if scn else "None"
    door_data = []
    if scn_name == "DoorScene":
        for event_details in scn.door_events:
            door_data.append({"event": event_details["event"], "hint": event_details["hint"]})
    elif p.hp <= 0 and hasattr(g, "door_scene"):
        for event_details in g.door_scene.door_events:
            door_data.append({"event": event_details["event"], "hint": event_details["hint"]})
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
        "status_desc": p.get_status_desc(),
        "inventory": p.inventory
      },
      "door_events": door_data,
      "monster": monster_data,
      "shop_items": shop_data
    }
    if scn_name == "UseItemScene":
        state["active_items"] = scn.active_items
    if hasattr(g, "last_shop_message") and g.last_shop_message:
        state["last_message"] = g.last_shop_message
        g.last_shop_message = ""  # 清空消息，避免重复显示
    if hasattr(g, "last_monster_message") and g.last_monster_message:
        state["last_message"] = g.last_monster_message
        g.last_monster_message = ""
    if hasattr(g, "last_use_item_message") and g.last_use_item_message:
        state["last_message"] = g.last_use_item_message
        g.last_use_item_message = ""
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
        # 按钮：0->攻击，1->进入使用道具场景，2->逃跑
        if index == 0:
            log_msg = scn.handle_action("attack")
        elif index == 1:
            g.go_to_scene("use_item_scene")
            log_msg = "进入使用道具界面"
        elif index == 2:
            log_msg = scn.handle_action("escape")
        else:
            log_msg = "无效操作"
    elif scn_name == "ShopScene":
        log_msg = scn.handle_purchase(index)
    elif scn_name == "UseItemScene":
        log_msg = scn.handle_use(index)
    elif scn_name == "GameOver":
        # GameOver状态下：0->重启, 1->使用复活卷轴, 2->退出游戏
        if index == 0:
            g.reset_game()
            log_msg = "游戏已重启"
        elif index == 1:
            p = g.player
            revived = p.try_revive()
            if revived:
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
# 5) 启动 Flask 应用
# -------------------------------

if __name__ == "__main__":
    app.run(debug=True)
