import random
from .monster import get_random_monster
from typing import Optional, Dict, Any
from models.base_class import BaseClass
from models.monster import Monster
from models.shop import Shop
from enum import Enum


class DoorEnum(Enum):
    """门类型枚举"""
    TRAP = "trap"
    REWARD = "reward"
    MONSTER = "monster"
    SHOP = "shop"
    
    def create_instance(self, **kwargs):
        """创建门实例"""
        return {
            DoorEnum.TRAP: TrapDoor,
            DoorEnum.REWARD: RewardDoor,
            DoorEnum.MONSTER: MonsterDoor,
            DoorEnum.SHOP: ShopDoor
        }.get(self)(**kwargs)
    
    @classmethod
    def is_valid_door_type(cls, door_type: Any) -> bool:
        """检查是否是有效的门类型"""
        return isinstance(door_type, Door)

    
    @classmethod
    def is_valid_door_enum(cls, door_enum: Any) -> bool:
        """检查是否是有效的门枚举"""
        return isinstance(door_enum, cls)

class Door(BaseClass):
    """门的基类"""
    def _initialize(self, **kwargs) -> None:
        super()._initialize(**kwargs)
        self.controller = kwargs.get('controller', None)
        if not self.controller:
            raise ValueError("controller is required")
                
        if 'hint' in kwargs:
            self.hint = kwargs['hint']
        else:
            self.hint= ""

    def generate_hint(self) -> None:
        """生成门的提示"""
        raise NotImplementedError("子类必须实现generate_hint方法")

    def generate_non_monster_door_hint(self) -> None:
        fake_door_enum = random.choice([enum for enum in DoorEnum if enum != self.enum])
        self.hint = get_mixed_door_hint(frozenset([self.enum, fake_door_enum]))
        if fake_door_enum == DoorEnum.MONSTER:
            fake_monster = get_random_monster(current_round=self.controller.round_count)
            tier_hint, type_hint = fake_monster.get_hints()
            self.hint = f"{self.hint}, {tier_hint}, {type_hint}"

    def enter(self) -> bool:
        """进入门"""
        raise NotImplementedError("子类必须实现enter方法")
    
    


class TrapDoor(Door):
    """陷阱门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.TRAP
        super()._initialize(**kwargs)
        self.damage = kwargs.get('damage', 10)
        self.generate_hint()
    

    def generate_hint(self) -> None:
        if not self.hint:
            self.generate_non_monster_door_hint()
            
    def enter(self) -> bool:
        self.controller.player.take_damage(self.damage)
        self.controller.add_message(f"你受到了{self.damage}点伤害！")
        return True


class RewardDoor(Door):
    """奖励门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.REWARD
        super()._initialize(**kwargs)
        self.reward = kwargs.get('reward', {'gold': 50})
        self.generate_hint()
    
    def generate_hint(self) -> None:
        self.generate_non_monster_door_hint()
    
    def enter(self) -> bool:
        for item, amount in self.reward.items():
            if item == 'gold':
                self.controller.player.gold += amount
                self.controller.add_message(f"你获得了{amount}金币！")
            else:
                self.controller.player.add_item(item, amount)
                self.controller.add_message(f"你获得了{amount}个{item}！")
        return True


class MonsterDoor(Door):
    """怪物门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.MONSTER
        super()._initialize(**kwargs)
        if 'monster' in kwargs:
            self.monster = kwargs['monster']
        else:
            self.monster = get_random_monster(current_round=self.controller.round_count)
        self.generate_hint()
    
    def generate_hint(self) -> None:
        fake_door_enum = random.choice([enum for enum in DoorEnum if enum != self.enum])
        tier_hint, type_hint = self.monster.get_hints()
        self.hint = f"{get_mixed_door_hint(frozenset([self.enum, fake_door_enum]))}, {tier_hint}, {type_hint}"
    
    def enter(self) -> bool:
        if not self.monster:
            return False
        self.controller.current_monster = self.monster
        return True


class ShopDoor(Door):
    """商店门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.SHOP
        super()._initialize(**kwargs)
        self.shop = self.controller.current_shop
        self.generate_hint()
    
    def generate_hint(self) -> None:
        self.generate_non_monster_door_hint()
    
    def enter(self) -> bool:
        if not self.shop:
            return False
        self.controller.current_shop = self.shop
        return True

# 基础提示语配置
HINT_CONFIGS = {
    # 组合提示
    "combo": {
        frozenset({DoorEnum.MONSTER, DoorEnum.REWARD}): [
            "野兽的咆哮中夹杂着金币的叮当声",
            "危险的气息中闪烁着宝物的光芒",
            "黑暗中似乎有宝藏，但似乎也有危险",
            "猛兽的嘶吼与财宝的诱惑交织",
            "危机与机遇并存"
        ],
        frozenset({DoorEnum.MONSTER, DoorEnum.SHOP}): [
            "商人的吆喝声中藏着野兽的咆哮",
            "交易与危险并存",
            "商人的声音中似乎藏着威胁",
            "猛兽的怒吼与商人的叫卖交织",
            "买卖与战斗并存"
        ],
        frozenset({DoorEnum.MONSTER, DoorEnum.TRAP}): [
            "危险的气息扑面而来",
            "猛兽与陷阱的双重威胁",
            "黑暗中藏着双重危险",
            "野兽的咆哮与机关的咔嗒声交织",
            "危机四伏"
        ],
        frozenset({DoorEnum.TRAP, DoorEnum.REWARD}): [
            "机关与宝藏并存",
            "陷阱中似乎藏着宝物",
            "危险与机遇并存",
            "机关的咔嗒声中夹杂着金币的叮当声",
            "危机与财富并存"
        ],
        frozenset({DoorEnum.TRAP, DoorEnum.SHOP}): [
            "商人的声音中似乎藏着机关",
            "交易与陷阱并存",
            "买卖声中似乎有机关的咔嗒声",
            "商人的吆喝与机关的咔嗒声交织",
            "买卖与危险并存"
        ],
        frozenset({DoorEnum.SHOP, DoorEnum.REWARD}): [
            "商人的吆喝声中夹杂着金币的叮当声",
            "交易与财富并存",
            "买卖声中似乎有宝物的光芒",
            "商人的声音与财宝的诱惑交织",
            "买卖与机遇并存"
        ]
    },
    # 缺省提示语
    "default": {
        DoorEnum.MONSTER: [
            "黑暗中似乎有什么在移动...",
            "危险的气息扑面而来...",
            "有什么东西在等待着你...",
            "空气中弥漫着紧张的气氛...",
            "似乎有什么可怕的存在..."
        ],
        DoorEnum.TRAP: [
            "这里的气氛有些诡异...",
            "空气中弥漫着危险的气息...",
            "似乎有什么机关在等待...",
            "这里的一切都显得那么可疑...",
            "黑暗中似乎藏着什么..."
        ],
        DoorEnum.REWARD: [
            "金光闪闪，似乎有什么宝物...",
            "空气中飘来一丝财富的气息...",
            "这里似乎藏着什么好东西...",
            "金光若隐若现，引人遐想...",
            "似乎有什么宝物在等待..."
        ],
        DoorEnum.SHOP: [
            "商人的吆喝声传来...",
            "空气中飘来交易的气息...",
            "这里似乎有商人在此...",
            "商人的声音若隐若现...",
            "似乎有什么人在做买卖..."
        ]
    }
}

def get_mixed_door_hint(door_enums: list[DoorEnum]) -> str:
    """获取混合门提示"""
    if not door_enums:
        return ""
    if len(door_enums) == 1:
        return random.choice(HINT_CONFIGS["default"][door_enums[0].value])
    return random.choice(HINT_CONFIGS["combo"][frozenset(random.sample(door_enums,2))])
