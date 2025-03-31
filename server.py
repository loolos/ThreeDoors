# server.py
from flask import Flask, render_template, session, request, jsonify, redirect, url_for
from flask_session import Session
import random, string, os
from models.door import Door
from models.monster import Monster, get_random_monster

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
        "damage_reduction": {
            "name": "伤害减免",
            "description": "受到伤害减少30%",
            "duration": 5,
            "is_battle_only": False,
            "value": 0.7
        },
        "healing_scroll": {
            "name": "恢复卷轴",
            "description": "每回合恢复生命",
            "duration": 10,
            "is_battle_only": False,
            "value": 5  # 默认恢复值，实际值在购买时随机生成
        },
        "immune": {
            "name": "免疫",
            "description": "免疫所有负面效果",
            "duration": 5,
            "is_battle_only": False
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
        self.hp = hp
        self.base_atk = atk
        self.atk = atk
        self.gold = gold
        self.statuses = {}  # 如 {"poison": {"duration": 3}, "weak": {"duration": 2}, ...}
        self.inventory = []  # 最多可存10个道具，每个道具为字典

    def take_damage(self, dmg):
        self.hp -= dmg

    def heal(self, amount):
        """恢复生命值"""
        old_hp = self.hp
        self.hp += amount  # 直接增加生命值
        return self.hp - old_hp  # 返回实际恢复的生命值

    def add_gold(self, amt):
        self.gold += amt

    def try_revive(self):
        # 检查库存中是否有复活卷轴
        for item in self.inventory:
            if item["type"] == "revive":
                self.inventory.remove(item)  # 消耗复活卷轴
                self.hp = 20  # 复活后恢复20点生命值
                return True
        return False

    def is_stunned(self):
        """检查玩家是否处于晕眩状态"""
        return "stun" in self.statuses and self.statuses["stun"]["duration"] > 0

    def attack(self, target):
        """玩家攻击目标"""
        # 检查是否晕眩
        if self.is_stunned():
            return ["你处于眩晕状态, 无法行动!"], False
            
        # 应用战斗状态效果
        self.apply_turn_effects(is_battle_turn=True)
        
        # 计算伤害
        dmg = max(1, self.atk - random.randint(0, 1))
        
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
        msg = []  # 初始化msg列表
        # 计算逃跑概率
        escape_chance = 0.3  # 基础30%概率
        if "weak" in self.statuses:
            escape_chance -= 0.1  # 虚弱状态降低10%概率
        if "poison" in self.statuses:
            escape_chance -= 0.1  # 中毒状态降低10%概率
        if "stun" in self.statuses:
            escape_chance -= 0.2  # 晕眩状态降低20%概率
            
        # 尝试逃跑
        if random.random() < escape_chance:
            return ["你成功逃脱了!"], True
        else:
            # 逃跑失败，受到伤害
            mdmg = max(1, monster.atk - random.randint(0, 1))
            if "damage_reduction" in self.statuses:
                original_dmg = mdmg
                mdmg = int(mdmg * 0.25)  # 减少75%伤害
                msg.append(f"一部分伤害被减伤卷轴挡掉了！")
            self.take_damage(mdmg)
            msg.append(f"逃跑失败，{monster.name} 反击造成 {mdmg} 点伤害!")
            
            # 检查是否死亡
            if self.hp <= 0:
                revived = self.try_revive()
                if revived:
                    msg.append("复活卷轴救了你(HP=1)!")
                else:
                    msg.append("你被怪物击倒, 英勇牺牲!")
            
            return msg, False

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
            self.atk = self.base_atk * self.statuses["atk_multiplier"]["value"]
        if "weak" in self.statuses and self.statuses["weak"]["duration"] > 0 and not immune:
            self.atk = max(1, self.atk - 2)
        if "atk_up" in self.statuses and self.statuses["atk_up"]["duration"] > 0:
            # 确保atk_up状态有value字段
            if "value" in self.statuses["atk_up"]:
                self.atk += self.statuses["atk_up"]["value"]
            
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
            # 确保atk_up状态有value字段
            if "value" in self.statuses["atk_up"]:
                self.atk += self.statuses["atk_up"]["value"]
            
        # 处理恢复卷轴效果
        if "healing_scroll" in self.statuses and self.statuses["healing_scroll"]["duration"] > 0:
            heal_amount = random.randint(1, 5)  # 每次随机恢复1-5点生命
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
                    desc.append(f"每回合随机恢复1-5HP({v['duration']}回合)")
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
            old_hp = self.hp
            self.hp += value
            effect_msg = f"生命值从 {old_hp} 升到 {self.hp}"
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
        else:
            # 处理状态效果卷轴
            duration = random.randint(10, 20)  # 统一使用10-20回合的持续时间
            if item_type == "atk_up":
                atk_boost = random.randint(10, 20)  # 攻击力提升10-20
                if "atk_up" in self.statuses:
                    # 如果已有atk_up状态，累加持续时间，取较大的攻击力提升
                    old_duration = self.statuses["atk_up"]["duration"]
                    old_value = self.statuses["atk_up"].get("value", 0)
                    self.statuses["atk_up"]["duration"] = old_duration + duration
                    self.statuses["atk_up"]["value"] = max(old_value, atk_boost)
                    effect_msg = f"攻击力增益效果叠加，提升 {self.statuses['atk_up']['value']}，持续 {self.statuses['atk_up']['duration']} 回合"
                else:
                    self.statuses["atk_up"] = {"duration": duration, "value": atk_boost}
                    effect_msg = f"未来 {duration} 回合攻击力增加 {atk_boost}"
            elif item_type in ["damage_reduction", "healing_scroll", "immune"]:
                if item_type in self.statuses:
                    # 如果已有状态，累加持续时间
                    self.statuses[item_type]["duration"] += duration
                    effect_msg = f"{item_type}效果叠加，持续 {self.statuses[item_type]['duration']} 回合"
                else:
                    self.statuses[item_type] = {"duration": duration}
                    scroll_names = {
                        "healing_scroll": "恢复卷轴",
                        "damage_reduction": "减伤卷轴",
                        "immune": "免疫卷轴",
                    }
                    effect_msg = f"未来 {duration} 回合{scroll_names[item_type]}效果"
        return effect_msg

    def revive(self):
        """复活"""
        if self.hp <= 0:
            self.hp = 20  # 复活后恢复20点生命值
            return True
        return False

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
        
        # 如果选择了非怪物门，清除所有战斗状态
        door = self.doors[index]
        if door.event != "monster":
            StatusEffect.clear_battle_statuses(p)
        p.apply_turn_effects(is_battle_turn=False)  # Adventure turn effects
        
        # 进入门并处理事件
        msg = door.enter(p, c)
        c.add_message(f"第{c.round_count}回合：{msg}")
            
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
            msg = ["你处于眩晕状态, 无法行动!"]
            monster_msg, _ = self.monster.attack(p)
            msg.extend(monster_msg)
            self.controller.add_message("\n".join(msg))
            return

        if index == 0:
            self.do_attack(p)
        elif index == 1:
            self.controller.go_to_scene("use_item_scene")
            self.controller.add_message("进入使用道具界面")
        elif index == 2:
            self.do_escape(p)
        else:
            self.controller.add_message("无效操作")

    def do_attack(self, p):
        # 玩家攻击
        msg, monster_dead = p.attack(self.monster)
        
        # 如果怪物未死亡，怪物反击
        if not monster_dead:
            monster_msg, _ = self.monster.attack(p)
            msg.extend(monster_msg)
            # 检查玩家生命值
            if p.hp <= 0:
                self.controller.go_to_scene("game_over_scene")
        
        # 如果怪物死亡，处理战利品
        if monster_dead:
            loot = self.controller.monster_loot(self.monster)
            msg.append(loot)
            # 清除所有战斗状态
            StatusEffect.clear_battle_statuses(p)
            self.controller.door_scene._generate_doors()  # 添加这行，确保战斗胜利后重新生成门
            self.controller.go_to_scene("door_scene")
        
        self.controller.add_message("\n".join(msg))

    def do_escape(self, p):
        msg, success = p.try_escape(self.monster)
        if success:
            self.controller.go_to_scene("door_scene")
        self.controller.add_message("\n".join(msg))
        # 检查玩家生命值
        if p.hp <= 0:
            self.controller.go_to_scene("game_over_scene")

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
        msg = logic.purchase_item(index, self.controller.player)
        self.controller.door_scene._generate_doors()  # Ensure doors regenerate
        self.controller.go_to_scene("door_scene")
        self.controller.add_message(msg + "\n离开商店, 回到门场景")

class UseItemScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.active_items = []

    def on_enter(self):
        p = self.controller.player
        # 筛选库存中主动使用的道具，排除复活卷轴（active=False）
        self.active_items = [item for item in p.inventory if item.get("active", False)]
        if not self.active_items:
            self.controller.add_message("你没有可使用的道具")
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

class ShopLogic:
    def __init__(self):
        self.shop_items = []

    def generate_items(self, player):
        self.shop_items = []
        if player.gold == 0:
            return
        # 移除未使用的has_neg变量
        # 每个元组：名称, 类型, 效果值, 基准价格, 是否主动使用
        possible = [
            ("普通治疗药水", "heal", 10, 10, False),
            ("高级治疗药水", "heal", 20, 20, False),
            ("超高级治疗药水", "heal", 30, 30, False),
            ("普通装备", "weapon", 2, 15, False),
            ("稀有装备", "weapon", 5, 30, False),
            ("复活卷轴", "revive", 1, 25, False),
            ("减伤卷轴", "damage_reduction", 2, 15, False),
            ("攻击力增益卷轴", "atk_up", 5, 20, False),
            ("恢复卷轴", "healing_scroll", 0, 30, False),
            ("免疫卷轴", "immune", 0, 25, False),
            ("飞锤", "飞锤", 0, 20, True),
            ("结界", "结界", 0, 20, True),
            ("巨大卷轴", "巨大卷轴", 0, 20, True),
        ]
        # 如果金币不足10，则只显示低价物品或增益类（注意：主动使用的物品仍保留）
        if player.gold < 10:
            possible = [item for item in possible if item[3] <= 10 or item[1] in ("atk_up", "damage_reduction", "immune")]
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
            return f"你花费 {cost} 金币, 购买了 {n}, 已存入道具栏!"
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
                           self.game_config.START_PLAYER_GOLD)
        
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
      "shop_items": shop_data,
      "button_texts": scn.get_button_texts() if scn else ["", "", ""]
    }
    if scn_name == "UseItemScene":
        state["active_items"] = scn.active_items
    
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