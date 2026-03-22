"""物品定义：类型枚举、基类与具体物品（药水、卷轴、战斗道具等）。"""

import random
from enum import Enum
from models.game_config import GameConfig
from models.status import Status, StatusName
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.player import Player
    from models.monster import Monster


class ItemType(Enum):
    """物品大类：消耗品、战斗用、被动常驻。"""
    CONSUMABLE = "consumable"  # 消耗品
    BATTLE = "battle"  # 战斗物品
    PASSIVE = "passive"  # 被动物品


class Item:
    """物品基类：名称、类型、价格及 effect/acquire 接口。"""

    def __init__(self, name: str, **kwargs):
        self.name = name
        self.item_type = kwargs.get('item_type')
        self.cost = kwargs.get('cost', 0)

    def get_type(self) -> ItemType:
        """获取物品类型"""
        return self.item_type

    def effect(self, **kwargs):
        """物品效果的基础方法，由子类实现"""
        raise NotImplementedError("子类必须实现effect方法")
        
    def acquire(self, **kwargs) -> bool:
        """
        物品获得时的行为，返回是否需要加入物品栏
        True: 加入物品栏
        False: 直接使用效果
        """
        raise NotImplementedError("子类必须实现acquire方法")

class ConsumableItem(Item):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, item_type=ItemType.CONSUMABLE, cost=kwargs.get('cost', 0))
        
    def acquire(self, **kwargs) -> bool:
        # 消耗品获得时直接使用
        self.effect(**kwargs)
        return False

class BattleItem(Item):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, item_type=ItemType.BATTLE, cost=kwargs.get('cost', 0))
        
    def acquire(self, **kwargs) -> bool:
        # 战斗物品获得时加入物品栏
        player = kwargs.get('player')
        if player:
            if ItemType.BATTLE not in player.inventory:
                player.inventory[ItemType.BATTLE] = []
            player.inventory[ItemType.BATTLE].append(self)
            player.controller.add_message(f"{self.name}已加入物品栏!")
        return True

class PassiveItem(Item):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, item_type=ItemType.PASSIVE, cost=kwargs.get('cost', 0))
        self.duration = kwargs.get('duration', 0)
        
    def acquire(self, **kwargs) -> bool:
        # 被动物品获得时加入物品栏
        player = kwargs.get('player')
        if player:
            if ItemType.PASSIVE not in player.inventory:
                player.inventory[ItemType.PASSIVE] = []
            player.inventory[ItemType.PASSIVE].append(self)
            player.controller.add_message(f"{self.name}已加入物品栏!")
        return True

# 治疗药水类
class HealingPotion(ConsumableItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.heal_amount = kwargs.get('heal_amount', 0)

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player:
            total_heal = self.heal_amount
            bonus_heal = self._get_late_game_bonus_heal(player)
            if bonus_heal > 0:
                total_heal += bonus_heal
            recovered = player.heal(total_heal)
            if bonus_heal > 0:
                player.controller.add_message(f"恢复 {recovered} HP! (其中 {bonus_heal} 点来自生命底蕴)")
            else:
                player.controller.add_message(f"恢复 {recovered} HP!")

    def _get_late_game_bonus_heal(self, player: "Player") -> int:
        """
        40 回合后，治疗药水有概率触发「生命底蕴」额外治疗。

        触发与强度规则（以当前实现为准）：
        - 仅当回合数 > 40 且历史峰值生命（peak_hp）高于初始生命时才可能触发；
        - 触发概率：min(0.9, 0.25 + (round_count - 40) * 0.01)
        - 额外治疗量（触发后一次性加成）：
          base_cap = floor(hp_growth / 100)
          bonus_cap = max(1, floor(base_cap * base_heal * U(0.2, 1.0)))
          其中 base_heal = 本药水的 heal_amount，U 为均匀随机数（每次调用重算）。
        """
        controller = getattr(player, "controller", None)
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        if round_count <= 40:
            return 0

        peak_hp = int(max(getattr(controller, "player_peak_hp", player.hp), player.hp))
        hp_growth = max(0, peak_hp - GameConfig.START_PLAYER_HP)
        if hp_growth <= 0:
            return 0

        # 生命底蕴：历史峰值生命越高、药水基础治疗越大，触发时给的额外治疗越多。
        # 当前算法不再做“按药水大小的线性缩放+randint”，而是：
        # - base_cap = floor(hp_growth / 100)
        # - bonus_cap = max(1, floor(base_cap * base_heal * U(0.2, 1.0)))
        base_cap = hp_growth // 100
        base_heal = max(0, int(getattr(self, "heal_amount", 0)))
        bonus_cap = max(1, int((base_cap * base_heal) *random.uniform(0.2,1)))
        # 40 回合后可触发概率随回合数上升，但保持上限避免失衡
        trigger_chance = min(0.9, 0.25 + (round_count - 40) * 0.01)
        if random.random() >= trigger_chance:
            return 0

        return bonus_cap

# 装备类
class Equipment(ConsumableItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.atk_bonus = kwargs.get('atk_bonus', 0)

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player:
            player.change_base_atk(self.atk_bonus)

# 减伤卷轴类
class DamageReductionScroll(ConsumableItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.duration = kwargs.get('duration', random.randint(10, 15))

    def effect(self, **kwargs):
        player = kwargs.get('player')
        monster = kwargs.get('monster')
        if player:
            player.apply_status(StatusName.DAMAGE_REDUCTION.create_instance(duration=self.duration, target=player))
        elif monster:
            monster.apply_status(StatusName.DAMAGE_REDUCTION.create_instance(duration=self.duration, target=monster))

# 攻击力增益卷轴类
class AttackUpScroll(ConsumableItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.atk_bonus = kwargs.get('atk_bonus', 0)
        self.duration = kwargs.get('duration', random.randint(10, 15))

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player:
            player.apply_status(StatusName.ATK_UP.create_instance(duration=self.duration, target=player, value=self.atk_bonus))

# 复活卷轴类
class ReviveScroll(PassiveItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.duration = kwargs.get('duration', 0)

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player and player.hp <= 0:
            player.hp = GameConfig.START_PLAYER_HP
            player.controller.add_message("复活卷轴生效，你复活了!")

# 恢复卷轴类
class HealingScroll(ConsumableItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.duration = kwargs.get('duration', random.randint(10, 15))

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player:
            player.apply_status(StatusName.HEALING_SCROLL.create_instance(duration=self.duration, target=player))

# 免疫卷轴类
class ImmuneScroll(ConsumableItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.duration = kwargs.get('duration', 0)

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player:
            player.apply_status(StatusName.IMMUNE.create_instance(duration=self.duration, target=player))

# 战斗物品类
class BattleItemBase(BattleItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.duration = kwargs.get('duration', 0)

# 飞锤类
class FlyingHammer(BattleItemBase):
    def effect(self, **kwargs):
        player = kwargs.get('player')
        monster = kwargs.get('monster')
        target = kwargs.get('target', monster)  # 默认对怪物生效
        if player and target:
            target.apply_status(StatusName.STUN.create_instance(duration=3, target=target))
            player.controller.add_message("飞锤飞出，怪物被晕眩3回合！")

# 结界类
class Barrier(BattleItemBase):
    def effect(self, **kwargs):
        player = kwargs.get('player')
        target = kwargs.get('target', player)  # 默认对自己生效
        if player and target:
            target.apply_status(StatusName.BARRIER.create_instance(duration=self.duration, target=target))
            player.controller.add_message("结界形成：首次减伤90%，之后每次受击减伤递减10%，最低降至0%（战斗结束失效）。")

# 巨大卷轴类
class GiantScroll(BattleItemBase):
    def effect(self, **kwargs):
        player = kwargs.get('player')
        target = kwargs.get('target', player)  # 默认对自己生效
        if player and target:
            target.apply_status(StatusName.ATK_MULTIPLIER.create_instance(duration=self.duration, target=target, value=2))
            player.controller.add_message(f"巨大卷轴激活，接下来{self.duration}回合你的攻击力翻倍！")


class DepositedBackpack(BattleItemBase):
    """时光当铺后续奖励：寄存的背包。"""

    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.stored_gold = max(0, int(kwargs.get('stored_gold', 0)))
        self.stored_items = list(kwargs.get('stored_items', []))

    def acquire(self, **kwargs) -> bool:
        # 寄存的背包是剧情结算容器，不进入背包，获得时立即结算内容。
        self.effect(**kwargs)
        return False

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player:
            player.controller.add_message("你拆开寄存的背包，开始清点当铺寄存的东西。")
            if self.stored_gold > 0:
                player.add_gold(self.stored_gold)
                player.controller.add_message(f"寄存的背包里翻出了 {self.stored_gold} 金币。")
            for item in self.stored_items:
                player.controller.add_message(f"寄存的背包里找到：{item.name}")
                item.acquire(player=player)

# 金币袋子类
class GoldBag(ConsumableItem):
    def __init__(self, name: str, **kwargs):
        super().__init__(name, cost=kwargs.get('cost', 0))
        self.gold_amount = kwargs.get('gold_amount', 0)

    def effect(self, **kwargs):
        player = kwargs.get('player')
        if player:
            player.add_gold(self.gold_amount)
            player.controller.add_message(f"获得 {self.gold_amount} 金币!")

def create_reward_door_item():
    """创建宝物门专用随机物品，多样化且不含金币袋"""
    # 治疗药水：小/中/大，回复量随机
    potion_choices = [
        ("微光药水", 5, 12),
        ("小治疗药水", 8, 18),
        ("中治疗药水", 12, 28),
        ("大治疗药水", 20, 45),
        ("生命精华", 30, 55),
    ]
    # 装备：多种名称与加成
    equip_choices = [
        ("生锈的匕首", 1, 2),
        ("铁剑", 2, 3),
        ("精钢长剑", 3, 5),
        ("秘银短剑", 4, 6),
        ("附魔之刃", 5, 8),
    ]
    # 卷轴：多种类型与数值
    scroll_defs = [
        ("减伤卷轴", DamageReductionScroll, {"duration": random.randint(3, 8)}),
        ("攻击卷轴", AttackUpScroll, {"atk_bonus": random.randint(3, 7), "duration": random.randint(5, 12)}),
        ("恢复卷轴", HealingScroll, {"duration": random.randint(6, 14)}),
        ("免疫卷轴", ImmuneScroll, {"duration": random.randint(3, 6)}),
    ]
    # 战斗物品
    battle_defs = [
        (FlyingHammer, {"name": "飞锤"}),
        (Barrier, {"name": "结界", "duration": random.randint(2, 5)}),
        (GiantScroll, {"name": "巨大卷轴", "duration": random.randint(2, 4)}),
    ]

    category = random.choices(
        ["potion", "equip", "scroll", "battle"],
        weights=[25, 22, 28, 25],
        k=1
    )[0]
    if category == "potion":
        name, lo, hi = random.choice(potion_choices)
        return HealingPotion(name, heal_amount=random.randint(lo, hi), cost=0)
    if category == "equip":
        name, lo, hi = random.choice(equip_choices)
        atk = random.randint(lo, hi)
        return Equipment(name, atk_bonus=atk, cost=atk * 3)
    if category == "scroll":
        name, cls, extra = random.choice(scroll_defs)
        return cls(name, cost=0, **extra)
    cls, extra = random.choice(battle_defs)
    return cls(name=extra.get("name", "宝物"), cost=0, **{k: v for k, v in extra.items() if k != "name"})


def _normalize_treasure_tier(treasure_tier: Optional[int]) -> Optional[int]:
    """规范化宝物 tier（用于与怪物强度关联的掉落）。"""
    if treasure_tier is None:
        return None
    try:
        parsed_tier = int(treasure_tier)
    except (TypeError, ValueError):
        parsed_tier = GameConfig.MONSTER_MIN_TIER
    return max(GameConfig.MONSTER_MIN_TIER, min(GameConfig.MONSTER_MAX_TIER, parsed_tier))


def _choose_equipment_name_pool(atk_bonus: int):
    """根据攻击加成选择最接近的统一装备命名池。"""
    pools = GameConfig.EQUIPMENT_NAME_POOLS
    if not pools:
        return ["装备"]
    closest_key = min(pools.keys(), key=lambda key: abs(int(key) - int(atk_bonus)))
    return pools[closest_key]


def _create_tiered_treasure_item(treasure_tier: int):
    """按宝物 tier 生成与怪物强度相关的宝物。"""
    tier = _normalize_treasure_tier(treasure_tier) or GameConfig.MONSTER_MIN_TIER
    category = random.choices(["potion", "equip", "scroll"], weights=[40, 30, 30], k=1)[0]

    if category == "potion":
        potion_tier = min(3, max(1, tier))
        potion_choice = random.choices(
            ["小治疗药水", "中治疗药水", "大治疗药水"],
            weights=[0.5, 0.35, 0.15] if potion_tier == 1 else
                    [0.2, 0.5, 0.3] if potion_tier == 2 else
                    [0.1, 0.3, 0.6],
            k=1
        )[0]
        heal_base = {"小治疗药水": (5, 12), "中治疗药水": (10, 22), "大治疗药水": (20, 40)}
        lo, hi = heal_base[potion_choice]
        heal_amount = random.randint(lo + tier, hi + tier * 2)
        return HealingPotion(potion_choice, heal_amount=heal_amount, cost=0)

    if category == "equip":
        equip_boost = 2 * tier
        name_pool = _choose_equipment_name_pool(equip_boost)
        return Equipment(
            random.choice(list(name_pool)),
            atk_bonus=equip_boost,
            cost=equip_boost * 2,
        )

    scroll_value = random.randint(tier + 5, tier * 3 + 10)
    scroll_type = random.choice(["healing", "damage_reduction", "attack_up"])
    if scroll_type == "healing":
        return HealingScroll("恢复卷轴", cost=scroll_value * 2, duration=scroll_value)
    if scroll_type == "damage_reduction":
        return DamageReductionScroll("减伤卷轴", cost=scroll_value * 2, duration=scroll_value)
    return AttackUpScroll("攻击力增益卷轴", atk_bonus=scroll_value, cost=scroll_value * 2, duration=scroll_value)


def create_random_item(treasure_tier: Optional[int] = None):
    """创建随机物品（支持按宝物 tier 生成关联强度掉落）。"""
    normalized_tier = _normalize_treasure_tier(treasure_tier)
    if normalized_tier is not None:
        return _create_tiered_treasure_item(normalized_tier)

    # 兼容旧逻辑：未指定宝物 tier 时沿用原随机池。
    item_types = [
        # (Class, Params, Weight)
        (HealingPotion, {"name": "小治疗药水", "heal_amount": 10, "cost": 4}, 20),
        (HealingPotion, {"name": "中治疗药水", "heal_amount": 20, "cost": 8}, 15),
        (HealingPotion, {"name": "大治疗药水", "heal_amount": 30, "cost": 12}, 10),
        (Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[2], "atk_bonus": 2, "cost": 15}, 15),
        (Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[5], "atk_bonus": 5, "cost": 35}, 8),
        (Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[10], "atk_bonus": 5, "cost": 35}, 5),
        (DamageReductionScroll, {"name": "减伤卷轴", "duration": 5, "cost": 20}, 15),
        (AttackUpScroll, {"name": "攻击力提升卷轴", "atk_bonus": 5, "duration": 8, "cost": 25}, 10),
        (HealingScroll, {"name": "恢复卷轴", "duration": 10, "cost": 18}, 10),
        (ImmuneScroll, {"name": "免疫卷轴", "duration": 5, "cost": 20}, 5),
        (FlyingHammer, {"name": "飞锤", "cost": 25}, 5),
        (Barrier, {"name": "结界", "duration": 3, "cost": 30}, 5),
        (GiantScroll, {"name": "巨大卷轴", "duration": 3, "cost": 40}, 5),
        (GoldBag, {"name": "小钱袋", "gold_amount": random.randint(10, 50), "cost": 0}, 10)
    ]
    
    # 根据权重随机选择
    total_weight = sum(item[2] for item in item_types)
    r = random.uniform(0, total_weight)
    upto = 0
    for item_class, params, weight in item_types:
        if upto + weight >= r:
            params = dict(params or {})
            name_pool = params.pop("name_pool", None)
            if item_class is Equipment and name_pool and "name" not in params:
                params["name"] = random.choice(list(name_pool))
            return item_class(**params)
        upto += weight
    
    # Fallback
    return item_types[0][0](**item_types[0][1])
