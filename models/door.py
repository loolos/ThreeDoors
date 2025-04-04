import random
from .monster import get_random_monster

class Door:
    # 基础组合提示
    combo_hints = {
        frozenset({"monster", "reward"}): [
            "野兽的咆哮中夹杂着金币的叮当声",
            "危险的气息中闪烁着宝物的光芒",
            "黑暗中似乎有宝藏，但似乎也有危险",
            "猛兽的嘶吼与财宝的诱惑交织",
            "危机与机遇并存"
        ],
        frozenset({"monster", "shop"}): [
            "商人的吆喝声中藏着野兽的咆哮",
            "交易与危险并存",
            "商人的声音中似乎藏着威胁",
            "猛兽的怒吼与商人的叫卖交织",
            "买卖与战斗并存"
        ],
        frozenset({"monster", "trap"}): [
            "危险的气息扑面而来",
            "猛兽与陷阱的双重威胁",
            "黑暗中藏着双重危险",
            "野兽的咆哮与机关的咔嗒声交织",
            "危机四伏"
        ],
        frozenset({"trap", "reward"}): [
            "机关与宝藏并存",
            "陷阱中似乎藏着宝物",
            "危险与机遇并存",
            "机关的咔嗒声中夹杂着金币的叮当声",
            "危机与财富并存"
        ],
        frozenset({"trap", "shop"}): [
            "商人的声音中似乎藏着机关",
            "交易与陷阱并存",
            "买卖声中似乎有机关的咔嗒声",
            "商人的吆喝与机关的咔嗒声交织",
            "买卖与危险并存"
        ],
        frozenset({"shop", "reward"}): [
            "商人的吆喝声中夹杂着金币的叮当声",
            "交易与财富并存",
            "买卖声中似乎有宝物的光芒",
            "商人的声音与财宝的诱惑交织",
            "买卖与机遇并存"
        ]
    }
        
    # 缺省提示语
    default_hints = {
        "monster": [
            "黑暗中似乎有什么在移动...",
            "危险的气息扑面而来...",
            "有什么东西在等待着你...",
            "空气中弥漫着紧张的气氛...",
            "似乎有什么可怕的存在..."
        ],
        "trap": [
            "这里的气氛有些诡异...",
            "空气中弥漫着危险的气息...",
            "似乎有什么机关在等待...",
            "这里的一切都显得那么可疑...",
            "黑暗中似乎藏着什么..."
        ],
        "reward": [
            "金光闪闪，似乎有什么宝物...",
            "空气中飘来一丝财富的气息...",
            "这里似乎藏着什么好东西...",
            "金光若隐若现，引人遐想...",
            "似乎有什么宝物在等待..."
        ],
        "shop": [
            "商人的吆喝声传来...",
            "空气中飘来交易的气息...",
            "这里似乎有商人在此...",
            "商人的声音若隐若现...",
            "似乎有什么人在做买卖..."
        ]
    }

    @classmethod
    def generate_monster_door(cls, monster):
        """生成怪物门"""
        # 创建 Monster 对象
        monster_obj = monster
        event_details = {
            "monster": {
                "name": monster.name,
                "hp": monster.hp,
                "atk": monster.atk,
                "tier": monster.tier
            }
        }
        return cls("monster", event_details, monster_obj)

    @classmethod
    def generate_reward_door(cls):
        """生成奖励门"""
        # 随机决定奖励类型
        reward_type = random.random()
        if reward_type < 0.4:  # 40%概率获得金币
            g = random.randint(5, 15)
            event_details = {
                "reward": {"type": "gold", "value": g}
            }
        elif reward_type < 0.7:  # 30%概率获得装备
            boost = random.randint(1, 10)
            event_details = {
                "reward": {"type": "equip", "value": boost}
            }
        else:  # 30%概率获得状态卷轴
            scroll_type = random.choice([
                ("healing_scroll", "恢复卷轴", random.randint(10, 20)),
                ("damage_reduction", "减伤卷轴", random.randint(10, 20)),  # 随机持续10-20回合
                ("atk_up", "攻击力增益卷轴", random.randint(10, 20)),
            ])
            event_details = {
                "reward": {
                    "type": "scroll", 
                    "scroll_type": scroll_type[0], 
                    "duration": scroll_type[2],
                    "value": random.randint(10, 20) if scroll_type[0] == "atk_up" else None  # 随机增加10-20攻击力
                }
            }
        return cls("reward", event_details)

    @classmethod
    def generate_shop_door(cls):
        """生成商店门"""
        return cls("shop")

    def __init__(self, event, event_details=None, monster=None):
        self.event = event
        self.event_details = event_details or {}
        self.monster = monster  # 保存monster对象
        # 根据事件类型生成提示
        if event == "monster":
            self.hint = self.generate_mixed_hints(event, monster)
        else:
            self.hint = self.generate_mixed_hints(event)

    @classmethod
    def generate_mixed_hints(cls, real_event, monster=None):
        """生成混淆的提示，基于真实门和虚假门的类型"""
        # 获取所有可能的门类型
        all_events = ["monster", "trap", "reward", "shop"]
        
        # 生成一个虚假的门类型（与真实门不同）
        fake_event = random.choice([e for e in all_events if e != real_event])
        
        # 根据真实门和虚假门的类型生成提示
        if real_event == "monster":
            # 如果真实门是怪物门
            combo = cls.combo_hints.get(frozenset({real_event, fake_event}))
            if not combo:
                combo = cls.default_hints["monster"]
            combo = random.choice(combo)
            
            if monster:
                # 直接从monster对象获取提示
                return f"{combo} {monster.tier_hint} {monster.type_hint}"
            else:
                # 使用随机的等级和类型
                fake_monster = get_random_monster(current_round=1)  # 使用默认回合数
                return f"{combo} {fake_monster.tier_hint} {fake_monster.type_hint}"
        elif fake_event == "monster":
            # 如果虚假门是怪物门
            combo = cls.combo_hints.get(frozenset({real_event, "monster"}))
            if not combo:
                combo = cls.default_hints[real_event]
            combo = random.choice(combo)
            
            # 生成一个随机的怪物提示
            fake_monster = get_random_monster(current_round=1)  # 使用默认回合数
            return f"{combo} {fake_monster.tier_hint} {fake_monster.type_hint}"
        else:
            # 如果都不是怪物门，使用对应的组合提示
            combo = cls.combo_hints.get(frozenset({real_event, fake_event}))
            if not combo:
                combo = cls.default_hints[real_event]
            return random.choice(combo)

    @classmethod
    def generate_trap_door(cls):
        """生成陷阱门"""
        dmg = random.randint(5, 10)
        event_details = {
            "trap": {"damage": dmg}
        }
        return cls("trap", event_details)

    def enter(self, player, controller):
        """进入门并处理事件"""
        if self.event == "monster":
            # 使用传入的monster对象
            monster = self.monster
            monster_desc = f"你遇到了 {monster.name} (HP: {monster.hp}, ATK: {monster.atk}, Tier: {monster.tier})"
            if monster.has_status("stun"):
                monster_desc += f" [晕眩{monster.statuses['stun']['duration']}回合]"
            controller.current_monster = monster
            controller.go_to_scene("battle_scene")
            controller.add_message(monster_desc)
        elif self.event == "trap":
            # 根据回合数和玩家状态决定陷阱效果
            current_round = controller.round_count
            
            # 计算基础伤害，回合数越高伤害越高
            base_damage = random.randint(5, 15)
            damage = base_damage + (current_round // 5) * 2
            
            # 添加陷阱消息
            controller.add_message("你触发了陷阱!")
            
            # 造成伤害
            player.take_damage(damage)
            
            # 30%概率损失金币
            if random.random() < 0.3:
                # 计算金币损失，回合数越高损失越多
                base_loss = random.randint(5, 15)  # 降低基础损失范围
                loss = base_loss + (current_round // 5) * 3  # 降低每5回合的额外损失
                player.gold = max(0, player.gold - loss)
                controller.add_message(f"你损失了 {loss} 金币!")
        elif self.event == "reward":
            # 根据回合数决定奖励
            current_round = controller.round_count
            
            # 计算金币奖励，回合数越高奖励越多
            base_gold = random.randint(10, 30)
            gold = base_gold + (current_round // 5) * 5
            player.gold += gold
            
            # 30%概率获得额外奖励
            if random.random() < 0.3:
                # 随机选择一种额外奖励
                reward_type = random.choice(["heal", "weapon", "armor"])
                if reward_type == "heal":
                    heal_amt = random.randint(5, 15)
                    player.heal(heal_amt)
                    controller.add_message(f"你获得了 {gold} 金币! 你恢复了 {heal_amt} 点生命!")
                elif reward_type == "weapon":
                    atk_boost = random.randint(2, 5)
                    player.atk += atk_boost
                    player.base_atk += atk_boost
                    controller.add_message(f"你获得了 {gold} 金币! 你的攻击力提升了 {atk_boost} 点!")
                elif reward_type == "armor":
                    hp_boost = random.randint(5, 10)
                    player.hp += hp_boost
                    controller.add_message(f"你获得了 {gold} 金币! 你的生命值提升了 {hp_boost} 点!")
            else:
                controller.add_message(f"你获得了 {gold} 金币!")
        elif self.event == "shop":
            # 进入商店
            controller.go_to_scene("shop_scene")
            controller.add_message("你进入了商店!")
        else:
            controller.add_message("未知事件!") 