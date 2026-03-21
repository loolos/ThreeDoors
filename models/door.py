"""门类型与门实例：陷阱/奖励/怪物/商店/事件门及提示配置。"""
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
        """根据枚举创建对应门类型的实例；若枚举未注册则抛出 ValueError。"""
        factory = {
            DoorEnum.TRAP: TrapDoor,
            DoorEnum.REWARD: RewardDoor,
            DoorEnum.MONSTER: MonsterDoor,
            DoorEnum.SHOP: ShopDoor,
            DoorEnum.EVENT: EventDoor,
        }.get(self)
        if factory is None:
            raise ValueError(f"Unsupported door type for create_instance: {self}")
        return factory(**kwargs)
    
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
            current_hp = int(max(1, self.controller.player.hp))
            max_spike_damage = max(10, int(current_hp * 0.1))
            spike_damage = random.randint(10, max_spike_damage)
            self.controller.player.take_damage(spike_damage)
            self.controller.add_message(f"地面的尖刺突然升起！受到了{spike_damage}点伤害！")
            
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
            entrance_quote = getattr(self.monster, "get_entrance_quote", lambda: None)()
            if entrance_quote:
                self.controller.add_message(f"{self.monster.name}：{entrance_quote}")
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

# 基础提示语配置：组合提示约5~15字，文采模糊，可暗指文学影视意象；配合怪物 tier+type 总长约25~40字
HINT_CONFIGS = {
    # 组合提示：文采与歧义兼具，暗示两种门类型（不点名出处）
    "combo": {
        frozenset({DoorEnum.MONSTER, DoorEnum.REWARD}): [
            "金堆上沉睡的守护者",
            "财光深处有呼吸起伏",
            "利爪与金币同眠",
            "洞穴尽头是宝光还是瞳光",
            "黄金与看守者的低吟",
            "宝库即猎场",
            "龙眠于财宝之侧",
            "取宝者须过利齿关",
        ],
        frozenset({DoorEnum.MONSTER, DoorEnum.SHOP}): [
            "代价写在灵魂的价签上",
            "契约与利齿，你选哪一个",
            "市集深处有非人的目光",
            "讨价还价时听见磨牙",
            "买与卖，谁在秤上",
            "交易完成时獠牙才露",
            "黑市抑或兽巢难辨",
            "议价声中藏低吼",
        ],
        frozenset({DoorEnum.MONSTER, DoorEnum.TRAP}): [
            "迷宫里不止有牛头",
            "机关与獠牙，谁先咬住你",
            "每一步都可能踩中死亡",
            "陷阱张开时猎食者也在靠近",
            "锁扣与利齿双重杀机",
            "暗处有机簧亦有喘息",
            "伏击与扑咬一线之隔",
            "地砖与喉音一同绷紧",
        ],
        frozenset({DoorEnum.TRAP, DoorEnum.REWARD}): [
            "宝光诱人，地砖在等你",
            "馈赠与绞索一线之隔",
            "金光下藏着机关的呼吸",
            "伸手取宝时听见咔嗒",
            "宝箱抑或绞架",
            "奖赏台与陷坑重叠",
            "地砖缝里有机簧与金光",
            "诱饵与杀机同放一匣",
        ],
        frozenset({DoorEnum.TRAP, DoorEnum.SHOP}): [
            "欢迎光临，地板会说话",
            "价码与弹簧一同绷紧",
            "交易完成时陷阱才启动",
            "柜台上摆着诱饵与杀机",
            "讨价抑或请君入瓮",
            "货架后藏着不止商品",
            "买卖声中夹着咔嗒",
            "黑店与牢笼一步之遥",
        ],
        frozenset({DoorEnum.SHOP, DoorEnum.REWARD}): [
            "讨价抑或白得馈赠",
            "商人的微笑里藏着赠礼",
            "买一送一的可能是命运",
            "柜台与宝堆只隔一扇门",
            "市集尽头有意外之财",
            "交易抑或馈赠难辨",
            "铜臭与金光暧昧交织",
            "成交时或许附赠横财",
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.MONSTER}): [
            "岔路遇人抑或遇兽",
            "命运翻开时利爪也在逼近",
            "际遇与猎杀一线之隔",
            "叙事声抑或磨牙",
            "舞台深处有非人的影子",
            "剧情翻页或扑脸",
            "奇遇尽头是蜕变还是吞噬",
            "故事的下一章藏在獠牙间",
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.TRAP}): [
            "岔路暗藏杀机",
            "际遇与暗算难辨",
            "命运之轮转动时有机关响",
            "剧情抑或陷坑",
            "转折点与绞索重叠",
            "线索抑或上弦",
            "故事在等你踩中",
            "奇遇的代价写在陷阱上",
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.REWARD}): [
            "命运的馈赠抑或玩笑",
            "故事尽头有金光",
            "际遇与财富难料",
            "剧情翻页时财宝也在等",
            "彩蛋抑或横财",
            "叙事与馈赠交织",
            "命运的价码在此结算",
            "奇遇的奖赏藏在下一幕",
        ],
        frozenset({DoorEnum.EVENT, DoorEnum.SHOP}): [
            "岔路口处有商人在等",
            "际遇抑或买卖难辨",
            "命运的价码可以议",
            "剧情与黑市只隔一扇门",
            "神秘人与商人的面孔重叠",
            "吆喝掺窃窃私语",
            "故事的下一章在柜台后",
            "议价声中藏着命运的密语",
        ],
    },
    # 缺省提示语（单门类型时使用，约6~10字）
    "default": {
        DoorEnum.MONSTER: ["黑暗中有物在动", "危险气息扑面", "何物在等待", "紧张弥漫", "可怕存在潜伏"],
        DoorEnum.TRAP: ["气氛诡异", "机关在等待", "一切可疑", "暗中藏机关", "杀机潜伏"],
        DoorEnum.REWARD: ["金光闪闪", "财富气息飘来", "宝物在等", "金光若隐", "馈赠诱人"],
        DoorEnum.SHOP: ["吆喝声传来", "交易气息", "商人在此", "叫卖若隐", "买卖声近"],
        DoorEnum.EVENT: ["神秘气息弥漫", "有事在发生", "命运齿轮转动", "不同寻常", "未知遭遇待"],
    },
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

_LAST_HINT_BY_KEY = {}


def _pick_rotating_hint(key, hints):
    """在同一提示池内尽量避免连续两次返回同一句。"""
    if not hints:
        return ""
    if len(hints) == 1:
        chosen = hints[0]
        _LAST_HINT_BY_KEY[key] = chosen
        return chosen
    last_hint = _LAST_HINT_BY_KEY.get(key)
    candidates = [hint for hint in hints if hint != last_hint]
    if not candidates:
        candidates = hints
    chosen = random.choice(candidates)
    _LAST_HINT_BY_KEY[key] = chosen
    return chosen


def get_mixed_door_hint(door_enums):
    """获取混合门提示"""
    if not door_enums:
        return ""
    if len(door_enums) == 1:
        single_enum = next(iter(door_enums))
        default_hints = HINT_CONFIGS["default"].get(
            single_enum, ["空气中弥漫着神秘的气息..."]
        )
        return _pick_rotating_hint(("default", single_enum), default_hints)
    door_enums_list = list(door_enums)
    selected_enums = []
    selected_enums.append(door_enums_list.pop(random.randint(0, len(door_enums_list) - 1)))
    selected_enums.append(door_enums_list.pop(random.randint(0, len(door_enums_list) - 1)))
    key = frozenset(selected_enums)
    hints = HINT_CONFIGS["combo"].get(key)
    if hints:
        return _pick_rotating_hint(("combo", key), hints)
    return _pick_rotating_hint(
        ("default", selected_enums[0]),
        HINT_CONFIGS["default"].get(selected_enums[0], ["空气中弥漫着神秘的气息..."]),
    )
