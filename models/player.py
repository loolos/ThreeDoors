from models.door import Door
from models.monster import Monster, get_random_monster
from .status_effect import StatusEffect
import random

class Player:
    def __init__(self, name="勇士", hp=20, atk=5, gold=0, controller=None):
        self.name = name
        self.hp = hp
        self.base_atk = atk
        self.atk = atk
        self.gold = gold
        self.statuses = {}  # 如 {"poison": {"duration": 3}, "weak": {"duration": 2}, ...}
        self.inventory = []  # 最多可存10个道具，每个道具为字典
        self.controller = controller  # 添加controller引用

    def take_damage(self, dmg):
        """受到伤害，如果有减伤状态则减少75%伤害，返回实际受到的伤害"""
        # 如果有减伤状态，减少75%伤害
        if "damage_reduction" in self.statuses:
            original_dmg = dmg
            dmg = max(1, int(dmg * 0.25))  # 减少75%伤害
            if self.controller:
                self.controller.add_message(f"一部分伤害被减伤卷轴挡掉了！（原伤害 {original_dmg}，实际伤害 {dmg}）")
        
        # 显示伤害消息
        if self.controller:
            self.controller.add_message(f"你受到了 {dmg} 点伤害!")
        
        self.hp -= dmg
        
        # 检查是否死亡
        if self.hp <= 0:
            # 尝试使用复活卷轴
            revived = self.try_revive()
            if self.controller:
                if revived:
                    self.controller.add_message("复活卷轴救了你(HP=1)!")
                else:
                    self.controller.add_message("你被怪物击倒, 英勇牺牲!")
                    # 立即切换到GameOverScene
                    self.controller.scene_manager.go_to("game_over_scene")
        
        return dmg

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
                if self.controller:
                    self.hp = self.controller.game_config.START_PLAYER_HP
                else:
                    self.hp = 20  # 默认值
                return True
        return False

    def is_stunned(self):
        """检查玩家是否处于晕眩状态"""
        return "stun" in self.statuses and self.statuses["stun"]["duration"] > 0

    def attack(self, target):
        """玩家攻击目标"""
        # 检查是否晕眩
        if self.is_stunned():
            if self.controller:
                self.controller.add_message("你处于眩晕状态, 无法行动!")
            return False
            
        # 应用战斗状态效果
        self.apply_turn_effects(is_battle_turn=True)
        
        # 计算伤害
        dmg = max(1, self.atk - random.randint(0, 1))
        
        # 造成伤害
        target.take_damage(dmg)
        if self.controller:
            self.controller.add_message(f"你攻击 {target.name} 造成 {dmg} 点伤害.")
        
        # 检查目标是否死亡
        if target.hp <= 0:
            if self.controller:
                self.controller.add_message(f"你击败了 {target.name}!")
            return True
        
        return False

    def try_escape(self, monster):
        """尝试逃跑"""
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
            if self.controller:
                self.controller.add_message("你成功逃脱了!")
            return True
        else:
            # 逃跑失败，受到伤害
            mdmg = max(1, monster.atk - random.randint(0, 1))
            actual_dmg = self.take_damage(mdmg)
            if self.controller:
                self.controller.add_message(f"逃跑失败，{monster.name} 反击造成 {actual_dmg} 点伤害!")
            return False

    def apply_turn_effects(self, is_battle_turn=False):
        """处理回合效果，统一处理战斗和冒险回合"""
        # 处理基础效果（对战斗和冒险回合都生效）
        self._apply_base_effects()
        
        # 处理特殊效果
        if not is_battle_turn:
            self._apply_special_adventure_effects()
            
        # 更新状态持续时间
        self._update_status_durations(is_battle_turn)
    
    def _apply_base_effects(self):
        """处理基础效果（对战斗和冒险回合通用）"""
        # 检查免疫状态
        immune = ("immune" in self.statuses and self.statuses["immune"]["duration"] > 0)
        
        # 处理中毒效果
        if "poison" in self.statuses and self.statuses["poison"]["duration"] > 0 and not immune:
            poison_damage = max(1, int(self.hp * 0.1))  # 计算10%生命值的伤害，最小为1
            self.hp -= poison_damage
            if self.controller:
                self.controller.add_message(f"中毒效果造成 {poison_damage} 点伤害！")
            
        # 重置并计算攻击力
        self.atk = self.base_atk
        
        # 处理攻击力相关效果
        if "atk_multiplier" in self.statuses and self.statuses["atk_multiplier"]["duration"] > 0:
            self.atk *= self.statuses["atk_multiplier"]["value"]
        
        if "weak" in self.statuses and self.statuses["weak"]["duration"] > 0 and not immune:
            self.atk = max(1, self.atk - 2)
            
        if "atk_up" in self.statuses and self.statuses["atk_up"]["duration"] > 0:
            if "value" in self.statuses["atk_up"]:
                self.atk += self.statuses["atk_up"]["value"]
    
    def _apply_special_adventure_effects(self):
        """处理冒险回合特有的效果"""
        if "healing_scroll" in self.statuses and self.statuses["healing_scroll"]["duration"] > 0:
            heal_amount = random.randint(1, 5)
            self.heal(heal_amount)
            print(f"恢复卷轴生效，恢复 {heal_amount} 点生命！")
    
    def _update_status_durations(self, is_battle_turn):
        """更新状态持续时间"""
        expired = []
        for st in self.statuses:
            # 根据回合类型决定要处理的状态
            if (is_battle_turn and StatusEffect.is_battle_status(st)) or \
               (not is_battle_turn and StatusEffect.is_adventure_status(st)):
                self.statuses[st]["duration"] -= 1
                if self.statuses[st]["duration"] <= 0:
                    expired.append(st)
        
        # 移除过期状态
        for st in expired:
            del self.statuses[st]

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
                # 如果没有指定value值，则使用随机的10-20之间的提升值
                atk_boost = value if value is not None else random.randint(10, 20)
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
            if self.controller:
                self.hp = self.controller.game_config.START_PLAYER_HP
            else:
                self.hp = 20  # 默认值
            return True
        return False 