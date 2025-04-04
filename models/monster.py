import random

class Monster:
    # 怪物类型定义
    MONSTER_TYPES = {
        1: [  # 初级怪物
            ("小哥布林", 10, 2),      # 弱小但数量多的生物
            ("史莱姆", 12, 1),        # 最基础的怪物
            ("蝙蝠", 8, 3),          # 速度快但脆弱
            ("野狼", 11, 2),         # 普通的野兽
            ("食人花", 13, 1),       # 植物怪物
            ("小蜥蜴人", 9, 3),      # 爬行类人生物
            ("土匪", 10, 2),         # 人类敌人
            ("小鸟妖", 9, 3)         # 飞行生物
        ],
        2: [  # 精英怪物
            ("半人马", 20, 4),       # 神话生物
            ("牛头人", 24, 3),       # 力量型怪物
            ("树人", 28, 2),        # 自然生物
            ("狼人", 22, 4),        # 诅咒生物
            ("食人魔", 25, 3),      # 巨型生物
            ("美杜莎", 18, 5),      # 神话生物
            ("巨型蝎子", 21, 4),    # 节肢生物
            ("幽灵", 16, 6)         # 灵体生物
        ],
        3: [  # 首领级怪物
            ("巨魔酋长", 32, 6),    # 部落首领
            ("九头蛇", 36, 5),      # 传说生物
            ("石像鬼", 28, 8),      # 魔法造物
            ("吸血鬼", 30, 7),      # 不死生物
            ("独眼巨人", 38, 5),    # 神话巨人
            ("精灵法师", 26, 9),    # 魔法使用者
            ("地狱犬", 34, 6),      # 地狱生物
            ("巨型蜘蛛", 33, 7)     # 巨型节肢生物
        ],
        4: [  # 传说级怪物
            ("青铜龙", 45, 8),      # 金属龙
            ("死亡骑士", 40, 10),   # 不死战士
            ("冰霜巨人", 50, 7),    # 元素巨人
            ("暗影刺客", 35, 12),   # 暗影生物
            ("雷鸟", 42, 9),        # 天空生物
            ("海妖", 38, 11),       # 水生生物
            ("地穴领主", 44, 9),    # 地下生物
            ("炎魔", 48, 8)         # 火焰生物
        ],
        5: [  # 史诗级怪物
            ("白银龙", 55, 11),     # 高级金属龙
            ("利维坦", 65, 9),      # 远古巨兽
            ("凤凰", 50, 13),       # 神话鸟类
            ("泰坦", 60, 10),       # 上古巨人
            ("冥界使者", 52, 12),   # 冥界生物
            ("天使", 58, 11),       # 天界生物
            ("混沌巫师", 48, 14),   # 混沌法师
            ("远古守卫", 62, 10)    # 远古生物
        ],
        6: [  # 神话级怪物
            ("黄金龙", 70, 13),     # 最强金属龙
            ("克拉肯", 80, 11),     # 深海巨兽
            ("天启骑士", 65, 15),   # 末日使者
            ("世界之蛇", 75, 12),   # 世界级巨兽
            ("深渊领主", 68, 14),   # 深渊生物
            ("创世神官", 72, 13),   # 神级生物
            ("混沌之主", 60, 17),   # 混沌生物
            ("永恒守护者", 85, 12)  # 永恒生物
        ]
    }

    # 怪物等级提示
    MONSTER_TIER_HINTS = {
        1: [
            "一股微弱的气息...",
            "似乎不是很危险...",
            "这个对手看起来很弱小...",
            "你感觉充满信心...",
            "这应该不难对付..."
        ],
        2: [
            "要小心应对...",
            "这个对手有点棘手...",
            "需要认真对待...",
            "不能掉以轻心...",
            "有一定的挑战性..."
        ],
        3: [
            "一股强大的气息...",
            "这个对手很危险...",
            "需要全力以赴...",
            "你感到一丝压力...",
            "这将是一场恶战..."
        ],
        4: [
            "极其危险的气息...",
            "这个对手实力非凡...",
            "你感到强大的压迫感...",
            "这是个可怕的对手...",
            "需要慎重应对..."
        ],
        5: [
            "史诗级的威压...",
            "令人窒息的气场...",
            "传说中的存在...",
            "你感到一阵战栗...",
            "这将是一场苦战..."
        ],
        6: [
            "神话级的存在...",
            "令人绝望的压迫感...",
            "你面对的是传说...",
            "空气都在颤抖...",
            "这是最强大的对手..."
        ]
    }

    # 怪物类型提示
    MONSTER_TYPE_HINTS = {
        "小哥布林": ["传来阵阵怪笑声...", "空气中有股怪味..."],
        "史莱姆": ["地上有粘液的痕迹...", "空气很潮湿..."],
        "蝙蝠": ["听到翅膀扇动的声音...", "黑暗中有影子晃动..."],
        "野狼": ["听到低沉的嚎叫...", "空气中有野兽的气味..."],
        "食人花": ["空气中有花香...", "地上有奇怪的藤蔓..."],
        "小蜥蜴人": ["地上有爬行的痕迹...", "听到沙沙的声音..."],
        "土匪": ["有人类活动的迹象...", "似乎有人在窃窃私语..."],
        "小鸟妖": ["空中有羽毛飘落...", "听到奇怪的鸟鸣..."],
        
        "半人马": ["听到马蹄声...", "空气中有野性的气息..."],
        "牛头人": ["地面在轻微震动...", "听到沉重的喘息声..."],
        "树人": ["空气中弥漫着木香...", "听到树枝晃动的声音..."],
        "狼人": ["月光下有影子晃动...", "听到野兽的低吼..."],
        "食人魔": ["空气中有腐臭味...", "地面在震动..."],
        "美杜莎": ["空气异常寒冷...", "听到蛇的嘶嘶声..."],
        "巨型蝎子": ["地上有奇怪的痕迹...", "空气中有毒素的气息..."],
        "幽灵": ["温度突然降低...", "有阴森的笑声..."],
        
        "巨魔酋长": ["听到野蛮的呐喊...", "空气中有篝火的味道..."],
        "九头蛇": ["空气中有硫磺的味道...", "听到多重的嘶嘶声..."],
        "石像鬼": ["石头在移动...", "空气中有魔法的波动..."],
        "吸血鬼": ["空气中有血腥味...", "黑暗中有红色的眼睛..."],
        "独眼巨人": ["地面在剧烈震动...", "听到巨大的脚步声..."],
        "精灵法师": ["空气中有魔法的波动...", "能感受到强大的魔力..."],
        "地狱犬": ["空气中有硫磺味...", "听到恶魔的吠叫..."],
        "巨型蜘蛛": ["到处都是蛛网...", "空气中有毒素的气息..."],
        
        "青铜龙": ["空气中有金属的气息...", "听到龙的咆哮..."],
        "死亡骑士": ["空气中有死亡的气息...", "听到铠甲的碰撞声..."],
        "冰霜巨人": ["温度急剧下降...", "空气中有冰晶飘动..."],
        "暗影刺客": ["黑暗中有影子移动...", "感受到杀意..."],
        "雷鸟": ["空气中有电流...", "听到雷鸣..."],
        "海妖": ["空气异常潮湿...", "听到海浪的声音..."],
        "地穴领主": ["地下传来震动...", "空气中有腐朽的气息..."],
        "炎魔": ["温度急剧升高...", "空气中有硫磺味..."],
        
        "白银龙": ["空气中有金属光泽...", "听到威严的龙吟..."],
        "利维坦": ["空气中有海洋的气息...", "感受到远古的威压..."],
        "凤凰": ["温度异常炎热...", "空气中有不死鸟的气息..."],
        "泰坦": ["大地在颤抖...", "感受到上古的威压..."],
        "冥界使者": ["空气中有死亡的气息...", "感受到冥界的力量..."],
        "天使": ["空气中有圣光...", "听到天界的圣歌..."],
        "混沌巫师": ["空气扭曲...", "感受到混沌的力量..."],
        "远古守卫": ["空气中有远古的气息...", "感受到守护的力量..."],
        
        "黄金龙": ["空气中有神圣的光芒...", "感受到龙王的威压..."],
        "克拉肯": ["空气中有深海的气息...", "感受到海怪的威压..."],
        "天启骑士": ["空气中有末日的气息...", "感受到天启的力量..."],
        "世界之蛇": ["空气在扭曲...", "感受到世界级的威压..."],
        "深渊领主": ["空气中有深渊的气息...", "感受到深渊的召唤..."],
        "创世神官": ["空气中有创世的力量...", "感受到神圣的威压..."],
        "混沌之主": ["现实在扭曲...", "感受到混沌的威能..."],
        "永恒守护者": ["时空在震动...", "感受到永恒的力量..."]
    }

    def __init__(self, name=None, hp=None, atk=None, tier=1):
        if name is None or hp is None or atk is None:
            # 随机选择对应等级的怪物类型
            monster_type = random.choice(self.MONSTER_TYPES[tier])
            self.name = monster_type[0]
            self.hp = monster_type[1]
            self.atk = monster_type[2]
        else:
            self.name = name
            self.hp = hp
            self.atk = atk
        self.tier = tier
        self.statuses = {}  # 使用状态系统来管理怪物的状态效果
        self.loot = self._generate_loot()  # 生成掉落物品
        
        # 生成怪物提示
        self.tier_hint = random.choice(self.MONSTER_TIER_HINTS[self.tier])  # 等级提示
        # 如果是测试怪物，使用默认提示
        if self.name.startswith("测试怪物"):
            self.type_hint = "未知生物的声响..."
        else:
            self.type_hint = random.choice(self.MONSTER_TYPE_HINTS[self.name])  # 类型提示

    def _generate_loot(self):
        """生成怪物的掉落物品"""
        loot = []
        # 基础金币掉落，随怪物等级提升
        base_gold = random.randint(5, 15) * self.tier
        loot.append(("gold", base_gold))
        
        # 根据怪物等级决定额外掉落
        if self.tier >= 2:
            # Tier 2及以上怪物有50%概率获得装备
            if random.random() < 0.5:
                equip_boost = 2 * self.tier  # 装备加成固定为2倍等级
                loot.append(("equip", equip_boost))
            
            # Tier 2及以上怪物有30%概率获得卷轴
            if random.random() < 0.3:
                scroll_type = random.choice([
                    ("healing_scroll", "恢复卷轴", 5 * self.tier),  # 恢复值随等级提升
                    ("damage_reduction", "减伤卷轴", 10 * self.tier),  # 减伤值随等级提升
                    ("atk_up", "攻击力增益卷轴", random.randint(self.tier+5, self.tier*3+10)),  # 攻击力加成随机10-20
                ])
                loot.append(("scroll", scroll_type))
        
        return loot

    def get_loot(self):
        """获取怪物的掉落物品"""
        return self.loot

    def process_loot(self, player):
        """处理怪物的掉落物品，应用到玩家身上"""
        for item_type, value in self.loot:
            if item_type == "gold":
                player.add_gold(value)
                if hasattr(player, 'controller') and player.controller:
                    player.controller.add_message(f"获得 {value} 金币")
            elif item_type == "equip":
                player.atk += value
                if hasattr(player, 'controller') and player.controller:
                    player.controller.add_message(f"获得装备，攻击力提升 {value} 点")
            elif item_type == "scroll":
                scroll_name, scroll_desc, scroll_value = value
                effect_msg = player.apply_item_effect(scroll_name, scroll_value)
                if hasattr(player, 'controller') and player.controller:
                    player.controller.add_message(f"获得 {scroll_desc}，{effect_msg}")

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

    def attack(self, target):
        """怪物攻击目标"""
        # 检查是否晕眩
        if self.has_status("stun"):
            self.update_statuses()
            if hasattr(target, 'controller') and target.controller:
                target.controller.add_message(f"{self.name} 被晕眩，无法反击!")
            return False

        # 检查目标是否有结界
        if "barrier" in target.statuses and target.statuses["barrier"]["duration"] > 0:
            if hasattr(target, 'controller') and target.controller:
                target.controller.add_message(f"{self.name} 的攻击被结界挡住了!")
            return False

        # 计算伤害
        mdmg = max(1, self.atk - random.randint(0, 1))
            
        # 造成伤害
        actual_dmg = target.take_damage(mdmg)
        if hasattr(target, 'controller') and target.controller:
            target.controller.add_message(f"{self.name} 反击造成 {actual_dmg} 点伤害.")

        # 检查目标是否死亡
        if target.hp <= 0:
            revived = target.try_revive()
            if hasattr(target, 'controller') and target.controller:
                if revived:
                    target.controller.add_message("复活卷轴救了你(HP=1)!")
                else:
                    target.controller.add_message("你被怪物击倒, 英勇牺牲!")

        # 较强怪物可能附带负面效果
        # 根据怪物等级调整负面效果概率
        effect_probability = 0.1  # 基础概率10%
        if self.tier >= 2:
            effect_probability += 0.1  # Tier 2怪物增加10%概率
        if self.tier >= 3:
            effect_probability += 0.1  # Tier 3怪物再增加10%概率
        if self.tier >= 4:
            effect_probability += 0.1  # Tier 4怪物再增加10%概率
            
        if random.random() < effect_probability:
            effect = random.choice(["weak", "poison", "stun"])
            duration = random.randint(1, 2)
            
            # 检查目标是否有免疫效果
            if hasattr(target, 'statuses') and "immune" in target.statuses and target.statuses["immune"]["duration"] > 0:
                if hasattr(target, 'controller') and target.controller:
                    target.controller.add_message(f"免疫效果保护了你免受 {effect} 效果!")
            else:
                target.statuses[effect] = {"duration": duration}
                if hasattr(target, 'controller') and target.controller:
                    target.controller.add_message(f"{self.name} 附带 {effect} 效果 ({duration}回合)!")

        return False

    def get_hints(self):
        """获取怪物的提示信息"""
        return [self.tier_hint, self.type_hint]

def get_random_monster(max_tier=None, current_round=None):
    """根据当前回合数生成随机怪物"""
    # 根据回合数限制怪物等级
    if max_tier is None and current_round is not None:
        if current_round <= 5:
            max_tier = 1  # 前5回合只出现Tier 1怪物
        elif current_round <= 10:
            max_tier = 2  # 6-10回合可能出现Tier 2怪物
        elif current_round <= 15:
            max_tier = 3  # 11-15回合可能出现Tier 3怪物
        elif current_round <= 20:
            max_tier = 4  # 16-20回合可能出现Tier 4怪物
        elif current_round <= 25:
            max_tier = 5  # 21-25回合可能出现Tier 5怪物
        else:
            max_tier = 6  # 25回合后可能出现所有怪物
    elif max_tier is None:
        max_tier = 1  # 默认使用Tier 1
    
    # 从对应等级的怪物池中随机选择
    return Monster(tier=random.randint(1, max_tier)) 