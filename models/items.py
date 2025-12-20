import random
from enum import Enum
from models.game_config import GameConfig
from models.status import Status, StatusName
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.player import Player
    from models.monster import Monster

class ItemType(Enum):
    CONSUMABLE = "consumable"  # 消耗品
    BATTLE = "battle"  # 战斗物品
    PASSIVE = "passive"  # 被动物品

class Item:
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
            recovered = player.heal(self.heal_amount)
            player.controller.add_message(f"恢复 {recovered} HP!")

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
            player.controller.add_message(f"结界形成，接下来{self.duration}回合你免受怪物伤害！")

# 巨大卷轴类
class GiantScroll(BattleItemBase):
    def effect(self, **kwargs):
        player = kwargs.get('player')
        target = kwargs.get('target', player)  # 默认对自己生效
        if player and target:
            target.apply_status(StatusName.ATK_MULTIPLIER.create_instance(duration=self.duration, target=target, value=2))
            player.controller.add_message(f"巨大卷轴激活，接下来{self.duration}回合你的攻击力翻倍！")

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

def create_random_item():
    """创建随机物品 (包含消耗品、永久装备和战斗物品)"""
    item_types = [
        # (Class, Params, Weight)
        (HealingPotion, {"name": "小治疗药水", "heal_amount": 10, "cost": 4}, 20),
        (HealingPotion, {"name": "大治疗药水", "heal_amount": 30, "cost": 12}, 10),
        (Equipment, {"name": "生锈的长剑", "atk_bonus": 2, "cost": 15}, 15),
        (Equipment, {"name": "精钢长剑", "atk_bonus": 5, "cost": 35}, 5),
        (DamageReductionScroll, {"name": "减伤卷轴", "duration": 5, "cost": 20}, 15),
        (AttackUpScroll, {"name": "攻击力提升卷轴", "atk_bonus": 5, "duration": 8, "cost": 25}, 10),
        (HealingScroll, {"name": "恢复卷轴", "duration": 10, "cost": 18}, 10),
        (ImmuneScroll, {"name": "免疫卷轴", "duration": 5, "cost": 20}, 5),
        (FlyingHammer, {"name": "飞锤", "cost": 25}, 5),
        (Barrier, {"name": "结界卷轴", "duration": 3, "cost": 30}, 5),
        (GiantScroll, {"name": "巨大化卷轴", "duration": 3, "cost": 40}, 5),
        (GoldBag, {"name": "小钱袋", "gold_amount": random.randint(10, 50), "cost": 0}, 10)
    ]
    
    # 根据权重随机选择
    total_weight = sum(item[2] for item in item_types)
    r = random.uniform(0, total_weight)
    upto = 0
    for item_class, params, weight in item_types:
        if upto + weight >= r:
            return item_class(**params)
        upto += weight
    
    # Fallback
    return item_types[0][0](**item_types[0][1])
