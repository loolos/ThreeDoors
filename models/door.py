import random
from .monster import get_random_monster
from typing import Optional, Dict, Any, List
from models.base_class import BaseClass
from models.monster import Monster
from models.shop import Shop
from enum import Enum
from models.items import create_random_item
from models.events import get_random_event, get_story_event_by_key, ELF_THIEF_NAME


class DoorEnum(Enum):
    """门类型枚举"""
    TRAP = "trap"
    REWARD = "reward"
    MONSTER = "monster"
    SHOP = "shop"
    EVENT = "event"
    
    def create_instance(self, **kwargs):
        """创建门实例"""
        return {
            DoorEnum.TRAP: TrapDoor,
            DoorEnum.REWARD: RewardDoor,
            DoorEnum.MONSTER: MonsterDoor,
            DoorEnum.SHOP: ShopDoor,
            DoorEnum.EVENT: EventDoor
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
        if "texture_key" in kwargs:
            self.texture_key = kwargs["texture_key"]
        else:
            self.texture_key = self._choose_texture_key()
        raw_extensions = kwargs.get("door_extensions", kwargs.get("extensions", []))
        self.door_extensions: List[Dict[str, Any]] = []
        for ext in raw_extensions:
            if isinstance(ext, dict):
                self.door_extensions.append(dict(ext))

    def _choose_texture_key(self) -> str:
        return random.choice(FRONT_DOOR_TEXTURES)

    def generate_hint(self) -> None:
        """生成门的提示"""
        raise NotImplementedError("子类必须实现generate_hint方法")

    def generate_non_monster_door_hint(self) -> None:
        fake_door_enum = random.choice([enum for enum in DoorEnum if enum != self.enum])
        self.hint = get_mixed_door_hint(frozenset([self.enum, fake_door_enum]))
        if fake_door_enum == DoorEnum.MONSTER:
            fake_monster = get_random_monster(
                current_round=self.controller.round_count,
                player=getattr(self.controller, "player", None),
                unlocked_tier=getattr(self.controller, "unlocked_monster_tier", 1),
            )
            tier_hint, type_hint = fake_monster.get_hints()
            self.hint = f"{self.hint}, {tier_hint}, {type_hint}"

    def enter(self) -> bool:
        """进入门"""
        raise NotImplementedError("子类必须实现enter方法")

    def add_door_extension(self, extension_config: Dict[str, Any]) -> None:
        """门扩展窗口：统一承载事件对门行为的改写。"""
        if isinstance(extension_config, dict):
            self.door_extensions.append(extension_config)

    def add_extension(self, extension_config: Dict[str, Any]) -> None:
        """兼容别名。"""
        self.add_door_extension(extension_config)

    def run_door_extensions(self, hook: str, **kwargs) -> List[Dict[str, Any]]:
        """执行门扩展并返回每个扩展的结果字典。"""
        if not self.door_extensions:
            return []
        story = getattr(self.controller, "story", None)
        if story is None or not hasattr(story, "apply_door_extension"):
            return []
        outputs: List[Dict[str, Any]] = []
        for ext in self.door_extensions:
            result = story.apply_door_extension(door=self, extension=ext, hook=hook, **kwargs)
            if isinstance(result, dict):
                outputs.append(result)
        return outputs
    
    


from models.status import StatusName

class TrapDoor(Door):
    """陷阱门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.TRAP
        super()._initialize(**kwargs)
        # Default damage for basic traps, but we'll use trap types now
        self.damage = kwargs.get('damage', 10)
        self.generate_hint()
    

    def generate_hint(self) -> None:
        if not self.hint:
            self.generate_non_monster_door_hint()
            
    def enter(self) -> bool:
        ext_outputs = self.run_door_extensions(hook="before_enter")
        for out in ext_outputs:
            replacement_door = out.get("replacement_door")
            if replacement_door is not None and hasattr(replacement_door, "enter"):
                return bool(replacement_door.enter())
            if out.get("skip_default_enter"):
                return True
        self.controller.add_message("你触发了机关！")
        
        trap_type = random.choice(['spike', 'poison', 'gold', 'weakness'])
        
        if trap_type == 'spike':
            self.controller.player.take_damage(self.damage)
            self.controller.add_message(f"地面的尖刺突然升起！受到了{self.damage}点伤害！")
            
        elif trap_type == 'poison':
            duration = 3
            self.controller.player.apply_status(StatusName.FIELD_POISON.create_instance(duration=duration, target=self.controller.player))
            self.controller.add_message(f"一股毒气喷涌而出！你中毒了，持续{duration}回合。")
            
        elif trap_type == 'gold':
            lost_gold = random.randint(10, 30)
            current_gold = self.controller.player.gold
            actual_loss = min(current_gold, lost_gold)
            if actual_loss > 0:
                self.controller.player.gold -= actual_loss
                self.controller.add_message(f"一群地精突然出现抢走了你的钱袋！损失了 {actual_loss} 金币！")
            else:
                self.controller.add_message("一群地精试图抢劫你，但发现你是个穷光蛋，骂骂咧咧地走了。")
                
        elif trap_type == 'weakness':
            duration = 3
            self.controller.player.apply_status(StatusName.WEAK.create_instance(duration=duration, target=self.controller.player))
            self.controller.add_message(f"你被虚弱诅咒击中！攻击力降低，持续{duration}回合。")
            
        return True


class RewardDoor(Door):
    """奖励门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.REWARD
        super()._initialize(**kwargs)
        self.reward = kwargs.get('reward') # allow None to trigger random generation
        if not self.reward:
             self.reward = self._generate_random_reward()
        self.generate_hint()

    def _generate_random_reward(self):
        """生成随机奖励：金币适度减少，物品种类多样化"""
        import models.items as items_module
        reward_type = random.choice(['gold', 'item', 'mixed'])
        rewards = {}

        if reward_type == 'gold':
            rewards['gold'] = random.randint(8, 22)
        elif reward_type == 'mixed':
            rewards['gold'] = random.randint(4, 14)
            rewards[items_module.create_reward_door_item()] = 1
            if random.random() < 0.35:
                rewards[items_module.create_reward_door_item()] = 1
        else:
            item = items_module.create_reward_door_item()
            rewards[item] = 1
            if random.random() < 0.4:
                rewards[items_module.create_reward_door_item()] = 1
        return rewards
    
    def generate_hint(self) -> None:
        self.generate_non_monster_door_hint()

    def enter(self) -> bool:
        self.run_door_extensions(hook="before_enter")
        if getattr(self, "elf_side_reward", False):
            story = getattr(self.controller, "story", None)
            rel = int(getattr(story, "elf_relation", 0)) if story else 0
            if rel >= 0:
                self.controller.add_message(
                    "一抹银影从门缝里闪出，与你擦肩而过时往你怀里塞了把东西：'顺来的，懒得拿。' 你低头一看，正是门里该有的那份。"
                )
            else:
                self.controller.add_message(
                    "你推门的瞬间，一道银光从门内掠出。她揣着鼓鼓的兜冲你摆摆手：'谢了啊，下次有这种好事记得叫我。' 门里只剩一地包装纸。"
                )
                self.reward = {}
        for item, amount in self.reward.items():
            if item == 'gold':
                self.controller.player.gold += amount
                self.controller.add_message(f"你获得了{amount}金币！")
            else:
                # Assuming item is an Item object given the key use in _generate_random_reward
                # Current logic: controller.player.add_item(item, amount)
                # But wait, add_item(item, amount) signature? 
                # Checking player.py: add_item(self, item) -> takes 1 arg (plus self).
                # Wait, existing code said: self.controller.player.add_item(item, amount)
                # Let's check player.py again. get_state uses p.inventory.items().
                # player.add_item(item) just appends.
                # So the existing code `self.controller.player.add_item(item, amount)` MIGHT BE WRONG or `item` was a string name before?
                # Previous RewardDoor: self.reward = {'gold': 50} (Default). 
                # If it had items, it would fail if add_item only takes 1 arg.
                # Let's assume for my new code: `item` is an Item object.
                # I will call item.acquire(player=self.controller.player) which handles logic.
                
                # Check if item is string (legacy support) or Item object
                import models.items
                if isinstance(item, models.items.Item):
                    # Use the Acquire logic so it auto-uses consumables or adds to inventory
                    # We repeat `amount` times
                    for _ in range(amount):
                        self.controller.add_message(f"获得道具：{item.name}")
                        item.acquire(player=self.controller.player)
                else:
                    # Fallback for string keys if any exist (though I suggest avoiding them now)
                    # Implementation for string-based items is likely missing in player.add_item
                    pass
        return True


class MonsterDoor(Door):
    """怪物门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.MONSTER
        super()._initialize(**kwargs)
        self.battle_extensions = list(kwargs.get("battle_extensions", []))
        if 'monster' in kwargs:
            self.monster = kwargs['monster']
        else:
            self.monster = get_random_monster(
                current_round=self.controller.round_count,
                player=getattr(self.controller, "player", None),
                unlocked_tier=getattr(self.controller, "unlocked_monster_tier", 1),
            )
        self.generate_hint()
    
    def generate_hint(self) -> None:
        fake_door_enum = random.choice([enum for enum in DoorEnum if enum != self.enum])
        tier_hint, type_hint = self.monster.get_hints()
        self.hint = f"{get_mixed_door_hint(frozenset([self.enum, fake_door_enum]))}, {tier_hint}, {type_hint}"

    def add_battle_extension(self, extension_config: Dict[str, Any]) -> None:
        """怪物门战斗扩展窗口：普通怪物门可保持为空。"""
        if isinstance(extension_config, dict):
            self.battle_extensions.append(extension_config)
    
    def enter(self) -> bool:
        self.run_door_extensions(hook="before_enter")
        if not self.monster:
            return False
        self.controller.current_monster = self.monster
        # 只加载当前怪物门声明的扩展，普通怪物门默认无扩展。
        self.controller.current_battle_extensions = self.battle_extensions
        if getattr(self.monster, "elf_side_story", False):
            self.controller.add_message(f"{ELF_THIEF_NAME}正与一头{self.monster.name}缠斗。她瞥见你：'愣着干什么？帮忙还是跑，选一个。'")
        else:
            self.controller.add_message(f"你遇到了 {self.monster.name}！")
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
        self.run_door_extensions(hook="before_enter")
        forced_key = getattr(self, "story_forced_event_key", None)
        if forced_key:
            event = get_story_event_by_key(forced_key, self.controller)
            if event is not None:
                self.controller.current_event = event
                self.controller.scene_manager.go_to("event_scene")
                return True
        if not self.shop:
            return False
        self.controller.current_shop = self.shop
        return True


class EventDoor(Door):
    """事件门"""
    
    def _initialize(self, **kwargs) -> None:
        self.enum = DoorEnum.EVENT
        super()._initialize(**kwargs)
        self.generate_hint()
    
    def generate_hint(self) -> None:
        self.generate_non_monster_door_hint()
    
    def enter(self) -> bool:
        self.run_door_extensions(hook="before_enter")
        forced_key = getattr(self, "story_forced_event_key", None)
        if forced_key:
            event = get_story_event_by_key(forced_key, self.controller) or get_random_event(self.controller)
        else:
            event = get_random_event(self.controller)
        self.controller.current_event = event
        # 记录本次事件类型，供后续非后续事件门去重
        if event and hasattr(self.controller, "recent_event_classes"):
            recents = self.controller.recent_event_classes
            recents.append(event.__class__.__name__)
            from models.events import RECENT_EVENT_WINDOW
            if len(recents) > RECENT_EVENT_WINDOW:
                self.controller.recent_event_classes = recents[-RECENT_EVENT_WINDOW:]
        self.controller.scene_manager.go_to("event_scene")
        return True

# 基础提示语配置：每条组合提示必须模糊暗示两种门类型，避免只偏向一种
HINT_CONFIGS = {
    # 组合提示：格式为「可能是A…也可能是B…」或「A与B交织」
    "combo": {
        frozenset({DoorEnum.MONSTER, DoorEnum.REWARD}): [
            "野兽的咆哮中夹杂着金币的叮当声",
            "也许是猛兽，也许是宝箱——危险与机遇难辨",
            "黑暗中似有财宝闪光，也似有爪牙潜伏",
            "猛兽的嘶吼与财宝的诱惑交织",
            "凶险与馈赠，一念之隔"
        ],
        frozenset({DoorEnum.MONSTER, DoorEnum.SHOP}): [
            "商人的吆喝声中藏着野兽的咆哮",
            "也许是集市，也许是兽巢——吆喝与低吼难分",
            "交易的气息与血腥味混杂",
            "猛兽的怒吼与商人的叫卖交织",
            "买卖与搏命，一步之遥"
        ],
        frozenset({DoorEnum.MONSTER, DoorEnum.TRAP}): [
            "猛兽与陷阱的双重威胁",
            "也许是怪物，也许是机关——杀机四伏",
            "野兽的咆哮与机关的咔嗒声交织",
            "黑暗中藏着利齿或尖刺",
            "伏击与陷阱，双重危机"
        ],
        frozenset({DoorEnum.TRAP, DoorEnum.REWARD}): [
            "机关与宝藏并存",
            "也许是陷阱，也许是财宝——险中求富贵",
            "机关的咔嗒声中夹杂着金币的叮当声",
            "危险的气息里似乎有宝光闪烁",
            "杀机与馈赠，一线之隔"
        ],
        frozenset({DoorEnum.TRAP, DoorEnum.SHOP}): [
            "商人的声音中似乎藏着机关",
            "也许是店铺，也许是陷阱——买卖与杀机难辨",
            "交易声中夹杂着机关的咔嗒声",
            "商人的吆喝与机关的咔嗒声交织",
            "买卖与暗算，真假难辨"
        ],
        frozenset({DoorEnum.SHOP, DoorEnum.REWARD}): [
            "商人的吆喝声中夹杂着金币的叮当声",
            "也许是店铺，也许是宝库——交易与馈赠难辨",
            "买卖声中似乎有宝物的光芒",
            "商人的声音与财宝的诱惑交织",
            "讨价还价或是白捡，一念之差"
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.MONSTER}): [
            "奇怪的声音中夹杂着野兽的咆哮",
            "也许是奇遇，也许是猛兽——未知与危险并存",
            "命运的岔路口，可能遇人也可能遇兽",
            "混乱的气息中藏着变故或利爪",
            "际遇与猎杀，一步之差"
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.TRAP}): [
            "未知的气息中带着一丝危险",
            "也许是奇遇，也许是机关——命运与杀机难辨",
            "命运的岔路口暗藏杀机",
            "奇怪的氛围中似乎有陷阱或转机",
            "际遇与暗算，真假难辨"
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.REWARD}): [
            "神秘的气息中透着宝物的光芒",
            "也许是奇遇，也许是财宝——未知与馈赠并存",
            "命运的馈赠还是玩笑？",
            "奇怪的事情似乎伴随着奖励或代价",
            "际遇与财富，福祸难料"
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.SHOP}): [
            "神秘人似乎在和商人交易",
            "也许是事件，也许是店铺——际遇与买卖难辨",
            "未知的事件与买卖并存",
            "商人的吆喝声中夹杂着窃窃私语",
            "奇遇与交易，一念之间"
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
        ],
        DoorEnum.EVENT: [
            "空气中弥漫着神秘的气息...",
            "似乎有什么事情正在发生...",
            "命运的齿轮开始转动...",
            "这里感觉有些不同寻常...",
            "未知的遭遇在等待..."
        ]
    }
}

# 门正面贴图池：与门后内容无关，纯随机外观
FRONT_DOOR_TEXTURES = [
    "door_oak",
    "door_obsidian",
    "door_vine",
    "door_rune",
    "door_iron",
    "door_bone",
]

def get_mixed_door_hint(door_enums):
    """获取混合门提示"""
    if not door_enums:
        return ""
    if len(door_enums) == 1:
        single_enum = next(iter(door_enums))
        return random.choice(HINT_CONFIGS["default"][single_enum])
    door_enums_list = list(door_enums)
    selected_enums = []
    selected_enums.append(door_enums_list.pop(random.randint(0, len(door_enums_list) - 1)))
    selected_enums.append(door_enums_list.pop(random.randint(0, len(door_enums_list) - 1)))
    key = frozenset(selected_enums)
    hints = HINT_CONFIGS["combo"].get(key)
    if hints:
        return random.choice(hints)
    return random.choice(HINT_CONFIGS["default"].get(selected_enums[0], ["空气中弥漫着神秘的气息..."]))
