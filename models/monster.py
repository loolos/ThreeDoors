from models.items import Item, ItemType, Equipment, HealingScroll, DamageReductionScroll, AttackUpScroll, create_random_item
from typing import Optional, TYPE_CHECKING
from models.game_config import GameConfig
from models import items
from .status import Status, StatusName, CreateStatusByName
if TYPE_CHECKING:
    from models.player import Player

import random

class Monster:
    # 怪物类型定义
    MONSTER_TYPES = {
        1: [  # 初级怪物
            ("小哥布林", 15, 3),      # 弱小但数量多的生物
            ("史莱姆", 18, 2),        # 最基础的怪物
            ("蝙蝠", 12, 4),          # 速度快但脆弱
            ("野狼", 16, 3),         # 普通的野兽
            ("食人花", 20, 2),       # 植物怪物
            ("小蜥蜴人", 14, 4),      # 爬行类人生物
            ("土匪", 15, 3),         # 人类敌人
            ("小鸟妖", 14, 4)         # 飞行生物
        ],
        2: [  # 精英怪物
            ("半人马", 30, 6),       # 神话生物
            ("牛头人", 36, 5),       # 力量型怪物
            ("树人", 42, 3),        # 自然生物
            ("狼人", 33, 6),        # 诅咒生物
            ("食人魔", 38, 5),      # 巨型生物
            ("美杜莎", 27, 7),      # 神话生物
            ("巨型蝎子", 32, 6),    # 节肢生物
            ("幽灵", 24, 9)         # 灵体生物
        ],
        3: [  # 首领级怪物
            ("巨魔酋长", 48, 9),    # 部落首领
            ("九头蛇", 54, 8),      # 传说生物
            ("石像鬼", 42, 12),      # 魔法造物
            ("吸血鬼", 45, 10),      # 不死生物
            ("独眼巨人", 57, 8),    # 神话巨人
            ("精灵法师", 39, 13),    # 魔法使用者
            ("地狱犬", 51, 9),      # 地狱生物
            ("巨型蜘蛛", 50, 10)     # 巨型节肢生物
        ],
        4: [  # 传说级怪物
            ("青铜龙", 68, 12),      # 金属龙
            ("死亡骑士", 60, 15),   # 不死战士
            ("冰霜巨人", 75, 10),    # 元素巨人
            ("暗影刺客", 53, 18),   # 暗影生物
            ("雷鸟", 63, 13),        # 天空生物
            ("海妖", 57, 16),       # 水生生物
            ("地穴领主", 66, 13),    # 地下生物
            ("炎魔", 72, 12)         # 火焰生物
        ],
        5: [  # 史诗级怪物
            ("白银龙", 83, 16),     # 高级金属龙
            ("利维坦", 98, 13),      # 远古巨兽
            ("凤凰", 75, 19),       # 神话鸟类
            ("泰坦", 90, 15),       # 上古巨人
            ("冥界使者", 78, 18),   # 冥界生物
            ("天使", 87, 16),       # 天界生物
            ("混沌巫师", 72, 21),   # 混沌法师
            ("远古守卫", 93, 15)    # 远古生物
        ],
        6: [  # 神话级怪物
            ("黄金龙", 105, 19),     # 最强金属龙
            ("克拉肯", 120, 16),     # 深海巨兽
            ("天启骑士", 98, 22),   # 末日使者
            ("世界之蛇", 113, 18),   # 世界级巨兽
            ("深渊领主", 102, 21),   # 深渊生物
            ("创世神官", 108, 19),   # 神级生物
            ("混沌之主", 90, 25),   # 混沌生物
            ("永恒守护者", 128, 18)  # 永恒生物
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

    def __init__(self, name=None, hp=None, atk=None, tier=1, effect_probability=None):
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
        
        # 设置效果概率
        self.effect_probability = effect_probability
        if self.effect_probability is None:
            # 根据怪物等级设置默认概率
            self.effect_probability = 0.1  # 基础概率10%
            if self.tier >= 2:
                self.effect_probability += 0.1  # Tier 2怪物增加10%概率
            if self.tier >= 3:
                self.effect_probability += 0.1  # Tier 3怪物再增加10%概率
            if self.tier >= 4:
                self.effect_probability += 0.1  # Tier 4怪物再增加10%概率
        
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
        gold_bag = items.GoldBag(f"{base_gold}金币", gold_amount=base_gold)
        loot.append(gold_bag)
        
        # 根据怪物等级决定额外掉落
        if self.tier >= 2:
            # Tier 2及以上怪物有50%概率获得装备
            if random.random() < 0.5:
                equip_boost = 2 * self.tier  # 装备加成固定为2倍等级
                item = Equipment(f"装备", atk_bonus=equip_boost, cost=equip_boost * 2)
                loot.append(item)
            
            # Tier 2及以上怪物有30%概率获得卷轴
            if random.random() < 0.3:
                scroll_value = random.randint(self.tier+5, self.tier*3+10)
                scroll_type = random.choice(["healing", "damage_reduction", "attack_up"])
                
                if scroll_type == "healing":
                    item = items.HealingScroll("恢复卷轴", cost=scroll_value * 2, duration=scroll_value)
                elif scroll_type == "damage_reduction":
                    item = items.DamageReductionScroll("减伤卷轴", cost=scroll_value * 2, duration=scroll_value)
                else:  # attack_up
                    item = items.AttackUpScroll("攻击力增益卷轴", atk_bonus=scroll_value, cost=scroll_value * 2, duration=scroll_value)
                    
                loot.append(item)
        
        return loot

    def get_loot(self):
        """获取怪物的掉落物品"""
        return self.loot

    def process_loot(self, player):
        """处理怪物的掉落物品，应用到玩家身上"""
        for item in self.loot:
            if item.acquire(player=player):
                if hasattr(player, 'controller') and player.controller:
                    player.controller.add_message(f"获得 {item.name}!")

    def take_damage(self, damage: int):
        """受到伤害"""
        # 检查是否有减伤效果
        if self.has_status(StatusName.DAMAGE_REDUCTION):
            damage = max(1, damage // 4)  # 减伤75%，至少受到1点伤害
            
        # 应用伤害
        self.hp -= damage
        
        # 检查是否死亡
        if self.hp <= 0:
            return True
        return False

    def heal(self, amount):
        """恢复生命值"""
        old_hp = self.hp
        self.hp += amount
        return self.hp - old_hp

    def apply_status(self, status: Status) -> None:
        """应用状态效果
        
        Args:
            status: 要应用的状态
        """
        # 检查状态是否在StatusName枚举中
        if not isinstance(status.enum, StatusName):
            return
            
        # 检查是否是负面状态且是否有免疫效果
        if status.enum in [StatusName.WEAK, StatusName.POISON, StatusName.STUN] and self.has_status(StatusName.IMMUNE):
            if hasattr(self, 'controller') and self.controller:
                # 获取状态名称的中文描述
                status_name_cn = status.enum.cn_name
                self.controller.add_message(f"{self.name}免疫了{status_name_cn}效果!")
            return
            
        if status.enum in self.statuses:
            # 如果已有相同状态，进行叠加
            self.statuses[status.enum].combine(status)
        else:
            # 如果是新状态，直接添加并启动效果
            self.statuses[status.enum] = status
            status.start_effect()  # 确保状态效果被正确启动

    def has_status(self, status_name: StatusName) -> bool:
        """检查是否具有指定状态
        
        Args:
            status_name: 要检查的状态名称
            
        Returns:
            如果具有该状态且持续时间大于0，返回 True
        """
        # 检查状态是否在StatusName枚举中
        if not isinstance(status_name, StatusName):
            return False
            
        return (status_name in self.statuses and 
                isinstance(self.statuses[status_name], Status) and 
                self.statuses[status_name].duration > 0)

    def get_status_duration(self, status_name: StatusName) -> int:
        """获取指定状态的剩余持续时间
        
        Args:
            status_name: 状态名称
            
        Returns:
            状态的剩余持续时间，如果状态不存在则返回0
        """
        if self.has_status(status_name):
            return self.statuses[status_name].duration
        return 0

    def attack(self, target):
        """怪物攻击目标"""
        # 检查是否晕眩
        if self.has_status(StatusName.STUN):
            if hasattr(target, 'controller') and target.controller:
                target.controller.add_message(f"{self.name} 处于眩晕状态，无法攻击！")
            return False

        # 检查目标是否有结界
        if target.has_status(StatusName.BARRIER):
            if hasattr(target, 'controller') and target.controller:
                target.controller.add_message(f"{self.name} 的攻击被结界挡住了!")
            return False

        # 计算伤害
        dmg = max(1, self.atk - random.randint(0, 1))
        
        # 如果有攻击力翻倍效果
        if self.has_status(StatusName.ATK_MULTIPLIER):
            dmg *= self.statuses[StatusName.ATK_MULTIPLIER].value
        # 造成伤害
        target.take_damage(dmg)

        # 使用设置的效果概率
        if random.random() < self.effect_probability:
            effect = random.choice([StatusName.WEAK, StatusName.POISON, StatusName.STUN])
            duration = random.randint(1, 2)
            
            # 应用状态
            status = effect.get_status_class(duration=duration, target=target)
            target.apply_status(status)
            if hasattr(target, 'controller') and target.controller:
                # 获取状态名称的中文描述
                status_name_cn = effect.cn_name
                target.controller.add_message(f"{self.name} 附带 {status_name_cn} 效果 ({duration}回合)!")

        return False

    def get_hints(self):
        """获取怪物的提示信息"""
        return [self.tier_hint, self.type_hint]

    def generate_loot(self) -> Optional[Item]:
        """生成掉落物品"""
        if random.random() < GameConfig.LOOT_CHANCE:
            return create_random_item()
        return None

    def drop_loot(self, player):
        """掉落物品"""
        # 掉落金币
        gold = random.randint(5, 15)
        player.gold += gold
        player.controller.add_message(f"获得 {gold} 金币!")
        
        # 30%概率掉落装备
        if random.random() < 0.3:
            value = random.randint(1, 3)
            item = Equipment(f"装备", atk_bonus=value, cost=value * 2)
            item.acquire(player=player)
            player.controller.add_message(f"获得 {item.name}!")
            
        # 30%概率掉落卷轴
        if random.random() < 0.3:
            scroll_value = random.randint(1, 3)
            scroll_type = random.choice(["healing", "damage_reduction", "attack_up"])
            
            if scroll_type == "healing":
                item = HealingScroll("恢复卷轴", cost=scroll_value * 2, duration=scroll_value)
            elif scroll_type == "damage_reduction":
                item = DamageReductionScroll("减伤卷轴", cost=scroll_value * 2, duration=scroll_value)
            else:  # attack_up
                item = AttackUpScroll("攻击力增益卷轴", atk_bonus=scroll_value, cost=scroll_value * 2, duration=scroll_value)
                
            item.acquire(player=player)
            player.controller.add_message(f"获得 {item.name}!")

    @staticmethod
    def get_random_item():
        """获取随机物品"""
        return create_random_item()

            
    def get_status_desc(self):
        """获取状态描述"""
        if not self.statuses:
            return "无"
            
        desc = []
        for status_enum, status in self.statuses.items():
            if isinstance(status, Status):
                # 获取状态名称的中文描述
                status_name_cn = status_enum.cn_name
                
                # 如果有特殊值（如攻击力翻倍的倍数），显示出来
                if status_enum == StatusName.ATK_MULTIPLIER and hasattr(status, 'value'):
                    desc.append(f"{status_name_cn}({status.duration}回合)x{status.value}")
                else:
                    desc.append(f"{status_name_cn}({status.duration}回合)")
                    
        return ", ".join(desc)

    def stun(self, duration: int) -> None:
        """使怪物晕眩"""
        self.statuses[StatusName.STUN] = StatusName.get_status_class(StatusName.STUN)(duration=duration, target=self)

    def battle_status_duration_pass(self) -> None:
        """处理战斗回合的状态持续时间"""
        expired = []
        for st in self.statuses:
            if self.statuses[st].duration_pass():
                expired.append(st)
        
        # 移除过期状态
        for st in expired:
            del self.statuses[st]

    def clear_battle_status(self) -> None:
        """清除所有战斗状态"""
        battle_statuses = [StatusName.WEAK, StatusName.POISON, StatusName.STUN, 
                          StatusName.ATK_MULTIPLIER, StatusName.BARRIER, 
                          StatusName.ATK_UP, StatusName.DAMAGE_REDUCTION]
        for status_name in battle_statuses:
            if status_name in self.statuses:
                del self.statuses[status_name]

def get_random_monster(max_tier=None, current_round=None, effect_probability=None):
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
    return Monster(tier=random.randint(1, max_tier), effect_probability=effect_probability) 