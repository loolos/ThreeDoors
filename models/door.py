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
                # 使用怪物的真实等级和类型，随机选择提示
                tier_hints = cls.monster_tier_hints.get(monster.tier, ["危险的气息..."])
                type_hints = cls.monster_type_hints.get(monster.name, ["未知生物的声响..."])
                tier_hint = random.choice(tier_hints)
                type_hint = random.choice(type_hints)
                return f"{combo} {tier_hint} {type_hint}"
            else:
                # 使用随机的等级和类型
                tier_hints = cls.monster_tier_hints[1]
                type_hints = list(cls.monster_type_hints.values())[0]
                tier_hint = random.choice(tier_hints)
                type_hint = random.choice(type_hints)
                return f"{combo} {tier_hint} {type_hint}"
        elif fake_event == "monster":
            # 如果虚假门是怪物门
            combo = cls.combo_hints.get(frozenset({real_event, "monster"}))
            if not combo:
                combo = cls.default_hints[real_event]
            combo = random.choice(combo)
            
            # 生成一个随机的怪物提示
            fake_monster = get_random_monster(current_round=1)  # 使用默认回合数
            tier_hints = cls.monster_tier_hints.get(fake_monster.tier, ["危险的气息..."])
            type_hints = cls.monster_type_hints.get(fake_monster.name, ["未知生物的声响..."])
            tier_hint = random.choice(tier_hints)
            type_hint = random.choice(type_hints)
            return f"{combo} {tier_hint} {type_hint}"
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
            return monster_desc
        elif self.event == "trap":
            # 根据回合数和玩家状态决定陷阱效果
            current_round = controller.round_count
            
            # 计算基础伤害，回合数越高伤害越高
            base_damage = random.randint(5, 15)
            damage = base_damage + (current_round // 5) * 2
            
            # 造成伤害
            actual_dmg = player.take_damage(damage)
            controller.add_message(f"你触发了陷阱，受到 {actual_dmg} 点伤害!")
            
            # 30%概率损失金币
            if random.random() < 0.3:
                # 计算金币损失，回合数越高损失越多
                base_loss = random.randint(5, 15)  # 降低基础损失范围
                loss = base_loss + (current_round // 5) * 3  # 降低每5回合的额外损失
                player.gold = max(0, player.gold - loss)
                controller.add_message(f"你损失了 {loss} 金币!")
            
            # 检查是否死亡
            if player.hp <= 0:
                revived = player.try_revive()
                if revived:
                    controller.add_message("复活卷轴救了你(HP=1)!")
                else:
                    controller.add_message("你被陷阱击倒, 英勇牺牲!")
                    controller.go_to_scene("game_over_scene")
            
            return "你触发了陷阱!"
        elif self.event == "reward":
            # 根据回合数决定奖励
            current_round = controller.round_count
            
            # 计算金币奖励，回合数越高奖励越多
            base_gold = random.randint(10, 30)
            gold = base_gold + (current_round // 5) * 5
            player.gold += gold
            
            # 30%概率获得额外奖励
            extra_reward = ""
            if random.random() < 0.3:
                # 随机选择一种额外奖励
                reward_type = random.choice(["heal", "weapon", "armor"])
                if reward_type == "heal":
                    heal_amt = random.randint(5, 15)
                    player.heal(heal_amt)
                    extra_reward = f"你恢复了 {heal_amt} 点生命!"
                elif reward_type == "weapon":
                    atk_boost = random.randint(2, 5)
                    player.atk += atk_boost
                    player.base_atk += atk_boost
                    extra_reward = f"你的攻击力提升了 {atk_boost} 点!"
                elif reward_type == "armor":
                    hp_boost = random.randint(5, 10)
                    player.hp += hp_boost
                    extra_reward = f"你的生命值提升了 {hp_boost} 点!"
            
            return f"你获得了 {gold} 金币! {extra_reward}"
        elif self.event == "shop":
            # 进入商店
            controller.go_to_scene("shop_scene")
            return "你进入了商店!"
        else:
            return "未知事件!" 