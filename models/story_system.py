import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Optional, Set, Tuple

from models.game_config import GameConfig
from models.door import DoorEnum
from models.items import (
    AttackUpScroll,
    Barrier,
    FlyingHammer,
    GiantScroll,
    HealingScroll,
    ImmuneScroll,
    ReviveScroll,
    create_random_item,
)
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
    force_on_expire: bool = False
    force_door_type: Optional[str] = None
    priority: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    required_flags: Set[str] = field(default_factory=set)
    forbidden_flags: Set[str] = field(default_factory=set)

    def _flags_match(self, story_flags: Set[str]) -> bool:
        if self.required_flags and not self.required_flags.issubset(story_flags):
            return False
        if self.forbidden_flags and self.forbidden_flags.intersection(story_flags):
            return False
        return True

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
        return self._flags_match(story_flags)

    def should_force_trigger(self, round_count: int, story_flags: Set[str]) -> bool:
        """达到截止轮次后可强制触发，不再受门类型和概率限制。"""
        if not self.force_on_expire or self.max_round is None:
            return False
        if self.min_round is not None and round_count < self.min_round:
            return False
        if round_count < self.max_round:
            return False
        return self._flags_match(story_flags)


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

    def _get_progress_stage(self) -> int:
        """按回合与玩家基础攻击估算后续影响强度阶段。"""
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        player = getattr(self.controller, "player", None)
        base_atk = 5
        if player is not None:
            base_atk = max(1, int(getattr(player, "_atk", getattr(player, "atk", 5))))
        score = round_count * 2 + base_atk * 4
        if score >= 130:
            return 3
        if score >= 90:
            return 2
        if score >= 55:
            return 1
        return 0

    def _scale_amount(self, amount: int, *, positive: bool, aggressive: bool = False) -> int:
        """按阶段缩放数值，保证前期与旧行为一致。"""
        stage = self._get_progress_stage()
        if stage <= 0:
            return int(amount)
        scale_steps = (1.0, 1.1, 1.22, 1.35) if positive else (1.0, 1.12, 1.25, 1.4)
        scale = scale_steps[min(stage, len(scale_steps) - 1)]
        if aggressive:
            scale += stage * 0.03
        scaled = int(round(amount * scale))
        if amount >= 0:
            return max(1, scaled)
        return min(-1, scaled)

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
        force_on_expire: bool = False,
        force_door_type: Optional[str] = None,
        delay_rounds: int = 0,
        priority: int = 0,
        payload: Optional[Dict[str, Any]] = None,
        required_flags: Optional[Iterable[str]] = None,
        forbidden_flags: Optional[Iterable[str]] = None,
    ) -> bool:
        if consequence_id in self.pending_consequences or consequence_id in self.consumed_consequences:
            return False

        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        try:
            delay_rounds = max(0, int(delay_rounds))
        except (TypeError, ValueError):
            delay_rounds = 0
        if delay_rounds:
            delayed_round = current_round + delay_rounds
            if min_round is None:
                min_round = delayed_round
            else:
                try:
                    min_round = max(int(min_round), delayed_round)
                except (TypeError, ValueError):
                    min_round = delayed_round

        normalized_force_door_type = None
        if isinstance(force_door_type, str):
            candidate = force_door_type.strip().upper()
            if candidate in DoorEnum.__members__:
                normalized_force_door_type = candidate

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
            force_on_expire=bool(force_on_expire),
            force_door_type=normalized_force_door_type,
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
        all_pending = list(self.pending_consequences.values())
        forced_candidates = [
            c for c in all_pending if c.should_force_trigger(round_count=round_count, story_flags=story_flags)
        ]
        if forced_candidates:
            forced_candidates.sort(
                key=lambda c: (
                    c.max_round if c.max_round is not None else 10**9,
                    -int(c.priority),
                    c.consequence_id,
                )
            )
            chosen = forced_candidates[0]
            apply_door = self._coerce_forced_door(door, chosen)
            return self._apply_chosen_consequence(chosen=chosen, door=apply_door, fallback_door=door, forced=True)

        candidates = [
            c
            for c in all_pending
            if c.matches(door=door, round_count=round_count, story_flags=story_flags)
        ]
        door_type = getattr(getattr(door, "enum", None), "name", "")

        if not candidates:
            return door

        # 事件门且候选 <5：按配置概率直接跳过门改写，沿用原门
        if door_type == "EVENT" and len(candidates) < 5:
            if random.random() < GameConfig.EVENT_DOOR_SKIP_REWRITE_CHANCE:
                return door

        # 按权重只抽取一条后果并应用（force_story_event 享有更高权重）
        weights = []
        for c in candidates:
            w = max(0.0, float(c.chance))
            if c.effect_key == "force_story_event":
                w *= GameConfig.FORCE_STORY_EVENT_WEIGHT_BONUS
            weights.append(w)
        total = sum(weights)
        if total <= 0:
            return door
        roll = random.uniform(0, total)
        acc = 0.0
        chosen = None
        for c, w in zip(candidates, weights):
            acc += w
            if roll <= acc:
                chosen = c
                break
        if chosen is None:
            chosen = candidates[-1]
        return self._apply_chosen_consequence(chosen=chosen, door=door, fallback_door=door, forced=False)

    def _coerce_forced_door(self, door: Any, consequence: PendingConsequence) -> Any:
        target_type = consequence.force_door_type
        if not target_type:
            return door
        current_type = getattr(getattr(door, "enum", None), "name", "")
        if current_type == target_type:
            return door
        target_enum = DoorEnum.__members__.get(target_type)
        if target_enum is None:
            return door
        forced_door = target_enum.create_instance(controller=self.controller)
        hint = consequence.payload.get("forced_door_hint")
        if isinstance(hint, str) and hint.strip():
            forced_door.hint = hint.strip()
        return forced_door

    def _apply_chosen_consequence(
        self,
        chosen: PendingConsequence,
        door: Any,
        fallback_door: Any,
        forced: bool,
    ) -> Any:
        trigger_message = self._build_trigger_message(chosen)
        if trigger_message:
            self.controller.add_message(trigger_message)
        applied, new_door = self._apply_effect(chosen, door)
        if forced and not applied and chosen.force_door_type:
            # 截止轮次的强制触发至少要保证门被改写到目标类型。
            applied, new_door = True, door
        if applied:
            self._apply_payload_metric_deltas(chosen)
            if not self._should_defer_consumption(chosen, new_door):
                self._consume_consequence(chosen)
            return new_door
        return fallback_door

    def _apply_payload_metric_deltas(self, consequence: PendingConsequence) -> None:
        """扩展端口：允许后果在触发时修改剧情指标（如木偶邪恶值）。"""
        payload = consequence.payload or {}
        if "evil_value_delta" not in payload:
            return
        try:
            delta = int(payload.get("evil_value_delta", 0))
        except (TypeError, ValueError):
            return
        if delta == 0:
            return
        current = int(getattr(self, "puppet_evil_value", 55))
        next_val = max(0, min(100, current + delta))
        self.puppet_evil_value = next_val
        self.story_tags.add(f"puppet_evil_bucket:{(next_val // 10) * 10}")
        if delta > 0:
            self.controller.add_message(f"木偶邪恶值上升至 {next_val}/100。")
        else:
            self.controller.add_message(f"木偶邪恶值下降至 {next_val}/100。")

    def _consume_consequence(self, consequence: PendingConsequence) -> None:
        cid = consequence.consequence_id
        self.consumed_consequences.add(cid)
        self.story_tags.add(f"consumed:{cid}")
        self.pending_consequences.pop(cid, None)
        self._queue_chain_followups(consequence)

    def _should_defer_consumption(self, consequence: PendingConsequence, door: Any) -> bool:
        if consequence.effect_key != "revenge_ambush":
            return False
        monster = getattr(door, "monster", None)
        if not monster:
            return False
        return bool(getattr(monster, "story_consume_on_defeat", False))

    def resolve_battle_consequence(self, monster: Any, defeated: bool) -> None:
        """战斗收尾：仅在击倒目标时结算特定后续影响。"""
        if not monster:
            return
        cid = getattr(monster, "story_consequence_id", None)
        if not cid:
            return
        if not bool(getattr(monster, "story_consume_on_defeat", False)):
            return
        if not defeated:
            return
        consequence = self.pending_consequences.get(cid)
        if not consequence:
            return
        self._consume_consequence(consequence)

    def record_elf_side_monster_outcome(self, monster: Any, defeated: bool) -> None:
        """银羽与利爪支线：根据击倒或逃跑给出不同提示并更新精灵关系。"""
        if not monster or not getattr(monster, "elf_side_story", False):
            return
        if defeated:
            self.controller.add_message("你们联手解决了敌人。她丢给你一句：'谢了，下次还你。'")
            self.elf_relation = max(-6, min(6, int(getattr(self, "elf_relation", 0)) + 1))
        else:
            self.controller.add_message("你转身就跑，背后传来她的骂声与怪物追来的风声。")
            self.elf_relation = max(-6, min(6, int(getattr(self, "elf_relation", 0)) - 1))

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
            reward_door = self._make_reward_door(
                gold=payload.get("gold", random.randint(50, 100)),
                include_item=payload.get("include_item", True),
                hint=payload.get("hint", "旧事回响"),
            )
            reward_desc = self._describe_reward(reward_door)
            self._log_effect_result(consequence, f"谢礼是 {reward_desc}")
            return True, reward_door

        if effect == "revenge_ambush":
            stage = self._get_progress_stage()
            force_hunter_config = payload.get("force_hunter", None)
            convert_to_hunter = payload.get("convert_to_hunter", True)
            hunter_name = payload.get("hunter_name")
            source_door_type = getattr(getattr(door, "enum", None), "name", "")
            monster = getattr(door, "monster", None)
            if force_hunter_config is None:
                # 在怪物门默认走“替换或强化”双路径；其余门默认转为追猎战。
                if source_door_type == "MONSTER" and monster is not None:
                    replace_chance = payload.get("monster_replace_chance", 0.35)
                    try:
                        replace_chance = max(0.0, min(1.0, float(replace_chance)))
                    except (TypeError, ValueError):
                        replace_chance = 0.35
                    force_hunter = random.random() < replace_chance
                else:
                    force_hunter = bool(convert_to_hunter)
            else:
                force_hunter = bool(force_hunter_config)
            if force_hunter or (monster is None and convert_to_hunter):
                hunter = self._create_hunter_monster(preferred_name=hunter_name)
                hp_ratio = payload.get("hp_ratio", 1.25)
                atk_ratio = payload.get("atk_ratio", 1.2)
                if stage > 0:
                    hp_ratio = min(2.4, hp_ratio * (1.0 + stage * 0.08))
                    atk_ratio = min(2.2, atk_ratio * (1.0 + stage * 0.07))
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
                hunter_hint = payload.get("hunter_hint", "脚步声不是偶然，那是追猎者在校准你的呼吸。")
                hunter.story_consequence_id = consequence.consequence_id
                # 由非怪物门引出的追猎战，只有击倒才算真正了结。
                hunter.story_consume_on_defeat = bool(
                    payload.get("consume_on_defeat", source_door_type != "MONSTER")
                )
                hunter_door = DoorEnum.MONSTER.create_instance(
                    controller=self.controller,
                    monster=hunter,
                    hint=hunter_hint,
                )
                self._log_effect_result(consequence, hunter.name)
                return True, hunter_door
            if monster:
                hp_ratio = payload.get("hp_ratio", 1.25)
                atk_ratio = payload.get("atk_ratio", 1.2)
                if stage > 0:
                    hp_ratio = min(2.4, hp_ratio * (1.0 + stage * 0.08))
                    atk_ratio = min(2.2, atk_ratio * (1.0 + stage * 0.07))
                old_hp, old_atk = monster.hp, monster.atk
                monster.hp = max(1, int(monster.hp * hp_ratio))
                monster.atk = max(1, int(monster.atk * atk_ratio))
                self.controller.add_message(
                    self._resolve_message(payload, "message", "旧怨者设下伏击，怪物获得强化。")
                )
                self._log_effect_result(
                    consequence,
                    f"{monster.name} 的气势暴涨，生命 {old_hp}->{monster.hp}，攻击 {old_atk}->{monster.atk}",
                )
                return True, door
            dmg = payload.get("damage", random.randint(5, 12))
            dmg = self._scale_amount(dmg, positive=False, aggressive=True)
            old_hp = self.controller.player.hp
            self.controller.player.take_damage(dmg)
            self.controller.add_message(
                self._resolve_message(payload, "message", f"你遭到报复，受到 {dmg} 点伤害。")
            )
            self._log_effect_result(
                consequence,
                f"你在伏击里失去 {dmg} 点生命（{old_hp}->{self.controller.player.hp}）",
            )
            return True, door

        if effect == "guard_reward":
            gold = payload.get("gold", random.randint(20, 60))
            heal = payload.get("heal", 0)
            gold = self._scale_amount(gold, positive=True, aggressive=True)
            if heal > 0:
                heal = self._scale_amount(heal, positive=True)
            old_gold, old_hp = self.controller.player.gold, self.controller.player.hp
            self.controller.player.gold += gold
            if heal > 0:
                self.controller.player.heal(heal)
            self.controller.add_message(
                self._resolve_message(payload, "message", f"守卫感谢你的协助，奖励了你 {gold} 金币。")
            )
            self._log_effect_result(
                consequence,
                f"你的状态发生变化：金币 {old_gold}->{self.controller.player.gold}，生命 {old_hp}->{self.controller.player.hp}",
            )
            return True, door

        if effect == "black_market_discount":
            if getattr(getattr(door, "enum", None), "name", "") != "SHOP":
                return False, door
            try:
                ratio = float(payload.get("ratio", 0.7))
            except (TypeError, ValueError):
                ratio = 0.7
            shop_targets = self._get_shop_targets(door)
            if not shop_targets:
                return False, door
            self._queue_shop_ratio(shop_targets, ratio)
            self._apply_shop_ratio(shop_targets, ratio)
            ratio_text = f"当前商品按约 {max(1, int(ratio * 100))}% 结算"
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    f"商人认出你是熟客同路人，{ratio_text}。",
                )
            )
            self._log_effect_result(consequence, ratio_text)
            return True, door

        if effect == "black_market_markup":
            if getattr(getattr(door, "enum", None), "name", "") != "SHOP":
                return False, door
            try:
                ratio = float(payload.get("ratio", 1.4))
            except (TypeError, ValueError):
                ratio = 1.4
            shop_targets = self._get_shop_targets(door)
            if not shop_targets:
                return False, door
            self._queue_shop_ratio(shop_targets, ratio)
            self._apply_shop_ratio(shop_targets, ratio)
            ratio_text = f"当前商品按约 {max(1, int(ratio * 100))}% 上浮"
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    f"商人认出你惹过他们的人，{ratio_text}。",
                )
            )
            self._log_effect_result(consequence, ratio_text)
            return True, door

        if effect == "shrine_blessing":
            if getattr(getattr(door, "enum", None), "name", "") == "TRAP":
                self.controller.add_message(
                    self._resolve_message(payload, "message", "圣坛余辉保护了你，陷阱化作馈赠。")
                )
                reward_door = self._make_reward_door(gold=random.randint(25, 65), include_item=False, hint="神佑余辉")
                self._log_effect_result(
                    consequence,
                    f"险境被改写成馈赠：{self._describe_reward(reward_door)}",
                )
                return True, reward_door
            monster = getattr(door, "monster", None)
            if monster:
                old_atk = monster.atk
                monster.atk = max(1, int(monster.atk * 0.82))
                self.controller.add_message(
                    self._resolve_message(payload, "message", "你受到神佑，敌人的攻势被压制。")
                )
                self._log_effect_result(
                    consequence,
                    f"{monster.name} 的攻击被压制（{old_atk}->{monster.atk}）",
                )
                return True, door
            return False, door

        if effect == "shrine_curse":
            duration = payload.get("duration", 2)
            if self._get_progress_stage() >= 2:
                duration += 1
            self.controller.player.apply_status(
                StatusName.WEAK.create_instance(duration=duration, target=self.controller.player)
            )
            self.controller.add_message(
                self._resolve_message(payload, "message", f"诅咒追上了你，陷入虚弱 {duration} 回合。")
            )
            self._log_effect_result(consequence, f"你陷入虚弱，持续 {duration} 回合")
            return True, door

        if effect == "atk_training":
            delta = payload.get("delta", 2)
            if self._get_progress_stage() >= 2:
                delta += 1
            old_atk = self.controller.player._atk
            self.controller.player.change_base_atk(delta)
            self.controller.add_message(
                self._resolve_message(payload, "message", "这段经历让你学会了更狠的出手方式。")
            )
            self._log_effect_result(
                consequence,
                f"你的基础攻击提升了（{old_atk}->{self.controller.player._atk}）",
            )
            return True, door

        if effect == "lose_gold":
            old_gold = self.controller.player.gold
            lost = min(self.controller.player.gold, payload.get("amount", random.randint(15, 45)))
            lost = min(self.controller.player.gold, self._scale_amount(lost, positive=False))
            self.controller.player.gold -= lost
            self.controller.add_message(
                self._resolve_message(payload, "message", f"旧账找上门来，你被迫赔了 {lost} 金币。")
            )
            self._log_effect_result(
                consequence,
                f"你付出了代价，金币 {old_gold}->{self.controller.player.gold}",
            )
            return True, door

        if effect == "force_story_event":
            if getattr(getattr(door, "enum", None), "name", "") != "EVENT":
                return False, door
            event_key = payload.get("event_key")
            if not isinstance(event_key, str) or not event_key.strip():
                return False, door
            door.story_forced_event_key = event_key.strip()
            hint = payload.get("hint")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            self.controller.add_message(
                self._resolve_message(payload, "message", "命运突然偏转，下一扇事件门被写上了你的名字。")
            )
            self._log_effect_result(consequence, "")
            return True, door

        if effect == "elf_side_reward_mark":
            door_type = getattr(getattr(door, "enum", None), "name", "")
            if door_type != "REWARD":
                return False, door
            chance = payload.get("chance", 0.2)
            chance = max(0.0, min(1.0, float(chance)))
            if random.random() >= chance:
                return False, door
            setattr(door, "elf_side_reward", True)
            hint = payload.get("hint")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            self.controller.add_message(
                self._resolve_message(payload, "message", "门缝里闪过一抹银光……")
            )
            self._log_effect_result(consequence, "")
            return True, door

        if effect == "elf_side_monster_mark":
            door_type = getattr(getattr(door, "enum", None), "name", "")
            if door_type != "MONSTER":
                return False, door
            chance = payload.get("chance", 0.2)
            chance = max(0.0, min(1.0, float(chance)))
            if random.random() >= chance:
                return False, door
            monster = getattr(door, "monster", None)
            if monster is None:
                return False, door
            setattr(monster, "elf_side_story", True)
            hint = payload.get("hint")
            hint_text = hint.strip() if isinstance(hint, str) and hint.strip() else ""
            if hint_text:
                door.hint = hint_text
            message_text = self._resolve_message(payload, "message", "门后传来打斗声，你推门一看——")
            self.controller.add_message(message_text)
            # 该支线强调“入门瞬间就要被拉进战斗”，因此确保 payload 提示会输出到消息流。
            if hint_text and hint_text != message_text:
                self.controller.add_message(hint_text)
            self._log_effect_result(consequence, "")
            return True, door

        if effect == "replace_with_elf_side_event":
            door_type = getattr(getattr(door, "enum", None), "name", "")
            if door_type != "SHOP":
                return False, door
            chance = payload.get("chance", 0.2)
            chance = max(0.0, min(1.0, float(chance)))
            if random.random() >= chance:
                return False, door
            event_key = payload.get("event_key")
            if not isinstance(event_key, str) or not event_key.strip():
                return False, door
            new_door = DoorEnum.SHOP.create_instance(controller=self.controller)
            new_door.story_forced_event_key = event_key.strip()
            hint = payload.get("hint", "墙上的银色箭羽指向下一次相遇。")
            if isinstance(hint, str) and hint.strip():
                new_door.hint = hint.strip()
            self.controller.add_message(
                self._resolve_message(payload, "message", "门后的景象和你预想的不太一样……")
            )
            self._log_effect_result(consequence, "")
            return True, new_door

        if effect == "treasure_marked_item":
            if getattr(getattr(door, "enum", None), "name", "") != "REWARD":
                return False, door
            current_reward = getattr(door, "reward", {})
            if not isinstance(current_reward, dict):
                current_reward = {}
            keep_gold = bool(payload.get("keep_gold", True))
            reward_gold = current_reward.get("gold", 0) if keep_gold else 0
            if bool(payload.get("replace_existing_items", True)):
                new_reward: Dict[Any, int] = {}
            else:
                new_reward = {k: v for k, v in current_reward.items() if k != "gold"}
            if reward_gold > 0:
                new_reward["gold"] = reward_gold
            bonus_gold = int(payload.get("gold_bonus", 0))
            if bonus_gold > 0:
                new_reward["gold"] = new_reward.get("gold", 0) + bonus_gold
            amount = max(1, int(payload.get("amount", 1)))
            item_key = payload.get("item_key")
            marked_item = self._create_story_item(item_key)
            if not marked_item:
                marked_item = create_random_item()
            new_reward[marked_item] = amount
            door.reward = new_reward
            self.controller.add_message(
                self._resolve_message(payload, "message", f"宝物门被人做了记号，里面是 {marked_item.name}。")
            )
            self._log_effect_result(
                consequence,
                f"宝物内容被改写：{self._describe_reward(door)}",
            )
            return True, door

        if effect == "treasure_vanish":
            if getattr(getattr(door, "enum", None), "name", "") != "REWARD":
                return False, door
            fake_gold = max(0, int(payload.get("fake_gold", 0)))
            door.reward = {"gold": fake_gold} if fake_gold > 0 else {}
            self.controller.add_message(
                self._resolve_message(payload, "message", "你推开宝物门，只看到被提前洗劫的空架子。")
            )
            self._log_effect_result(
                consequence,
                "宝物已被掏空",
            )
            return True, door

        if effect == "puppet_dark_boss":
            if getattr(getattr(door, "enum", None), "name", "") != "MONSTER":
                return False, door
            from models.monster import Monster, _apply_player_match_scaling, estimate_player_power

            base_hp = max(80, int(payload.get("base_hp", 220)))
            base_atk = max(10, int(payload.get("base_atk", 34)))
            boss_name = payload.get("boss_name", "堕暗机偶·弃线者")
            story_flags = self.choice_flags.union(self.story_tags)
            kind_name = payload.get("kind_persona_name", "绒心·诺诺")
            dark_name = payload.get("dark_persona_name", "裂齿·夜魇")

            default_kind_flags = {
                "puppet_intro_hide",
                "puppet_signal_empathy",
                "puppet_signal_analyze",
                "puppet_descent_patch",
            }
            default_dark_flags = {
                "puppet_intro_blackout",
                "puppet_intro_decoy",
                "puppet_signal_sellout",
                "puppet_descent_cut_emotion",
                "puppet_descent_dark_feed",
            }
            raw_kind_flags = payload.get("kind_flags", default_kind_flags)
            raw_dark_flags = payload.get("dark_flags", default_dark_flags)
            kind_flags = set(raw_kind_flags or default_kind_flags)
            dark_flags = set(raw_dark_flags or default_dark_flags)
            kind_score = sum(1 for f in kind_flags if f in story_flags)
            dark_score = sum(1 for f in dark_flags if f in story_flags)
            stored_evil = getattr(self, "puppet_evil_value", None)
            try:
                stored_evil = int(stored_evil) if stored_evil is not None else None
            except (TypeError, ValueError):
                stored_evil = None
            if stored_evil is None:
                evil_value = 55 + dark_score * 8 - kind_score * 8
            else:
                evil_value = stored_evil
            if "evil_value" in payload:
                try:
                    evil_value = int(payload.get("evil_value"))
                except (TypeError, ValueError):
                    pass
            evil_value += (dark_score - kind_score) * 2
            evil_value = max(0, min(100, evil_value))
            side_hit_count = len([tag for tag in self.story_tags if str(tag).startswith("consumed:puppet_side_")])
            direct_hp_scale = 1.0
            direct_atk_scale = 1.0
            player = getattr(self.controller, "player", None)

            def _add_start_damage(amount: int, text: str) -> None:
                if not player:
                    return
                real = max(0, min(player.hp, int(amount)))
                if real <= 0:
                    return
                player.take_damage(real)
                self.controller.add_message(text.format(value=real))

            def _add_start_heal(amount: int, text: str) -> None:
                if not player:
                    return
                healed = player.heal(max(0, int(amount)))
                if healed <= 0:
                    return
                self.controller.add_message(text.format(value=healed))

            # 中间事件的直接影响（不依赖邪恶值）。
            if "consumed:puppet_side_minion_once" in story_flags:
                direct_atk_scale *= 0.93
                self.controller.add_message("【前情影响】你拆过它的追猎小弟，已读懂一部分同步节奏，它开场挥击慢了半拍。")
            if "consumed:puppet_side_shop_once" in story_flags:
                direct_hp_scale *= 1.08
                self.controller.add_message("【前情影响】黑市替它补了装甲片，核心外壳更难被打穿。")
            if "consumed:puppet_side_trap_once" in story_flags:
                direct_atk_scale *= 1.05
                _add_start_damage(4, "【前情影响】陷阱回廊数据被写进战斗脚本，碎片风暴先手刮伤你（-{value}HP）。")
            if "consumed:puppet_side_reward_once" in story_flags:
                direct_hp_scale *= 0.94
                _add_start_heal(5, "【前情影响】你在宝物舱拿到的结界模板提前启动，稳住了开场节奏（+{value}HP）。")

            if "puppet_signal_soft" in story_flags:
                direct_hp_scale *= 0.9
                direct_atk_scale *= 0.9
                self.controller.add_message("【前情影响】你在信号室重放的温和样本还在生效，它的攻击协议出现了短暂迟滞。")
            elif "puppet_signal_log" in story_flags:
                direct_atk_scale *= 0.88
                self.controller.add_message("【前情影响】你截取的战术日志让你更早读出它的抬手动作。")
            elif "puppet_signal_resell" in story_flags:
                direct_hp_scale *= 1.12
                direct_atk_scale *= 1.1
                self.controller.add_message("【前情影响】你转卖污染片段导致病毒扩散，它的黑暗协议反而被额外喂强。")

            if "puppet_kind_echo_trust" in story_flags:
                direct_atk_scale *= 0.9
                self.controller.add_message("【前情影响】你回应过善良人格的求援，它在底层悄悄卡住了几条杀戮指令。")
            elif "puppet_kind_echo_comfort" in story_flags:
                direct_hp_scale *= 0.92
                _add_start_heal(6, "【前情影响】你安抚过它被遗弃的记忆，开战瞬间蓝光回路替你回了一口气（+{value}HP）。")
            elif "puppet_kind_echo_exploit" in story_flags:
                direct_atk_scale *= 1.08
                self.controller.add_message("【前情影响】你曾强挖它的情感弱点，创伤被反向利用，黑暗人格更暴躁。")

            if "puppet_rift_kind" in story_flags:
                direct_hp_scale *= 0.94
            elif "puppet_rift_balance" in story_flags:
                direct_atk_scale *= 0.97
            elif "puppet_rift_dark" in story_flags:
                direct_hp_scale *= 1.1
                direct_atk_scale *= 1.06

            hp_scale = 1.0
            atk_scale = 1.0
            awakened_kind = False
            dark_overload = False
            if evil_value <= 25:
                hp_scale, atk_scale = 0.72, 0.72
                awakened_kind = True
            elif evil_value <= 45:
                hp_scale, atk_scale = 0.86, 0.84
                awakened_kind = True
            elif evil_value <= 65:
                hp_scale, atk_scale = 1.0, 1.0
            elif evil_value <= 85:
                hp_scale, atk_scale = 1.18, 1.14
            else:
                hp_scale, atk_scale = 1.35, 1.28
                dark_overload = True
            hp_scale *= direct_hp_scale
            atk_scale *= direct_atk_scale

            boss = Monster(
                name=boss_name,
                hp=max(1, int(base_hp * hp_scale)),
                atk=max(1, int(base_atk * atk_scale)),
                tier=max(2, int(payload.get("tier", 5))),
            )
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            power_score = estimate_player_power(player=player, current_round=round_count)
            _apply_player_match_scaling(
                monster=boss,
                player=player,
                current_round=round_count,
                power_score=power_score,
            )
            if side_hit_count <= 0:
                self.controller.add_message(
                    self._resolve_message(
                        payload,
                        "no_side_event_message",
                        "你几乎没在中途触发那些支线干预，它的最终参数按核心读数直接结算。",
                    )
                )
            if awakened_kind:
                heal = min(100 - self.controller.player.hp, max(4, int(payload.get("kind_heal", 12))))
                if heal > 0:
                    self.controller.player.heal(heal)
                self.controller.add_message(
                    self._resolve_message(
                        payload,
                        "kind_awaken_message",
                        f"病毒噪声里忽然响起温柔童谣，{kind_name}短暂夺回控制，悄悄替你挡下一轮杀意。",
                    )
                )
            elif dark_overload:
                self.controller.add_message(
                    self._resolve_message(
                        payload,
                        "dark_overload_message",
                        f"你先前的选择不断喂养黑暗协议，{dark_name}完全接管了机偶核心。",
                    )
                )
            else:
                self.controller.add_message(
                    self._resolve_message(
                        payload,
                        "neutral_message",
                        f"{kind_name}与{dark_name}仍在互相撕扯，黑暗协议暂时占了上风。",
                    )
                )

            door.monster = boss
            hint = payload.get("hunter_hint") or payload.get("hint")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            self._log_effect_result(
                consequence,
                f"{boss.name} 降临（邪恶值 {evil_value}/100），生命 {boss.hp}，攻击 {boss.atk}",
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

    def _build_trigger_message(self, consequence: PendingConsequence) -> str:
        custom = self._resolve_message(consequence.payload, "log_trigger", "")
        if custom:
            return custom

        by_consequence = {
            "knight_aid_traitor_revenge": "你脑中闪过那名被你救下的骑士，空气里多了一股熟悉的杀意。",
            "smuggler_report_gang_revenge": "你想起那次举报，巷道深处传来追兵踩碎砂石的声音。",
            "lost_child_village_gift": "你忽然听见远处有人喊你的名字，像是旧日恩情追上了你。",
        }
        if consequence.consequence_id in by_consequence:
            return by_consequence[consequence.consequence_id]

        by_source = {
            "knight_aided": "你曾经的善举在此刻回响。",
            "smuggler_bought_goods": "黑市里那笔交易并没有真正结束。",
            "smuggler_reported": "你以为早已翻篇的旧账，忽然被人重新翻开。",
            "lost_child_guided_home": "那次送孩子回家的路，似乎把命运也悄悄改了道。",
        }
        if consequence.source_flag in by_source:
            return by_source[consequence.source_flag]

        return ""

    def _log_effect_result(self, consequence: PendingConsequence, detail: str) -> None:
        custom = self._resolve_message(consequence.payload, "log_result", "")
        if custom:
            self.controller.add_message(custom)
            return

        cid = consequence.consequence_id
        effect = consequence.effect_key

        if cid == "knight_aid_traitor_revenge":
            self.controller.add_message(f"因为你之前救了骑士，现在骑士的死对头{detail}来追杀你了。")
            return
        if effect == "black_market_discount":
            self.controller.add_message(f"你刚踏进店门，掌柜就改了价签：{detail}。")
            return
        if effect == "black_market_markup":
            self.controller.add_message(f"掌柜瞥了你一眼，慢慢把价签往上拨：{detail}。")
            return
        if effect == "revenge_ambush":
            self.controller.add_message(f"旧怨落地成刀，眼前局势骤变：{detail}。")
            return
        if effect == "guard_reward":
            self.controller.add_message(f"你收下了这份迟来的回报：{detail}。")
            return
        if effect == "villagers_gift":
            self.controller.add_message(f"门后没有杀意，只有一份留给你的心意：{detail}。")
            return
        if effect == "shrine_blessing":
            self.controller.add_message(f"那点神性余辉在关键时刻护住了你：{detail}。")
            return
        if effect == "shrine_curse":
            self.controller.add_message(f"你听见耳边低语，诅咒果然还是追了上来：{detail}。")
            return
        if effect == "atk_training":
            self.controller.add_message(f"旧经历在手中成了新招：{detail}。")
            return
        if effect == "lose_gold":
            self.controller.add_message(f"这笔旧账终究要还：{detail}。")
            return
        if effect == "force_story_event":
            return
        if effect == "treasure_marked_item":
            self.controller.add_message(f"宝物门里的陈设明显被提前动过手脚：{detail}。")
            return
        if effect == "treasure_vanish":
            self.controller.add_message(f"你只摸到一层冷灰，值钱的东西全没了：{detail}。")
            return

        self.controller.add_message(f"命运的回声改写了这一刻：{detail}。")

    def _create_story_item(self, item_key: Any):
        if not isinstance(item_key, str):
            return None
        key = item_key.strip().lower()
        item_factory = {
            "flying_hammer": lambda: FlyingHammer(name="飞锤", cost=25),
            "barrier": lambda: Barrier(name="结界", duration=3, cost=30),
            "giant_scroll": lambda: GiantScroll(name="巨大卷轴", duration=3, cost=40),
            "revive_scroll": lambda: ReviveScroll(name="复活卷轴", cost=50),
            "attack_up_scroll": lambda: AttackUpScroll(
                name="攻击力提升卷轴",
                atk_bonus=5,
                duration=8,
                cost=25,
            ),
            "healing_scroll": lambda: HealingScroll(name="恢复卷轴", duration=10, cost=18),
            "immune_scroll": lambda: ImmuneScroll(name="免疫卷轴", duration=5, cost=20),
        }
        factory = item_factory.get(key)
        return factory() if factory else None

    def _describe_reward(self, reward_door: Any) -> str:
        reward = getattr(reward_door, "reward", {})
        parts = []
        for key, amount in reward.items():
            if key == "gold":
                parts.append(f"{amount}G")
            else:
                name = getattr(key, "name", "未知道具")
                parts.append(f"{name}x{amount}")
        return ", ".join(parts) if parts else "无"

    # 追猎怪物池：按回合区间划分，每档内随机选择
    HUNTER_POOL = [
        (10, [("土匪", 26, 6), ("野狼", 22, 5), ("蝙蝠", 20, 6), ("小哥布林", 24, 5)]),
        (20, [("狼人", 38, 8), ("食人魔", 40, 7), ("美杜莎", 32, 9), ("幽灵", 28, 10), ("吸血鬼", 42, 10)]),
        (999, [("暗影刺客", 56, 16), ("死亡骑士", 55, 14), ("冥界使者", 62, 15), ("海妖", 52, 14), ("雷鸟", 58, 13)]),
    ]

    def _create_hunter_monster(self, preferred_name: Optional[str] = None):
        from models.monster import Monster

        round_count = getattr(self.controller, "round_count", 0)
        stage = self._get_progress_stage()
        if preferred_name:
            if round_count <= 10:
                hunter = Monster(name=preferred_name, hp=32, atk=8, tier=2)
            elif round_count <= 20:
                hunter = Monster(name=preferred_name, hp=48, atk=12, tier=3)
            else:
                hunter = Monster(name=preferred_name, hp=62, atk=17, tier=4)
            if stage > 0:
                hunter.hp = max(1, int(hunter.hp * (1 + stage * 0.08)))
                hunter.atk = max(1, int(hunter.atk * (1 + stage * 0.06)))
            return hunter
        for max_round, pool in self.HUNTER_POOL:
            if round_count <= max_round:
                name, base_hp, base_atk = random.choice(pool)
                tier = 2 if max_round == 10 else (3 if max_round == 20 else 4)
                hunter = Monster(name=name, hp=base_hp, atk=base_atk, tier=tier)
                if stage > 0:
                    hunter.hp = max(1, int(hunter.hp * (1 + stage * 0.08)))
                    hunter.atk = max(1, int(hunter.atk * (1 + stage * 0.06)))
                return hunter
        name, base_hp, base_atk = random.choice(self.HUNTER_POOL[-1][1])
        hunter = Monster(name=name, hp=base_hp, atk=base_atk, tier=4)
        if stage > 0:
            hunter.hp = max(1, int(hunter.hp * (1 + stage * 0.08)))
            hunter.atk = max(1, int(hunter.atk * (1 + stage * 0.06)))
        return hunter

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
                    original = item.cost
                    if ratio > 1:
                        new_cost = max(1, int(original * ratio + 0.9999))
                        if new_cost == original:
                            new_cost = original + 1
                    elif ratio < 1:
                        new_cost = max(1, int(original * ratio))
                        if new_cost == original and original > 1:
                            new_cost = original - 1
                    else:
                        new_cost = original
                    item.cost = max(1, new_cost)
                after = first_item.cost
                preview = f"{first_item.name}: {before}G→{after}G"
        return preview

    def _queue_shop_ratio(self, shops, ratio: float) -> None:
        for shop in shops:
            queue_method = getattr(shop, "queue_next_price_ratio", None)
            if callable(queue_method):
                queue_method(ratio)
