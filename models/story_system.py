import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple

from models.items import create_random_item
from models.status import StatusName


@dataclass
class PendingConsequence:
    """待触发的后续影响。"""

    consequence_id: str
    source_flag: str
    effect_key: str
    description: str = ""
    chance: float = 0.25
    trigger_door_types: Set[str] = field(default_factory=set)
    trigger_monsters: Set[str] = field(default_factory=set)
    min_round: Optional[int] = None
    max_round: Optional[int] = None
    priority: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    required_flags: Set[str] = field(default_factory=set)
    forbidden_flags: Set[str] = field(default_factory=set)

    def matches(self, door: Any, round_count: int, story_flags: Set[str]) -> bool:
        door_type = getattr(getattr(door, "enum", None), "name", "")
        monster_name = getattr(getattr(door, "monster", None), "name", "")
        if self.trigger_door_types and door_type not in self.trigger_door_types:
            return False
        if self.trigger_monsters and monster_name not in self.trigger_monsters:
            return False
        if self.min_round is not None and round_count < self.min_round:
            return False
        if self.max_round is not None and round_count > self.max_round:
            return False
        if self.required_flags and not self.required_flags.issubset(story_flags):
            return False
        if self.forbidden_flags and self.forbidden_flags.intersection(story_flags):
            return False
        return True


class StorySystem:
    """记录历史选择、道德值与后续影响。"""

    HIGH_MORAL = 30
    LOW_MORAL = -30

    HIGH_MORAL_MONSTERS = {"树人", "天使", "创世神官", "幽灵", "精灵法师"}
    LOW_MORAL_MONSTERS = {"土匪", "狼人", "食人魔", "冥界使者", "暗影刺客"}

    def __init__(self, controller: Any):
        self.controller = controller
        self.moral_score = 0
        self.choice_flags: Set[str] = set()
        self.story_tags: Set[str] = set()
        self.pending_consequences: Dict[str, PendingConsequence] = {}
        self.consumed_consequences: Set[str] = set()
        self.effect_handlers: Dict[str, Callable[[PendingConsequence, Any], Tuple[bool, Any]]] = {}

    def register_effect_handler(
        self,
        effect_key: str,
        handler: Callable[[PendingConsequence, Any], Tuple[bool, Any]],
    ) -> None:
        """扩展端口：允许外部注册新的效果处理函数。"""
        self.effect_handlers[effect_key] = handler

    def add_story_tag(self, tag: str) -> None:
        if tag:
            self.story_tags.add(tag)

    def register_choice(
        self,
        choice_flag: str,
        moral_delta: int = 0,
        consequences: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> None:
        self.choice_flags.add(choice_flag)
        self.story_tags.add(f"choice:{choice_flag}")
        if moral_delta:
            self.moral_score = max(-100, min(100, self.moral_score + moral_delta))
        if not consequences:
            return
        for cfg in consequences:
            self.register_consequence(choice_flag=choice_flag, **cfg)

    def register_consequence(
        self,
        choice_flag: str,
        consequence_id: str,
        effect_key: str,
        description: str = "",
        chance: float = 0.25,
        trigger_door_types: Optional[Iterable[str]] = None,
        trigger_monsters: Optional[Iterable[str]] = None,
        min_round: Optional[int] = None,
        max_round: Optional[int] = None,
        priority: int = 0,
        payload: Optional[Dict[str, Any]] = None,
        required_flags: Optional[Iterable[str]] = None,
        forbidden_flags: Optional[Iterable[str]] = None,
    ) -> bool:
        if consequence_id in self.pending_consequences or consequence_id in self.consumed_consequences:
            return False
        self.pending_consequences[consequence_id] = PendingConsequence(
            consequence_id=consequence_id,
            source_flag=choice_flag,
            effect_key=effect_key,
            description=description,
            chance=max(0.0, min(1.0, chance)),
            trigger_door_types=set(trigger_door_types or []),
            trigger_monsters=set(trigger_monsters or []),
            min_round=min_round,
            max_round=max_round,
            priority=priority,
            payload=payload or {},
            required_flags=set(required_flags or []),
            forbidden_flags=set(forbidden_flags or []),
        )
        return True

    def apply_pre_enter_checks(self, door: Any) -> Any:
        """选门后、入门前触发检查：先后续影响，再道德影响。"""
        door = self._trigger_pending_consequence(door)
        door = self._trigger_moral_influence(door)
        return door

    def _trigger_pending_consequence(self, door: Any) -> Any:
        round_count = getattr(self.controller, "round_count", 0)
        story_flags = self.choice_flags.union(self.story_tags)
        candidates = [
            c
            for c in self.pending_consequences.values()
            if c.matches(door=door, round_count=round_count, story_flags=story_flags)
        ]
        if not candidates:
            return door

        # 高优先级先尝试，同优先级随机化。
        random.shuffle(candidates)
        candidates.sort(key=lambda c: c.priority, reverse=True)
        current_door = door
        applied_any = False
        for consequence in candidates:
            if random.random() > consequence.chance:
                continue
            applied, new_door = self._apply_effect(consequence, current_door)
            if applied:
                self.consumed_consequences.add(consequence.consequence_id)
                self.story_tags.add(f"consumed:{consequence.consequence_id}")
                del self.pending_consequences[consequence.consequence_id]
                self._queue_chain_followups(consequence)
                current_door = new_door
                applied_any = True
        return current_door if applied_any else door

    def _trigger_moral_influence(self, door: Any) -> Any:
        monster = getattr(door, "monster", None)
        if not monster:
            return door

        # 道德影响不应频发。
        if random.random() > 0.22:
            return door

        name = getattr(monster, "name", "")
        moral = self.moral_score
        if moral >= self.HIGH_MORAL:
            if name in self.HIGH_MORAL_MONSTERS:
                if random.random() < 0.5:
                    self.controller.add_message(f"{name} 感知到你的善意，献上宝物后离开。")
                    return self._make_reward_door(gold=random.randint(35, 80), include_item=True, hint="善行回响")
                monster.hp = max(1, int(monster.hp * 0.8))
                monster.atk = max(1, int(monster.atk * 0.85))
                self.controller.add_message(f"{name} 因敬意收敛敌意，实力被压制。")
            elif name in self.LOW_MORAL_MONSTERS and random.random() < 0.5:
                monster.hp = max(1, int(monster.hp * 1.15))
                monster.atk = max(1, int(monster.atk * 1.2))
                self.controller.add_message(f"{name} 认为你心慈手软，攻势更凶猛。")
        elif moral <= self.LOW_MORAL:
            if name in self.LOW_MORAL_MONSTERS:
                if random.random() < 0.45:
                    self.controller.add_message(f"{name} 认出你的恶名，主动献上买路财。")
                    return self._make_reward_door(gold=random.randint(30, 75), include_item=False, hint="恶名震慑")
                monster.atk = max(1, int(monster.atk * 0.9))
                self.controller.add_message(f"{name} 对你心生忌惮，出手反而迟疑。")
            elif name in self.HIGH_MORAL_MONSTERS and random.random() < 0.6:
                monster.hp = max(1, int(monster.hp * 1.18))
                monster.atk = max(1, int(monster.atk * 1.22))
                self.controller.add_message(f"{name} 厌恶你的作风，愤怒地强化了自己。")
        return door

    def _apply_effect(self, consequence: PendingConsequence, door: Any) -> Tuple[bool, Any]:
        effect = consequence.effect_key
        payload = consequence.payload

        custom_handler = self.effect_handlers.get(effect)
        if custom_handler:
            return custom_handler(consequence, door)

        if effect == "villagers_gift":
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    "你过往的行为被人记住了，对方直接把宝物交给了你。",
                )
            )
            return True, self._make_reward_door(
                gold=payload.get("gold", random.randint(50, 100)),
                include_item=payload.get("include_item", True),
                hint=payload.get("hint", "旧事回响"),
            )

        if effect == "revenge_ambush":
            force_hunter = payload.get("force_hunter", True)
            convert_to_hunter = payload.get("convert_to_hunter", True)
            monster = getattr(door, "monster", None)
            if force_hunter or (monster is None and convert_to_hunter):
                hunter = self._create_hunter_monster()
                hp_ratio = payload.get("hp_ratio", 1.25)
                atk_ratio = payload.get("atk_ratio", 1.2)
                if monster:
                    hunter.hp = max(hunter.hp, int(monster.hp * hp_ratio))
                    hunter.atk = max(hunter.atk, int(monster.atk * atk_ratio))
                self.controller.add_message(
                    self._resolve_message(
                        payload,
                        "message",
                        "门后等待你的不是原住怪物，而是一路追杀而来的猎手。",
                    )
                )
                from models.door import DoorEnum

                hunter_hint = payload.get("hunter_hint", "脚步声不是偶然，那是追猎者在校准你的呼吸。")
                return True, DoorEnum.MONSTER.create_instance(
                    controller=self.controller,
                    monster=hunter,
                    hint=hunter_hint,
                )
            if monster:
                hp_ratio = payload.get("hp_ratio", 1.25)
                atk_ratio = payload.get("atk_ratio", 1.2)
                monster.hp = max(1, int(monster.hp * hp_ratio))
                monster.atk = max(1, int(monster.atk * atk_ratio))
                self.controller.add_message(
                    self._resolve_message(payload, "message", "旧怨者设下伏击，怪物获得强化。")
                )
                return True, door
            dmg = payload.get("damage", random.randint(5, 12))
            self.controller.player.take_damage(dmg)
            self.controller.add_message(
                self._resolve_message(payload, "message", f"你遭到报复，受到 {dmg} 点伤害。")
            )
            return True, door

        if effect == "guard_reward":
            gold = payload.get("gold", random.randint(20, 60))
            heal = payload.get("heal", 0)
            self.controller.player.gold += gold
            if heal > 0:
                self.controller.player.heal(heal)
            self.controller.add_message(
                self._resolve_message(payload, "message", f"守卫感谢你的协助，奖励了你 {gold} 金币。")
            )
            return True, door

        if effect == "black_market_discount":
            if getattr(getattr(door, "enum", None), "name", "") != "SHOP":
                return False, door
            ratio = payload.get("ratio", 0.7)
            shop_targets = self._get_shop_targets(door)
            if not shop_targets:
                return False, door
            preview = self._apply_shop_ratio(shop_targets, ratio)
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    f"商人认出你是熟客同路人，当前货架即时降价（如 {preview}）。",
                )
            )
            return True, door

        if effect == "black_market_markup":
            if getattr(getattr(door, "enum", None), "name", "") != "SHOP":
                return False, door
            ratio = payload.get("ratio", 1.4)
            shop_targets = self._get_shop_targets(door)
            if not shop_targets:
                return False, door
            preview = self._apply_shop_ratio(shop_targets, ratio)
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    f"商人认出你惹过他们的人，当前货架即时涨价（如 {preview}）。",
                )
            )
            return True, door

        if effect == "shrine_blessing":
            if getattr(getattr(door, "enum", None), "name", "") == "TRAP":
                self.controller.add_message(
                    self._resolve_message(payload, "message", "圣坛余辉保护了你，陷阱化作馈赠。")
                )
                return True, self._make_reward_door(gold=random.randint(25, 65), include_item=False, hint="神佑余辉")
            monster = getattr(door, "monster", None)
            if monster:
                monster.atk = max(1, int(monster.atk * 0.82))
                self.controller.add_message(
                    self._resolve_message(payload, "message", "你受到神佑，敌人的攻势被压制。")
                )
                return True, door
            return False, door

        if effect == "shrine_curse":
            duration = payload.get("duration", 2)
            self.controller.player.apply_status(
                StatusName.WEAK.create_instance(duration=duration, target=self.controller.player)
            )
            self.controller.add_message(
                self._resolve_message(payload, "message", f"诅咒追上了你，陷入虚弱 {duration} 回合。")
            )
            return True, door

        if effect == "atk_training":
            delta = payload.get("delta", 2)
            self.controller.player.change_base_atk(delta)
            self.controller.add_message(
                self._resolve_message(payload, "message", "这段经历让你学会了更狠的出手方式。")
            )
            return True, door

        if effect == "lose_gold":
            lost = min(self.controller.player.gold, payload.get("amount", random.randint(15, 45)))
            self.controller.player.gold -= lost
            self.controller.add_message(
                self._resolve_message(payload, "message", f"旧账找上门来，你被迫赔了 {lost} 金币。")
            )
            return True, door

        return False, door

    def _queue_chain_followups(self, consequence: PendingConsequence) -> None:
        """链式扩展端口：某个后续触发后再挂新的后续影响。"""
        followups = consequence.payload.get("chain_followups", [])
        if not isinstance(followups, list):
            return
        for cfg in followups:
            if not isinstance(cfg, dict):
                continue
            followup_cfg = dict(cfg)
            if "choice_flag" not in followup_cfg:
                followup_cfg["choice_flag"] = f"chain:{consequence.consequence_id}"
            try:
                self.register_consequence(**followup_cfg)
            except TypeError:
                # 配置不完整时忽略，避免影响主流程
                continue

    def _resolve_message(self, payload: Dict[str, Any], key: str, fallback: str) -> str:
        msg = payload.get(key, fallback)
        if isinstance(msg, list):
            valid = [m for m in msg if isinstance(m, str) and m.strip()]
            return random.choice(valid) if valid else fallback
        return msg if isinstance(msg, str) and msg.strip() else fallback

    def _make_reward_door(self, gold: int, include_item: bool, hint: str = "") -> Any:
        from models.door import DoorEnum

        reward: Dict[Any, int] = {"gold": max(0, gold)}
        if include_item:
            reward[create_random_item()] = 1
        return DoorEnum.REWARD.create_instance(
            controller=self.controller,
            reward=reward,
            hint=hint or "命运的馈赠",
        )

    def _create_hunter_monster(self):
        from models.monster import Monster

        round_count = getattr(self.controller, "round_count", 0)
        if round_count <= 10:
            return Monster(name="土匪", hp=26, atk=6, tier=2)
        if round_count <= 20:
            return Monster(name="狼人", hp=38, atk=8, tier=3)
        return Monster(name="暗影刺客", hp=56, atk=16, tier=4)

    def _get_shop_targets(self, door: Any):
        shops = []
        current_shop = getattr(self.controller, "current_shop", None)
        if current_shop:
            shops.append(current_shop)
        door_shop = getattr(door, "shop", None)
        if door_shop and door_shop not in shops:
            shops.append(door_shop)
        return shops

    def _apply_shop_ratio(self, shops, ratio: float) -> str:
        preview = "无商品"
        for shop in shops:
            if getattr(shop, "shop_items", None):
                first_item = shop.shop_items[0]
                before = first_item.cost
                for item in shop.shop_items:
                    item.cost = max(1, int(item.cost * ratio))
                after = first_item.cost
                preview = f"{first_item.name}: {before}G→{after}G"
        return preview
