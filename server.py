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

class StatusEffect:
    """状态效果定义类"""
    # 战斗状态：只在战斗回合中生效
    BATTLE_STATUSES = {
        "barrier": {
            "name": "结界",
            "description": "免受怪物伤害",
            "duration": 3,
            "is_battle_only": True
        },
        "atk_multiplier": {
            "name": "攻击翻倍",
            "description": "攻击力翻倍",
            "duration": 999,  # 使用足够大的数值确保在当前战斗中持续有效
            "is_battle_only": True,
            "value": 2
        },
        # 怪物造成的负面效果
        "poison": {
            "name": "中毒",
            "description": "每回合损失1点生命",
            "duration": 3,
            "is_battle_only": True,
            "value": -1,
            "is_monster_effect": True
        },
        "weak": {
            "name": "虚弱",
            "description": "攻击力降低2点",
            "duration": 3,
            "is_battle_only": True,
            "value": -2,
            "is_monster_effect": True
        },
        "stun": {
            "name": "眩晕",
            "description": "无法行动",
            "duration": 2,
            "is_battle_only": True,
            "is_monster_effect": True
        }
    }
    
    # 冒险状态：在冒险回合中生效
    ADVENTURE_STATUSES = {
        "atk_up": {
            "name": "攻击力提升",
            "description": "攻击力增加",
            "duration": 5,
            "is_battle_only": False,
            "value": 2
        },
        "immune": {
            "name": "免疫",
            "description": "免疫负面效果",
            "duration": 5,
            "is_battle_only": False
        },
        "dodge": {
            "name": "闪避",
            "description": "闪避提升",
            "duration": 5,
            "is_battle_only": False
        },
        "damage_reduction": {
            "name": "伤害减免",
            "description": "受到伤害减少30%",
            "duration": 5,
            "is_battle_only": False,
            "value": 0.7
        },
        "trap_resist": {
            "name": "陷阱减伤",
            "description": "陷阱伤害减半",
            "duration": 5,
            "is_battle_only": False,
            "value": 0.5
        },
        "healing_scroll": {
            "name": "恢复卷轴",
            "description": "每回合恢复生命",
            "duration": 10,
            "is_battle_only": False,
            "value": 5  # 默认恢复值，实际值在购买时随机生成
        }
    }
    
    @classmethod
    def get_status_info(cls, status_name):
        """获取状态效果的详细信息"""
        if status_name in cls.BATTLE_STATUSES:
            return cls.BATTLE_STATUSES[status_name]
        elif status_name in cls.ADVENTURE_STATUSES:
            return cls.ADVENTURE_STATUSES[status_name]
        return None
    
    @classmethod
    def is_battle_status(cls, status_name):
        """判断是否为战斗状态"""
        return status_name in cls.BATTLE_STATUSES
    
    @classmethod
    def is_adventure_status(cls, status_name):
        """判断是否为冒险状态"""
        return status_name in cls.ADVENTURE_STATUSES
    
    @classmethod
    def is_monster_effect(cls, status_name):
        """判断是否为怪物造成的效果"""
        status_info = cls.get_status_info(status_name)
        return status_info and status_info.get("is_monster_effect", False)
    
    @classmethod
    def clear_battle_statuses(cls, player):
        """清除所有战斗状态"""
        expired = []
        for st in player.statuses:
            if cls.is_battle_status(st):
                expired.append(st)
        for r in expired:
            del player.statuses[r]

class Player:
    def __init__(self, name="勇士", hp=20, atk=5, gold=0):
        self.name = name
        self.base_hp = hp
        self.hp = hp
        self.base_atk = atk
        self.atk = atk
        self.gold = gold
        self.statuses = {}  # 如 {"poison": {"duration": 3}, "weak": {"duration": 2}, ...}
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

    def is_stunned(self):
        """检查玩家是否处于晕眩状态"""
        return "stun" in self.statuses and self.statuses["stun"]["duration"] > 0

    def attack(self, target, is_defending=False):
        """玩家攻击目标"""
        # 检查是否晕眩
        if self.is_stunned():
            return ["你处于眩晕状态, 无法行动!"], False
            
        # 应用战斗状态效果
        self.apply_turn_effects(is_battle_turn=True)
        
        # 计算伤害
        multiplier = self.statuses.get("atk_multiplier", {"value": 1})
        dmg = max(1, self.atk * multiplier["value"] - random.randint(0, 1))
        
        # 造成伤害
        target.take_damage(dmg)
        msg = [f"你攻击 {target.name} 造成 {dmg} 点伤害."]
        
        # 检查目标是否死亡
        if target.hp <= 0:
            msg.append(f"你击败了 {target.name}!")
            return msg, True
        
        return msg, False

    def try_escape(self, monster):
        """尝试逃跑"""
        # 检查是否晕眩
        if self.is_stunned():
            return "你处于眩晕状态, 无法行动!", False
            
        fail_chance = min(1.0, monster.tier * 0.2)
        if random.random() < fail_chance:
            # 检查怪物是否晕眩
            if monster.has_status("stun"):
                monster.update_statuses()
                return "你试图逃跑, 怪物被晕眩，未能反击!", True

            # 计算怪物伤害
            mdmg = max(1, monster.atk - random.randint(0, 1))
            if "damage_reduction" in self.statuses:
                mdmg = int(mdmg * 0.7)
            
            # 受到伤害
            self.take_damage(mdmg)
            msg = [f"你试图逃跑, 但失败了！{monster.name} 反击造成 {mdmg} 点伤害."]
            
            # 检查是否死亡
            if self.hp <= 0:
                revived = self.try_revive()
                if revived:
                    msg.append("复活卷轴救了你(HP=1)!")
                else:
                    msg.append("你被怪物击倒, 英勇牺牲!")
            
            return "\n".join(msg), False
        else:
            # 逃跑成功时清除所有战斗状态
            StatusEffect.clear_battle_statuses(self)
            return "你成功逃跑!", True

    def apply_turn_effects(self, is_battle_turn=False):
        # 根据回合类型调用对应的函数
        if is_battle_turn:
            self._apply_battle_turn_effects()
        else:
            self._apply_adventure_turn_effects()

    def _apply_battle_turn_effects(self):
        """处理战斗回合的效果"""
        # 处理中毒效果
        immune = ("immune" in self.statuses and self.statuses["immune"]["duration"] > 0)
        if "poison" in self.statuses and self.statuses["poison"]["duration"] > 0 and not immune:
            self.hp -= 1
            
        # 处理攻击力相关效果
        self.atk = self.base_atk
        if "atk_multiplier" in self.statuses and self.statuses["atk_multiplier"]["duration"] > 0:
            self.atk *= self.statuses["atk_multiplier"]["value"]
        if "weak" in self.statuses and self.statuses["weak"]["duration"] > 0 and not immune:
            self.atk = max(1, self.atk - 2)
        if "atk_up" in self.statuses and self.statuses["atk_up"]["duration"] > 0:
            self.atk += 2
            
        # 更新战斗回合的状态持续时间
        self._update_battle_status_durations()

    def _apply_adventure_turn_effects(self):
        """处理冒险回合的效果"""
        # 处理中毒效果
        immune = ("immune" in self.statuses and self.statuses["immune"]["duration"] > 0)
        if "poison" in self.statuses and self.statuses["poison"]["duration"] > 0 and not immune:
            self.hp -= 1
            
        # 处理攻击力相关效果
        self.atk = self.base_atk
        if "atk_multiplier" in self.statuses and self.statuses["atk_multiplier"]["duration"] > 0:
            self.atk *= self.statuses["atk_multiplier"]["value"]
        if "weak" in self.statuses and self.statuses["weak"]["duration"] > 0 and not immune:
            self.atk = max(1, self.atk - 2)
        if "atk_up" in self.statuses and self.statuses["atk_up"]["duration"] > 0:
            self.atk += 2
            
        # 处理恢复卷轴效果
        if "healing_scroll" in self.statuses and self.statuses["healing_scroll"]["duration"] > 0:
            heal_amount = random.randint(1, 10)  # 每次随机恢复1-10点生命
            self.heal(heal_amount)
            print(f"恢复卷轴生效，恢复 {heal_amount} 点生命！")
                
        # 更新冒险回合的状态持续时间
        self._update_adventure_status_durations()

    def _update_battle_status_durations(self):
        """更新战斗回合的状态持续时间"""
        expired = []
        for st in self.statuses:
            # 战斗回合只处理战斗状态
            if StatusEffect.is_battle_status(st):
                self.statuses[st]["duration"] -= 1
                if self.statuses[st]["duration"] <= 0:
                    expired.append(st)
        for r in expired:
            del self.statuses[r]

    def _update_adventure_status_durations(self):
        """更新冒险回合的状态持续时间"""
        expired = []
        for st in self.statuses:
            # 冒险回合处理所有状态
            if StatusEffect.is_adventure_status(st):
                self.statuses[st]["duration"] -= 1
                if self.statuses[st]["duration"] <= 0:
                    expired.append(st)
        for r in expired:
            del self.statuses[r]

    def get_status_desc(self):
        if not self.statuses:
            return "无"
        desc = []
        for k, v in self.statuses.items():
            status_info = StatusEffect.get_status_info(k)
            if status_info:
                if k == "healing_scroll":
                    desc.append(f"每回合随机恢复1-10HP({v['duration']}回合)")
                elif k == "atk_multiplier":
                    desc.append(f"攻击翻倍")
                else:
                    desc.append(f"{status_info['name']}({v['duration']}回合)")
            else:
                desc.append(f"{k}({v['duration']}回合)")
        return ", ".join(desc)

    def apply_item_effect(self, item_type, value):
        """统一处理物品效果"""
        effect_msg = ""
        if item_type == "heal":
            self.heal(value)
            effect_msg = f"恢复 {value} HP"
        elif item_type == "weapon":
            oldatk = self.atk
            self.atk += value
            self.base_atk += value
            effect_msg = f"攻击力从 {oldatk} 升到 {self.atk}"
        elif item_type == "armor":
            old_hp = self.base_hp
            self.base_hp += value
            self.hp += value
            effect_msg = f"生命值从 {old_hp} 升到 {self.base_hp}"
        elif item_type == "revive":
            # 复活卷轴只添加到物品栏，不立即使用
            self.inventory.append({"name": "复活卷轴", "type": "revive", "value": 1, "cost": 0, "active": False})
            effect_msg = "获得复活卷轴"
        elif item_type == "cure_poison":
            if "poison" in self.statuses:
                self.statuses["poison"]["duration"] = 0
            effect_msg = "解除了中毒"
        elif item_type == "cure_weak":
            if "weak" in self.statuses:
                self.statuses["weak"]["duration"] = 0
            effect_msg = "解除了虚弱"
        elif item_type == "atk_up":
            duration = random.randint(5, 10)
            atk_boost = random.randint(10, 20)
            self.statuses["atk_up"] = {"duration": duration, "value": atk_boost}
            self.atk += atk_boost
            effect_msg = f"未来 {duration} 回合攻击力增加 {atk_boost}"
        elif item_type == "immune":
            duration = random.randint(5, 10)
            self.statuses["immune"] = {"duration": duration}
            effect_msg = f"未来 {duration} 回合免疫负面"
        elif item_type == "dodge":
            duration = random.randint(5, 10)
            self.statuses["dodge"] = {"duration": duration}
            effect_msg = f"未来 {duration} 回合闪避提升"
        elif item_type == "damage_reduction":
            duration = random.randint(5, 10)
            self.statuses["damage_reduction"] = {"duration": duration}
            effect_msg = f"未来 {duration} 回合伤害减免"
        elif item_type == "trap_resist":
            duration = random.randint(5, 10)
            self.statuses["trap_resist"] = {"duration": duration}
            effect_msg = f"未来 {duration} 回合陷阱伤害减半"
        elif item_type == "healing_scroll":
            duration = random.randint(10, 20)
            self.statuses["healing_scroll"] = {"duration": duration}
            effect_msg = f"未来 {duration} 回合每回合随机恢复1-10点生命"
        return effect_msg

class Monster:
    def __init__(self, name, hp, atk, tier=1):
        self.name = name
        self.hp = hp
        self.atk = atk
        self.tier = tier
        self.statuses = {}  # 使用状态系统来管理怪物的状态效果

    def take_damage(self, dmg):
        self.hp -= dmg

    def apply_status(self, status_name, duration):
        """应用状态效果"""
        self.statuses[status_name] = {"duration": duration}

    def has_status(self, status_name):
        """检查是否有特定状态"""
        return status_name in self.statuses and self.statuses[status_name]["duration"] > 0

    def update_statuses(self):
        """更新状态持续时间"""
        expired = []
        for status in self.statuses:
            self.statuses[status]["duration"] -= 1
            if self.statuses[status]["duration"] <= 0:
                expired.append(status)
        for status in expired:
            del self.statuses[status]

    def attack(self, target, is_defending=False):
        """怪物攻击目标"""
        # 检查是否晕眩
        if self.has_status("stun"):
            self.update_statuses()
            return [f"{self.name} 被晕眩，无法反击!"], False

        # 检查目标是否有结界
        if "barrier" in target.statuses and target.statuses["barrier"]["duration"] > 0:
            return [f"{self.name} 的攻击被结界挡住了!"], False

        # 计算伤害
        mdmg = max(1, self.atk - random.randint(0, 1))
        if is_defending:
            mdmg = mdmg // 2
        if "damage_reduction" in target.statuses:
            mdmg = int(mdmg * 0.7)

        # 造成伤害
        target.take_damage(mdmg)
        msg = [f"{self.name} 反击造成 {mdmg} 点伤害."]

        # 检查目标是否死亡
        if target.hp <= 0:
            revived = target.try_revive()
            if revived:
                msg.append("复活卷轴救了你(HP=1)!")
            else:
                msg.append("你被怪物击倒, 英勇牺牲!")

        # 较强怪物可能附带负面效果
        if self.tier >= 3 and random.random() < 0.3:
            effect = random.choice(["weak", "poison", "stun"])
            duration = random.randint(1, 2)
            target.statuses[effect] = {"duration": duration}
            msg.append(f"{self.name} 附带 {effect} 效果 ({duration}回合)!")

        return msg, False

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
        try:
            current_round = get_game().round_count
            if current_round <= 5:
                max_tier = 1  # 前5回合只出现Tier 1怪物
            elif current_round <= 10:
                max_tier = 2  # 6-10回合可能出现Tier 2怪物
            elif current_round <= 15:
                max_tier = 3  # 11-15回合可能出现Tier 3怪物
            else:
                max_tier = 4  # 15回合后可能出现所有怪物
        except:
            # 如果无法获取回合数，默认使用Tier 1
            max_tier = 1
    
    # 过滤出符合条件的怪物
    filtered = [m for m in monster_pool if m.tier <= max_tier]
    if filtered:
        monster_pool = filtered
    
    return random.choice(monster_pool)

class Door:
    # 基础组合提示
    combo_hints = {
        ("monster", "treasure"): [
            "有些骚动也许是野兽，也许是财宝",
            "血腥气中又闪着金光",
            "危险与机遇并存",
            "咆哮声中夹杂着金币的叮当声",
            "黑暗中似乎有宝藏，但似乎也有危险"
        ],
        ("monster", "equip"): [
            "危机中或许暗藏利器",
            "低沉咆哮与金属碰撞声交织",
            "危险中藏着武器",
            "野兽的咆哮与武器的寒光",
            "似乎有武器，但似乎也有危险"
        ],
        ("monster", "shop"): [
            "猛兽怒吼夹杂着商贩吆喝",
            "似有咆哮也有人在此做买卖",
            "商人的叫卖声中似乎有野兽的咆哮",
            "危险与交易并存",
            "商人的声音中似乎藏着危险"
        ],
        ("monster", "trap"): [
            "血腥气与阴森诡异混合",
            "猛兽或陷阱？都危险重重",
            "危险的气息扑面而来",
            "似乎有陷阱，似乎也有野兽",
            "黑暗中藏着双重危险"
        ],
        ("trap", "treasure"): [
            "危险气息中似乎闪现宝物光芒",
            "既像埋伏又像财宝，难料",
            "陷阱与宝藏并存",
            "金光闪闪，但似乎有机关",
            "宝藏近在眼前，但似乎有危险"
        ],
        ("trap", "equip"): [
            "陷阱暗示与金属声交织",
            "武器或机关，需要谨慎",
            "危险中藏着武器",
            "金属声与机关声交织",
            "似乎有武器，但似乎有陷阱"
        ],
        ("trap", "shop"): [
            "也许是陷阱伪装也许是商店",
            "商贩在此亦有危机气息",
            "商店中似乎有机关",
            "商人的声音中似乎有机关声",
            "交易与陷阱并存"
        ],
        ("shop", "treasure"): [
            "有金光也有吆喝声，或宝藏或商店",
            "闻到钱币味，也许能大赚一笔",
            "商店与宝藏并存",
            "金光闪闪，似乎有商人在此",
            "财富与交易并存"
        ],
        ("shop", "equip"): [
            "有人吆喝好物便宜卖，也许能捡武器",
            "商店与装备，也许能武装自己",
            "商人在此贩卖武器",
            "金属声与叫卖声交织",
            "商店中似乎有武器"
        ],
    }
    
    # 怪物等级相关提示
    monster_tier_hints = {
        1: [
            "似乎有轻微的骚动...",
            "隐约听到细小的声响...",
            "有什么东西在暗处蠢蠢欲动...",
            "空气中飘来一丝危险的气息...",
            "好像有什么小东西在活动...",
            "轻微的脚步声传来...",
            "有什么东西在移动...",
            "危险的气息若隐若现..."
        ],
        2: [
            "明显感觉到一股威胁...",
            "有生物的气息在靠近...",
            "危险的气息越来越浓...",
            "似乎有什么强大的存在...",
            "空气中弥漫着紧张的气氛...",
            "沉重的脚步声传来...",
            "有什么东西在靠近...",
            "危险的气息越来越强..."
        ],
        3: [
            "一股强大的气息扑面而来...",
            "危险的气息令人窒息...",
            "有什么可怕的东西在等待...",
            "空气中充满了压迫感...",
            "似乎遇到了不得了的对手...",
            "强大的气息令人战栗...",
            "有什么可怕的存在在等待...",
            "危险的气息令人不安..."
        ],
        4: [
            "恐怖的气息笼罩着这里...",
            "空气中弥漫着死亡的气息...",
            "有什么可怕的存在在等待...",
            "危险的气息令人战栗...",
            "似乎遇到了传说中的存在...",
            "死亡的气息扑面而来...",
            "有什么可怕的东西在等待...",
            "恐怖的气息令人窒息..."
        ]
    }
    
    # 怪物种类相关提示
    monster_type_hints = {
        "史莱姆": [
            "黏糊糊的声音...",
            "有什么东西在蠕动...",
            "滑溜溜的声响...",
            "黏液滴落的声音...",
            "软绵绵的移动声..."
        ],
        "哥布林": [
            "粗重的喘息声...",
            "矮小的身影闪过...",
            "野蛮的嚎叫...",
            "矮小的脚步声...",
            "粗鲁的说话声..."
        ],
        "狼": [
            "狼嚎声传来...",
            "野兽的脚步声...",
            "凶猛的咆哮...",
            "狼爪摩擦声...",
            "野兽的低吼..."
        ],
        "蜘蛛": [
            "窸窸窣窣的声音...",
            "蛛网在颤动...",
            "八条腿的声响...",
            "蛛丝摩擦声...",
            "蜘蛛的嘶嘶声..."
        ],
        "蝙蝠": [
            "翅膀拍打声...",
            "尖锐的叫声...",
            "黑暗中有什么在飞...",
            "蝙蝠的吱吱声...",
            "翅膀的呼啸声..."
        ],
        "小骷髅": [
            "骨头摩擦声...",
            "阴森的笑声...",
            "亡灵的气息...",
            "骨骼的咔咔声...",
            "死灵的低语..."
        ],
        "小恶魔": [
            "邪恶的笑声...",
            "地狱的气息...",
            "恶魔的低语...",
            "地狱的咆哮...",
            "恶魔的嘶鸣..."
        ],
        "牛头人": [
            "沉重的脚步声...",
            "愤怒的咆哮...",
            "牛角碰撞声...",
            "牛蹄的踏地声...",
            "愤怒的嘶吼..."
        ],
        "食人花": [
            "植物摩擦声...",
            "花瓣的沙沙声...",
            "饥饿的嘶嘶声...",
            "藤蔓的蠕动声...",
            "花朵的咀嚼声..."
        ],
        "蜥蜴人": [
            "鳞片摩擦声...",
            "嘶嘶的吐信声...",
            "爬行动物的声响...",
            "鳞片的沙沙声...",
            "蜥蜴的嘶鸣..."
        ],
        "石像鬼": [
            "石头摩擦声...",
            "雕像的移动声...",
            "石头的碎裂声...",
            "石像的咆哮...",
            "石头的碰撞声..."
        ],
        "半人马": [
            "马蹄声...",
            "弓箭的弦声...",
            "半人半兽的嘶鸣...",
            "马蹄的踏地声...",
            "弓箭的呼啸声..."
        ],
        "巨龙": [
            "龙吟声...",
            "火焰的咆哮...",
            "龙翼的拍打声...",
            "龙息的呼啸...",
            "龙鳞的摩擦声..."
        ],
        "暗黑骑士": [
            "铠甲碰撞声...",
            "黑暗的气息...",
            "骑士的马蹄声...",
            "黑暗的咆哮...",
            "铠甲的摩擦声..."
        ],
        "九头蛇": [
            "多个头的嘶鸣...",
            "毒液的滴落声...",
            "蛇鳞的摩擦声...",
            "蛇头的嘶鸣...",
            "毒液的嘶嘶声..."
        ],
        "独眼巨人": [
            "沉重的脚步声...",
            "愤怒的咆哮...",
            "大地的震动...",
            "巨人的怒吼...",
            "地面的震动..."
        ],
        "地狱犬": [
            "地狱的咆哮...",
            "火焰的嘶鸣...",
            "三头犬的吠叫...",
            "地狱的嘶吼...",
            "火焰的咆哮..."
        ],
        "巫妖": [
            "魔法的波动...",
            "死亡的气息...",
            "巫妖的咒语声...",
            "魔法的低语...",
            "死灵的咒语..."
        ],
        "末日领主": [
            "末日的低语...",
            "毁灭的气息...",
            "领主的咆哮...",
            "末日的咆哮...",
            "毁灭的嘶鸣..."
        ],
        "深渊魔王": [
            "深渊的呼唤...",
            "魔王的威压...",
            "黑暗的咆哮...",
            "深渊的咆哮...",
            "魔王的低语..."
        ],
        "混沌使者": [
            "混沌的波动...",
            "使者的低语...",
            "混乱的气息...",
            "混沌的咆哮...",
            "混乱的嘶鸣..."
        ],
        "虚空领主": [
            "虚空的回响...",
            "空间扭曲声...",
            "领主的低语...",
            "虚空的咆哮...",
            "空间的扭曲..."
        ],
        "死亡骑士": [
            "死亡的气息...",
            "骑士的咆哮...",
            "亡灵的嘶鸣...",
            "死亡的咆哮...",
            "骑士的低语..."
        ],
        "远古巨龙": [
            "远古的龙吟...",
            "时间的波动...",
            "巨龙的咆哮...",
            "远古的咆哮...",
            "时间的扭曲..."
        ]
    }

    @classmethod
    def generate_monster_door(cls, monster):
        """生成怪物门"""
        # 创建 Monster 对象
        monster_obj = Monster(
            monster.name,
            monster.hp,
            monster.atk,
            monster.tier
        )
        event_details = {
            "monster": {
                "name": monster.name,
                "hp": monster.hp,
                "atk": monster.atk,
                "tier": monster.tier
            }
        }
        return cls("monster", event_details, monster_obj)

    def __init__(self, event, event_details=None, monster=None):
        self.event = event
        self.event_details = event_details or {}
        # 根据事件类型生成提示
        if event == "monster":
            self.hint = self.generate_mixed_hints(event, monster)
        else:
            self.hint = self.generate_mixed_hints(event)

    @classmethod
    def generate_door_hint(cls, door_type, monster=None):
        """生成门的提示
        Args:
            door_type: 门的类型 ("monster", "trap", "treasure", "equip", "shop")
            monster: 如果是怪物门，需要传入怪物对象
        """
        # 获取该门的基础提示
        if door_type == "monster":
            base_hint = "门后传来怪物的咆哮声"
            if monster:
                # 使用怪物的真实等级和类型
                tier_hint = cls.monster_tier_hints.get(monster.tier, ["危险的气息..."])[0]
                type_hint = cls.monster_type_hints.get(monster.name, ["未知生物的声响..."])[0]
                return f"{base_hint} {tier_hint} {type_hint}"
            else:
                # 使用随机的等级和类型
                tier_hint = cls.monster_tier_hints[1][0]
                type_hint = list(cls.monster_type_hints.values())[0][0]
                return f"{base_hint} {tier_hint} {type_hint}"
        elif door_type == "trap":
            base_hint = "门后传来机关转动的声音"
            return base_hint
        elif door_type == "treasure":
            base_hint = "门后传来金币碰撞的声音"
            return base_hint
        elif door_type == "equip":
            base_hint = "门后传来金属碰撞的声音"
            return base_hint
        elif door_type == "shop":
            base_hint = "门后传来商人的吆喝声"
            return base_hint
        else:
            base_hint = "门后传来奇怪的声音"
            return base_hint

    @classmethod
    def generate_mixed_hints(cls, real_event, monster=None):
        """生成混淆的提示，包含真实提示和虚假提示"""
        # 生成真实提示
        real_hint = cls.generate_door_hint(real_event, monster)
        
        # 生成2-3个虚假提示
        fake_hints = []
        num_fake = random.randint(2, 3)
        
        # 获取所有可能的门类型
        all_events = ["monster", "trap", "treasure", "equip", "shop"]
        
        for _ in range(num_fake):
            # 随机选择一个不同于真实事件的门类型
            fake_event = random.choice([e for e in all_events if e != real_event])
            # 如果是怪物门，生成一个随机的怪物提示
            if fake_event == "monster":
                fake_monster = get_random_monster()
                fake_hint = cls.generate_door_hint(fake_event, fake_monster)
            else:
                fake_hint = cls.generate_door_hint(fake_event)
            fake_hints.append(fake_hint)
        
        # 将所有提示打乱，但确保真实提示一定在其中
        all_hints = [real_hint] + fake_hints
        random.shuffle(all_hints)
        
        # 将所有提示组合成一个字符串，用换行符分隔
        return "\n".join(all_hints)

    @classmethod
    def generate_trap_door(cls):
        """生成陷阱门"""
        dmg = random.randint(5, 10)
        event_details = {
            "trap": {"damage": dmg}
        }
        return cls("trap", event_details)

    @classmethod
    def generate_treasure_door(cls):
        """生成宝藏门"""
        g = random.randint(5, 15)
        event_details = {
            "treasure": {"gold": g}
        }
        return cls("treasure", event_details)

    @classmethod
    def generate_equip_door(cls):
        """生成装备门"""
        boost = random.randint(1, 3)
        event_details = {
            "equip": {"boost": boost}
        }
        return cls("equip", event_details)

    @classmethod
    def generate_shop_door(cls):
        """生成商店门"""
        return cls("shop")

    def enter(self, player, controller):
        """进入门并处理事件"""
        if self.event == "monster":
            monster_info = self.event_details["monster"]
            monster = Monster(
                monster_info["name"],
                monster_info["hp"],
                monster_info["atk"],
                monster_info["tier"]
            )
            controller.current_monster = monster
            monster_desc = f"你遇到了 {monster.name} (HP: {monster.hp}, ATK: {monster.atk}, Tier: {monster.tier})"
            controller.go_to_scene("battle_scene")
            return f"你选择了怪物之门，进入战斗场景! {monster_desc}"
            
        elif self.event == "trap":
            dmg = self.event_details["trap"]["damage"]
            if "trap_resist" in player.statuses:
                dmg = max(1, int(dmg * 0.5))
            player.take_damage(dmg)
            extra_msg = ""
            if random.random() < 0.3:
                extra = random.randint(1, 5)
                player.add_gold(extra)
                extra_msg = f" 你意外发现了 {extra} 金币！"
            if player.hp <= 0:
                revived = player.try_revive()
                if revived:
                    msg = f"你踩了陷阱({dmg}伤害){extra_msg}，但复活卷轴救了你(HP={player.hp})!"
                else:
                    msg = f"你踩到陷阱({dmg}伤害){extra_msg}，不幸身亡..."
                return msg
            else:
                return f"你踩到陷阱，损失{dmg}HP!{extra_msg}"
                
        elif self.event == "treasure":
            g = self.event_details["treasure"]["gold"]
            player.add_gold(g)
            return f"你发现宝藏，获得{g}金币!"
            
        elif self.event == "equip":
            boost = self.event_details["equip"]["boost"]
            oldatk = player.atk
            player.atk += boost
            player.base_atk += boost
            return f"你捡到武器，攻击力从{oldatk}提升到{player.atk}!"
            
        elif self.event == "shop":
            if player.gold == 0:
                return "你没有钱，于是被商人踢了出来。"
            else:
                controller.go_to_scene("shop_scene")
                return "你发现了商店，进去逛逛吧!"
                
        return "未知的门事件"

class DoorScene:
    def __init__(self, controller):
        self.controller = controller
        self.doors = []
        self.has_initialized = False

    def on_enter(self):
        if not self.has_initialized:
            self._generate_doors()
            self.has_initialized = True

    def handle_choice(self, index):
        c = self.controller
        p = c.player
        if index < 0 or index >= len(self.doors):
            return "无效的门选择"
        c.round_count += 1
        
        # 如果选择了非怪物门，清除所有战斗状态
        door = self.doors[index]
        if door.event != "monster":
            StatusEffect.clear_battle_statuses(p)
        p.apply_turn_effects(is_battle_turn=False)  # Adventure turn effects
        
        # 进入门并处理事件
        msg = door.enter(p, c)
        
        # 如果不是怪物门，重新生成门
        if door.event != "monster":
            self._generate_doors()
            
        return f"第{c.round_count}回合：{msg}"

    def _generate_doors(self):
        """生成三扇门，确保至少一扇是怪物门"""
        # 获取可用的门类型
        available_doors = ["trap", "treasure", "equip"]
        if self.controller.player.gold > 0:
            available_doors.append("shop")
            
        # 生成一扇怪物门
        monster = get_random_monster()
        monster_door = Door.generate_monster_door(monster)
        
        # 生成其他两扇门
        other_doors = []
        for _ in range(2):
            door_type = random.choice(available_doors)
            if door_type == "trap":
                door = Door.generate_trap_door()
            elif door_type == "treasure":
                door = Door.generate_treasure_door()
            elif door_type == "equip":
                door = Door.generate_equip_door()
            elif door_type == "shop":
                door = Door.generate_shop_door()
            other_doors.append(door)
            
        # 随机打乱三扇门的顺序
        self.doors = [monster_door] + other_doors
        random.shuffle(self.doors)

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
            monster_desc = f"你遇到了 {self.monster.name} (HP: {self.monster.hp}, ATK: {self.monster.atk}, Tier: {self.monster.tier})"
            if self.monster.has_status("stun"):
                monster_desc += f" [晕眩{self.monster.statuses['stun']['duration']}回合]"
            self.controller.last_monster_message = monster_desc
        
    def handle_action(self, action):
        p = self.controller.player
        if p.is_stunned():
            # 先应用战斗状态效果
            p.apply_turn_effects(is_battle_turn=True)
            # 玩家晕眩时，怪物进行攻击
            msg = ["你处于眩晕状态, 无法行动!"]
            monster_msg, _ = self.monster.attack(p, self.defending)
            msg.extend(monster_msg)
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
        # 玩家攻击
        msg, monster_dead = p.attack(self.monster, self.defending)
        
        # 如果怪物未死亡，怪物反击
        if not monster_dead:
            monster_msg, _ = self.monster.attack(p, self.defending)
            msg.extend(monster_msg)
        
        # 如果怪物死亡，处理战利品
        if monster_dead:
            loot = self.controller.monster_loot(self.monster)
            msg.append(loot)
            # 清除所有战斗状态
            StatusEffect.clear_battle_statuses(p)
            self.controller.door_scene._generate_doors()  # 添加这行，确保战斗胜利后重新生成门
            self.controller.go_to_scene("door_scene")
        
        self.defending = False
        return "\n".join(msg)

    def do_escape(self, p):
        msg, success = p.try_escape(self.monster)
        if success:
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
        return effect_msg

class ShopLogic:
    def __init__(self):
        self.shop_items = []

    def generate_items(self, player):
        self.shop_items = []
        if player.gold == 0:
            return
        has_neg = False
        if "poison" in player.statuses and player.statuses["poison"]["duration"] > 0:
            has_neg = True
        if "weak" in player.statuses and player.statuses["weak"]["duration"] > 0:
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
            effect = f"{n}已存入道具栏"
        else:
            # 非主动使用物品立即生效
            effect = player.apply_item_effect(t, v)
            
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

        # 创建场景
        self.door_scene = DoorScene(self)
        self.battle_scene = BattleScene(self)
        self.shop_scene = ShopScene(self)
        self.use_item_scene = UseItemScene(self)

        # 注册场景
        self.scene_manager.add_scene("door_scene", self.door_scene)
        self.scene_manager.add_scene("battle_scene", self.battle_scene)
        self.scene_manager.add_scene("shop_scene", self.shop_scene)
        self.scene_manager.add_scene("use_item_scene", self.use_item_scene)

        # 设置初始场景并生成门
        self.scene_manager.current_scene = self.door_scene
        self.door_scene._generate_doors()

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
        if random.random() < 0.3:
            drop_type = random.choice(["healing_potion", "weapon", "armor"])
            if drop_type == "healing_potion":
                heal_amt = random.randint(5, 10)
                effect_msg = p.apply_item_effect("heal", heal_amt)
                msg += f" 治疗药剂, {effect_msg}!"
            elif drop_type == "weapon":
                atk_boost = random.randint(2, 4) + tier
                effect_msg = p.apply_item_effect("weapon", atk_boost)
                msg += f" 武器, {effect_msg}!"
            elif drop_type == "armor":
                hp_boost = random.randint(5, 10)
                effect_msg = p.apply_item_effect("armor", hp_boost)
                msg += f" 护甲碎片, {effect_msg}!"
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
        for door in scn.doors:
            # 显示所有提示
            door_data.append({
                "event": door.event,
                "hint": door.hint
            })
    elif p.hp <= 0 and hasattr(g, "door_scene"):
        for door in g.door_scene.doors:
            # 显示所有提示
            door_data.append({
                "event": door.event,
                "hint": door.hint
            })
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
