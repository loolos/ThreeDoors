"""怪物定义：类型与 tier、生成、战力估算与战斗相关逻辑。"""

from models.items import create_random_item, GoldBag
from typing import TYPE_CHECKING, Optional
from models.game_config import GameConfig
from models.status import Status, StatusName
if TYPE_CHECKING:
    from models.player import Player

import random


def estimate_player_power(player=None, current_round=0):
    """
    估算玩家当前战力，用于动态匹配怪物强度。

    计算公式（与代码保持一致）：
    - round_score = max(0, int(current_round)) * 2
    - base_atk = player._atk（优先）否则 player.atk
    - power_score = base_atk * 0.15 + hp * 0.08 + min(gold, 400) * 0.02 + round_score
    - 其中 hp = max(0, player.hp)，gold = max(0, player.gold)

    举例（假设 player._atk 不存在，因此用 player.atk 作为 base_atk）：
    1) current_round=20, hp=200, atk=50, gold=100
       - round_score=20*2=40
       - atk项=50*0.15=7.5, hp项=200*0.08=16, gold项=min(100,400)*0.02=2
       - power_score=7.5+16+2+40=65.5
    2) current_round=100, hp=1000, atk=200, gold=400
       - round_score=100*2=200
       - atk项=200*0.15=30, hp项=1000*0.08=80, gold项=400*0.02=8
       - power_score=30+80+8+200=318
    3) current_round=200, hp=0, atk=200, gold=400（hp=0 代表当前 hp 不给/为 0）
       - round_score=200*2=400
       - atk项=200*0.15=30, hp项=0*0.08=0, gold项=400*0.02=8
       - power_score=30+0+8+400=438
    4) current_round=200, hp=2000, atk=400, gold=1000（gold 会被 cap 到 400）
       - round_score=400
       - atk项=400*0.15=60, hp项=2000*0.08=160, gold项=min(1000,400)*0.02=8
       - power_score=60+160+8+400=628
    """
    round_score = max(0, int(current_round or 0)) * 2
    if player is None:
        return float(round_score)

    base_atk = getattr(player, "_atk", None)
    if base_atk is None:
        base_atk = getattr(player, "atk", 0)
    hp = max(0, getattr(player, "hp", 0))
    gold = max(0, getattr(player, "gold", 0))

    # 主要依据回合推进；玩家属性仅提供轻微修正
    return float(base_atk * 0.15 + hp * 0.08 + min(gold, 400) * 0.02 + round_score)

class Monster:
    """怪物实体：名称、血量、攻击、tier、掉落与战斗行为。"""
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
            ("半人马", 36, 7),       # 神话生物
            ("牛头人", 42, 6),       # 力量型怪物
            ("树人", 50, 5),        # 自然生物
            ("狼人", 40, 7),        # 诅咒生物
            ("食人魔", 46, 6),      # 巨型生物
            ("美杜莎", 34, 8),      # 神话生物
            ("巨型蝎子", 39, 7),    # 节肢生物
            ("幽灵", 32, 8)         # 灵体生物
        ],
        3: [  # 首领级怪物
            ("巨魔酋长", 88, 13),    # 部落首领
            ("九头蛇", 96, 12),      # 传说生物
            ("石像鬼", 78, 15),      # 魔法造物
            ("吸血鬼", 84, 14),      # 不死生物
            ("独眼巨人", 108, 12),   # 神话巨人
            ("精灵法师", 72, 16),    # 魔法使用者
            ("地狱犬", 94, 13),      # 地狱生物
            ("巨型蜘蛛", 90, 14)     # 巨型节肢生物
        ],
        4: [  # 传说级怪物
            ("青铜龙", 180, 24),      # 金属龙
            ("死亡骑士", 165, 28),   # 不死战士
            ("冰霜巨人", 210, 22),    # 元素巨人
            ("暗影刺客", 150, 30),   # 暗影生物
            ("雷鸟", 175, 25),        # 天空生物
            ("海妖", 160, 27),       # 水生生物
            ("地穴领主", 195, 24),    # 地下生物
            ("炎魔", 220, 23)         # 火焰生物
        ],
        5: [  # 史诗级怪物
            ("白银龙", 360, 42),     # 高级金属龙
            ("利维坦", 430, 38),      # 远古巨兽
            ("凤凰", 340, 50),       # 神话鸟类
            ("泰坦", 410, 40),       # 上古巨人
            ("冥界使者", 350, 47),   # 冥界生物
            ("天使", 380, 44),       # 天界生物
            ("混沌巫师", 330, 55),   # 混沌法师
            ("远古守卫", 460, 39)    # 远古生物
        ],
        6: [  # 神话级怪物
            ("黄金龙", 1100, 112),     # 最强金属龙
            ("克拉肯", 1260, 106),     # 深海巨兽
            ("天启骑士", 1180, 128),   # 末日使者
            ("世界之蛇", 1320, 116),   # 世界级巨兽
            ("深渊领主", 1200, 124),   # 深渊生物
            ("创世神官", 1150, 118),   # 神级生物
            ("混沌之主", 1080, 136),   # 混沌生物
            ("永恒守护者", 1450, 110)  # 永恒生物
        ]
    }

    # 怪物等级提示（3~5字，供门提示约25~30字总长）
    MONSTER_TIER_HINTS = {
        1: ["微弱", "弱小", "不难对付", "轻松", "无妨"],
        2: ["棘手", "小心", "需认真", "挑战", "谨慎"],
        3: ["危险", "强大", "恶战", "压力", "全力以赴"],
        4: ["极危", "非凡", "可怕", "慎重", "压迫"],
        5: ["史诗", "窒息", "传说", "战栗", "苦战"],
        6: ["神话", "绝望", "传说级", "颤抖", "最强"],
    }

    # 怪物类型提示（5~9字，供门提示约25~30字总长）
    MONSTER_TYPE_HINTS = {
        "小哥布林": ["怪笑阵阵", "怪味飘来", "矮小身影"],
        "史莱姆": ["粘液痕迹", "潮湿滑腻", "果冻状"],
        "蝙蝠": ["翅声扑扑", "黑影掠过", "倒挂轮廓"],
        "野狼": ["低沉嚎叫", "兽腥扑鼻", "绿眸闪烁"],
        "食人花": ["花香异样", "藤蔓蠕动", "花瓣开合"],
        "小蜥蜴人": ["沙沙爬行", "鳞片反光", "吐信声"],
        "土匪": ["窃窃私语", "人迹杂乱", "刀刃轻响"],
        "小鸟妖": ["羽毛飘落", "怪鸟啼鸣", "羽翼拍打"],
        "半人马": ["马蹄踏地", "野性气息", "鬃毛拂动"],
        "牛头人": ["地面震动", "沉重喘息", "牛角轮廓"],
        "树人": ["木香弥漫", "枝杈摇晃", "根须窸窣"],
        "狼人": ["月光下影", "野兽低吼", "毛皮耸动"],
        "食人魔": ["腐臭弥漫", "地面震颤", "巨影晃动"],
        "美杜莎": ["寒意袭来", "蛇嘶嘶响", "发丝蠕动"],
        "巨型蝎子": ["毒息飘散", "尾刺轻晃", "节肢摩擦"],
        "幽灵": ["温度骤降", "阴森笑声", "半透明影"],
        "巨魔酋长": ["野蛮呐喊", "篝火焦味", "战鼓咚咚"],
        "九头蛇": ["硫磺刺鼻", "多重嘶嘶", "多头轮廓"],
        "石像鬼": ["石块移动", "魔法波动", "石翼展开"],
        "吸血鬼": ["血腥弥漫", "红眸闪烁", "斗篷掠动"],
        "独眼巨人": ["大地震裂", "巨足踏地", "单目注视"],
        "精灵法师": ["魔力涌动", "咒文低吟", "法杖微光"],
        "地狱犬": ["硫磺与吠", "三头低吼", "烈焰气息"],
        "巨型蜘蛛": ["蛛网密布", "毒雾飘散", "节肢咔哒"],
        "青铜龙": ["金属气息", "龙吟回荡", "鳞甲反光"],
        "死亡骑士": ["死气森然", "铠甲碰撞", "霜雾笼罩"],
        "冰霜巨人": ["寒意刺骨", "冰晶飘舞", "霜纹蔓延"],
        "暗影刺客": ["杀意潜伏", "影动无声", "刃光一闪"],
        "雷鸟": ["电弧闪烁", "雷鸣隐约", "羽翼带电"],
        "海妖": ["潮气扑面", "海浪低吟", "歌声诱人"],
        "地穴领主": ["地下震动", "腐朽气息", "骸骨窸窣"],
        "炎魔": ["热浪扑面", "硫磺浓烈", "火焰翻腾"],
        "白银龙": ["银光流转", "威严龙吟", "圣洁鳞片"],
        "利维坦": ["深海威压", "远古气息", "巨躯轮廓"],
        "凤凰": ["炙热不熄", "不死鸟鸣", "火焰涅槃"],
        "泰坦": ["大地颤抖", "上古威压", "巨影遮天"],
        "冥界使者": ["死亡笼罩", "冥力涌动", "彼岸低语"],
        "天使": ["圣光降临", "天界圣歌", "羽翼洁白"],
        "混沌巫师": ["混沌扭曲", "魔力狂涌", "咒文混乱"],
        "远古守卫": ["远古气息", "守护之力", "岁月沉淀"],
        "黄金龙": ["神光璀璨", "龙王威压", "金鳞辉煌"],
        "克拉肯": ["深海恐惧", "触腕蠕动", "海怪低吟"],
        "天启骑士": ["末日降临", "天启之力", "马蹄踏火"],
        "世界之蛇": ["世界扭曲", "巨躯盘绕", "蛇瞳凝视"],
        "深渊领主": ["深渊召唤", "暗潮涌动", "无尽坠落"],
        "创世神官": ["创世之力", "神威浩荡", "圣光灼目"],
        "混沌之主": ["混沌威能", "现实崩裂", "虚空撕扯"],
        "永恒守护者": ["永恒震颤", "时空波动", "无尽守望"],
    }

    # 怪物出场/死亡台词（改编自文学、影视、神话传说）
    # 仅部分代表性怪物配置；无配置者不显示台词
    MONSTER_QUOTES = {
        "吸血鬼": {
            "entrance": [
                "倾听暗夜之子的声音——多么美妙的音乐！",  # 《德古拉》Stoker
            ],
            "death": [
                "血液即生命……而今……",  # 《德古拉》
            ],
        },
        "独眼巨人": {
            "entrance": [
                "何人胆敢踏入我的领地？",
            ],
            "death": [
                "无人……是无人骗了我！",  # 《奥德赛》波吕斐摩斯
            ],
        },
        "美杜莎": {
            "entrance": [
                "直视我……如果你敢。",
            ],
            "death": [
                "我曾……也被人爱过……",  # 奥维德《变形记》美杜莎悲剧
            ],
        },
        "牛头人": {
            "entrance": [
                "迷宫中，只有猎人与猎物。",  # 米诺陶洛斯神话
            ],
            "death": [
                "迷宫的尽头……竟是解脱……",
            ],
        },
        "九头蛇": {
            "entrance": [
                "你砍得掉我的头，砍得尽我的命吗？",  # 赫拉克勒斯与许德拉
            ],
            "death": [
                "即便九首俱断……毒血仍在……",
            ],
        },
        "地狱犬": {
            "entrance": [
                "凡入此门者，须弃绝一切希望。",  # 但丁《神曲·地狱篇》
            ],
            "death": [
                "冥府之门……终将再度开启……",
            ],
        },
        "炎魔": {
            "entrance": [
                "吾乃乌顿之炎，远古阴影的造物。",  # 托尔金《魔戒》
            ],
            "death": [
                "阴影……终将……回归……",
            ],
        },
        "凤凰": {
            "entrance": [
                "灰烬之中，唯我不朽。",  # 凤凰涅槃神话
            ],
            "death": [
                "灰烬中……我会归来……",
            ],
        },
        "克拉肯": {
            "entrance": [
                "深海之眠已被惊扰……",  # 北欧神话/儒勒·凡尔纳
            ],
            "death": [
                "深渊……在召唤……",
            ],
        },
        "泰坦": {
            "entrance": [
                "吾等曾执掌天穹。",  # 希腊神话泰坦
            ],
            "death": [
                "吾等……终将……再度崛起……",
            ],
        },
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
        self.sprite_key = self._infer_sprite_key()
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
            self.type_hint = "未知声响"
        else:
            hints = self.MONSTER_TYPE_HINTS.get(self.name, ["未知声响"])
            self.type_hint = random.choice(hints) if isinstance(hints, list) else "未知声响"

    def _infer_sprite_key(self) -> str:
        """根据名称推断怪物贴图分组。"""
        name = self.name or ""
        if "银羽飞贼·莱希娅" in name:
            return "monster_elf_rival"
        if any(k in name for k in ["龙", "蛇", "凤凰", "雷鸟"]):
            return "monster_dragon"
        if any(k in name for k in ["鬼", "幽灵", "冥界", "死亡骑士", "吸血鬼"]):
            return "monster_undead"
        if any(k in name for k in ["土匪", "刺客", "骑士", "法师", "蜥蜴人", "半人马"]):
            return "monster_humanoid"
        if any(k in name for k in ["狼", "犬", "蜘蛛", "蝎子", "鸟妖", "克拉肯", "利维坦"]):
            return "monster_beast"
        if any(k in name for k in ["树人", "天使", "神官", "守护者", "泰坦"]):
            return "monster_mythic"
        if any(k in name for k in ["史莱姆", "食人花", "地穴"]):
            return "monster_spirit"
        return "monster_default"

    def _generate_loot(self):
        """生成怪物的掉落物品"""
        loot = []
        
        # 基础金币掉落，随怪物等级提升
        base_gold = random.randint(5, 15) * self.tier
        gold_bag = GoldBag(f"{base_gold}金币", gold_amount=base_gold)
        loot.append(gold_bag)
        
        # 额外宝物统一走 create_random_item，并将怪物 tier 传入以关联宝物强度
        treasure_item = create_random_item(treasure_tier=self.tier)
        if treasure_item is not None:
            loot.append(treasure_item)
        
        return loot

    def get_loot(self):
        """获取怪物的掉落物品"""
        return self.loot

    def process_loot(self, player):
        """处理怪物的掉落物品，应用到玩家身上"""
        for item in self.loot:
            if hasattr(player, 'controller') and player.controller:
                player.controller.add_message(f"掉落：{item.name}")
            item.acquire(player=player)

    def take_damage(self, damage: int):
        """受到伤害"""
        # 检查是否有减伤效果
        if self.has_status(StatusName.DAMAGE_REDUCTION):
            # 获取减伤比例 (默认 0.7 即减免 30%)
            reduction = self.statuses[StatusName.DAMAGE_REDUCTION].value
            damage = max(1, int(damage * reduction))
            
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

        # 计算伤害
        dmg = max(1, self.atk - random.randint(0, 1))
        
        # 如果有攻击力翻倍效果
        if self.has_status(StatusName.ATK_MULTIPLIER):
            dmg *= self.statuses[StatusName.ATK_MULTIPLIER].value
        target_controller = getattr(target, "controller", None)
        if target_controller and hasattr(target_controller, "apply_battle_extensions"):
            dmg = target_controller.apply_battle_extensions(
                trigger="monster_attack",
                attacker=self,
                defender=target,
                damage=dmg,
            )
        # 结界：按受击次数递减减伤（90% -> 80% -> 70% ... -> 0%）
        if target.has_status(StatusName.BARRIER):
            barrier_status = target.statuses.get(StatusName.BARRIER)
            if barrier_status and hasattr(barrier_status, "get_reduction_ratio"):
                reduction_ratio = barrier_status.get_reduction_ratio()
                reduced = int(dmg * reduction_ratio)
                dmg = max(0, dmg - reduced)
                if target_controller:
                    ratio_percent = int(reduction_ratio * 100)
                    if ratio_percent > 0:
                        target_controller.add_message(
                            f"{self.name} 的攻击触发结界：本次减伤 {ratio_percent}%，仅受到 {dmg} 点伤害。"
                        )
                    else:
                        target_controller.add_message(
                            f"{self.name} 的攻击触发结界：减伤已衰减至 0%，你受到 {dmg} 点伤害。"
                        )
        # 终局「选择困难症候群」等：台词挂在怪物上，不依赖门战斗扩展，确保每次出手都会嘲讽
        if target_controller and bool(getattr(self, "story_default_final_boss", False)):
            taunt_lines = getattr(self, "story_default_final_boss_attack_taunts", None)
            if isinstance(taunt_lines, list):
                valid_taunts = [t for t in taunt_lines if isinstance(t, str) and t.strip()]
                if valid_taunts:
                    target_controller.add_message(f"{self.name}：{random.choice(valid_taunts)}")
        # 造成伤害
        target.take_damage(dmg)

        # 使用设置的效果概率
        if random.random() < self.effect_probability:
            effect = random.choice([StatusName.WEAK, StatusName.POISON, StatusName.STUN])
            duration = random.randint(1, 2)
            
            # 应用状态
            status = effect.create_instance(duration=duration, target=target)
            target.apply_status(status)
            if hasattr(target, 'controller') and target.controller:
                # 获取状态名称的中文描述
                status_name_cn = effect.cn_name
                target.controller.add_message(f"{self.name} 附带 {status_name_cn} 效果 ({duration}回合)!")

        return False

    def get_hints(self):
        """获取怪物的提示信息"""
        return [self.tier_hint, self.type_hint]

    def get_entrance_quote(self) -> Optional[str]:
        """获取怪物出场台词，无则返回 None。"""
        quotes = self.MONSTER_QUOTES.get(self.name, {})
        lines = quotes.get("entrance", [])
        if not lines:
            return None
        return random.choice(lines) if isinstance(lines, list) else lines

    def get_death_quote(self) -> Optional[str]:
        """获取怪物死亡台词，无则返回 None。"""
        quotes = self.MONSTER_QUOTES.get(self.name, {})
        lines = quotes.get("death", [])
        if not lines:
            return None
        return random.choice(lines) if isinstance(lines, list) else lines

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
        self.statuses[StatusName.STUN] = StatusName.STUN.create_instance(duration=duration, target=self)

    def battle_status_duration_pass(self) -> None:
        """处理战斗回合的状态持续时间"""
        expired = []
        for st in list(self.statuses):
            if st not in self.statuses:
                continue
            if self.statuses[st].duration_pass():
                expired.append(st)
        
        for st in expired:
            if st in self.statuses:
                del self.statuses[st]

    def clear_battle_status(self) -> None:
        """清除所有战斗状态"""
        expired = []
        for status_name, status in self.statuses.items():
            if status.is_battle_only:
                expired.append(status_name)
        
        # 移除战斗状态
        for status_name in expired:
            del self.statuses[status_name]

def _get_round_limited_max_tier(current_round):
    """根据回合数给出基础怪物等级上限。"""
    if current_round is None:
        return 1
    if current_round <= 8:
        return 1  # 前8回合只出现Tier 1怪物
    if current_round <= 18:
        return 2  # 9-18回合可能出现Tier 2怪物
    if current_round <= 30:
        return 3  # 19-30回合可能出现Tier 3怪物
    if current_round <= 45:
        return 4  # 31-45回合可能出现Tier 4怪物
    if current_round <= 60:
        return 5  # 46-60回合可能出现Tier 5怪物
    return 6  # 60回合后可能出现所有怪物


def _roll_tier(max_tier, current_round, power_score):
    """按权重抽取怪物等级，后期更偏向高 tier。"""
    if max_tier <= 1:
        return 1

    weights = []
    for tier in range(1, max_tier + 1):
        # 同阶段下低 tier 更常见；后期再逐步提高高 tier 出场率
        base_weight = float((max_tier - tier + 1) * 1.2)
        if current_round is not None and current_round >= 20 and tier >= max_tier - 1:
            base_weight += 0.8
        if current_round is not None and current_round >= 45 and tier == max_tier:
            base_weight += 1.4
        if current_round is not None and current_round >= 60 and power_score >= 140 and tier == max_tier:
            base_weight += 0.8
        weights.append(max(0.1, base_weight))

    total = sum(weights)
    roll = random.uniform(0, total)
    acc = 0.0
    for tier, weight in enumerate(weights, start=1):
        acc += weight
        if roll <= acc:
            return tier
    return max_tier


def _apply_player_match_scaling(monster, player, current_round, power_score):
    """
    根据 `estimate_player_power()` 的结果，对怪物 `hp/atk/effect_probability` 进行动态缩放。

    约束：
    - `current_round < 40` 时不启用玩家强度缩放（直接返回）
    - 缩放强度由 `pressure = power_score / 400` 决定，且每次都会叠加随机波动
    """
    if player is None:
        return

    round_count = max(0, int(current_round or 0))
    if round_count < 40:
        # 玩家属性带来的额外怪物强化仅在 40 回合后启用
        return

    # 压力值：玩家越强 => power_score 越高 => pressure 越大 => 怪物属性越容易被放大
    pressure = power_score / 400.0

    # 乘法缩放上限：避免怪物 hp/atk 被无限放大
    hp_scale = min(4.65, random.uniform(1.0, 1.0 + pressure))
    atk_scale = min(2.45, random.uniform(1.0, 1.0 + pressure))

    # 额外的加法偏移：让高强度下的差异更明显（并带随机）
    scaled_hp = int(monster.hp * hp_scale + random.randint(0, 200) * pressure)
    scaled_atk = int(monster.atk * atk_scale + random.randint(0, 50) * pressure)

    # 保底：不会比原始 hp/atk 更低
    monster.hp = max(monster.hp, scaled_hp)
    monster.atk = max(monster.atk, scaled_atk)

    # 状态/特效出现概率同步上调，但有上限
    monster.effect_probability = min(
        0.75, monster.effect_probability + pressure * 0.4
    )


def get_random_monster(max_tier=None, current_round=None, effect_probability=None, player=None, unlocked_tier=None):
    """根据回合和已解锁 tier 生成随机怪物。"""
    round_limited = _get_round_limited_max_tier(current_round)
    hard_cap = GameConfig.MONSTER_MAX_TIER
    if max_tier is None:
        max_tier = hard_cap
    else:
        max_tier = max(GameConfig.MONSTER_MIN_TIER, min(hard_cap, int(max_tier)))
    if unlocked_tier is None:
        unlocked_tier = hard_cap
    else:
        unlocked_tier = max(GameConfig.MONSTER_MIN_TIER, min(hard_cap, int(unlocked_tier)))

    power_score = estimate_player_power(player=player, current_round=current_round)
    max_tier = min(max_tier, round_limited, unlocked_tier)
    max_tier = max(GameConfig.MONSTER_MIN_TIER, max_tier)

    tier = _roll_tier(max_tier=max_tier, current_round=current_round, power_score=power_score)
    monster = Monster(tier=tier, effect_probability=effect_probability)
    _apply_player_match_scaling(
        monster=monster,
        player=player,
        current_round=current_round,
        power_score=power_score,
    )
    return monster
