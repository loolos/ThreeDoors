import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

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
from models.pre_final_gate_config import ALL_PRE_FINAL_DOOR_TYPES, PRE_FINAL_GATE_STORY_CONFIG
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
    DEFAULT_ENDING_FORCE_ROUND = 200
    PRE_FINAL_WINDOW_START_OFFSET = 15
    PRE_FINAL_WINDOW_END_OFFSET = 10
    PRE_FINAL_RECHECK_INTERVAL = 5
    DEFAULT_ENDING_FORCE_CONSEQUENCE_ID = PRE_FINAL_GATE_STORY_CONFIG["round200_default_first_gate"]["consequence_id"]
    STAGE_CURTAIN_FORCE_CONSEQUENCE_ID = PRE_FINAL_GATE_STORY_CONFIG["round200_stage_preface"]["consequence_id"]
    PUPPET_PRE_FINAL_CONSEQUENCE_ID = PRE_FINAL_GATE_STORY_CONFIG["puppet_rematch_gate"]["consequence_id"]
    ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID = PRE_FINAL_GATE_STORY_CONFIG["elf_rival_final_gate"]["consequence_id"]

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

    def _has_started_long_story_branch(self) -> bool:
        """判断是否已开启任意长线分支，用于 200 回合默认结局分流。"""
        if bool(getattr(self, "elf_chain_started", False)):
            return True
        if "puppet_arc_active" in self.story_tags:
            return True

        event_counts = getattr(self.controller, "event_trigger_counts", {}) or {}
        if not isinstance(event_counts, dict) or not event_counts:
            return False
        try:
            from models.events import LONG_EVENT_STARTER_CLASSES
            starter_names = {event_cls.__name__ for event_cls in LONG_EVENT_STARTER_CLASSES}
        except Exception:
            starter_names = {
                "TimePawnshopEvent",
                "MirrorTheaterEvent",
                "MoonBountyEvent",
                "ClockworkBazaarEvent",
                "DreamWellEvent",
                "PuppetAbandonmentEvent",
                "ElfThiefIntroEvent",
            }
        for event_name in starter_names:
            if int(event_counts.get(event_name, 0)) > 0:
                return True
        return False

    def _is_stage_curtain_route_ready(self) -> bool:
        """舞台谢幕链前置：只要求已拿到飞贼钥匙。"""
        if "curtain_call_script_recovered" in self.story_tags:
            return False
        key_obtained = bool(getattr(self, "elf_key_obtained", False)) or ("elf_key_obtained" in self.story_tags)
        return key_obtained

    def ensure_stage_curtain_preface_schedule(self) -> bool:
        """满足前置时将“银羽秘藏”纳入终局前倒数窗口调度（宝物门命中，超窗强制）。"""
        if not self._is_stage_curtain_route_ready():
            return False
        if "ending:default_normal_completed" in self.story_tags:
            return False
        if "ending:stage_curtain_completed" in self.story_tags:
            return False
        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        ending_round = int(self.DEFAULT_ENDING_FORCE_ROUND)
        window_start = max(0, ending_round - int(self.PRE_FINAL_WINDOW_START_OFFSET))
        window_end = max(0, ending_round - int(self.PRE_FINAL_WINDOW_END_OFFSET))
        if current_round < window_start:
            return False
        if current_round <= window_end:
            min_round = current_round
            # 窗口内仅按门型触发；窗口结束后（下一回合）才进入强制兜底。
            max_round = window_end + 1
        else:
            min_round = current_round
            max_round = current_round
        consequence_id = self.STAGE_CURTAIN_FORCE_CONSEQUENCE_ID
        if consequence_id in self.pending_consequences or consequence_id in self.consumed_consequences:
            return False
        cfg = PRE_FINAL_GATE_STORY_CONFIG.get("round200_stage_preface", {})
        payload = cfg.get("payload", {})
        registered = self.register_consequence(
            choice_flag=str(cfg.get("choice_flag", "ending_stage_curtain_route")),
            consequence_id=consequence_id,
            effect_key=str(cfg.get("effect_key", "force_story_event")),
            chance=1.0,
            trigger_door_types=["REWARD"],
            min_round=min_round,
            max_round=max_round,
            force_on_expire=True,
            force_door_type=str(cfg.get("force_door_type", "EVENT")),
            priority=int(cfg.get("priority", 1260)),
            payload=dict(payload) if isinstance(payload, dict) else {},
        )
        if registered:
            self.story_tags.add("ending:stage_curtain_scheduled")
        return registered

    def _has_pending_blocking_pre_final_events(self) -> bool:
        blocking_ids = {
            self.STAGE_CURTAIN_FORCE_CONSEQUENCE_ID,
            self.PUPPET_PRE_FINAL_CONSEQUENCE_ID,
            self.ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID,
        }
        return any(cid in self.pending_consequences for cid in blocking_ids)

    def _should_run_pre_final_recheck(self, *, current_round: int, window_start: int, ending_round: int) -> bool:
        """倒数窗口统一检查：窗口起点 + 每隔固定回合 + 终局回合兜底。"""
        if current_round == ending_round:
            return True
        if current_round == window_start:
            return True
        last_round = getattr(self, "pre_final_last_check_round", None)
        if not isinstance(last_round, int):
            return True
        return (current_round - last_round) >= int(self.PRE_FINAL_RECHECK_INTERVAL)

    def ensure_pre_final_event_schedule(self) -> bool:
        """在终局前倒数 15~10 回合预挂载前置战，未命中时在结局前强制触发。"""
        if "ending:default_normal_completed" in self.story_tags:
            return False
        if "ending:stage_curtain_completed" in self.story_tags:
            return False

        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        ending_round = int(self.DEFAULT_ENDING_FORCE_ROUND)
        window_start = max(0, ending_round - int(self.PRE_FINAL_WINDOW_START_OFFSET))
        window_end = max(0, ending_round - int(self.PRE_FINAL_WINDOW_END_OFFSET))
        if current_round < window_start:
            return False
        if not self._should_run_pre_final_recheck(
            current_round=current_round,
            window_start=window_start,
            ending_round=ending_round,
        ):
            return False

        # 舞台谢幕钥匙线也纳入终局前事件窗口（宝物门命中，超窗强制）
        stage_scheduled = self.ensure_stage_curtain_preface_schedule()

        try:
            from models.events import schedule_next_pre_final_gate
        except Exception:
            return stage_scheduled

        if current_round <= window_end:
            min_round = current_round
            # 窗口内仅按门型触发；窗口结束后（下一回合）才进入强制兜底。
            max_round = window_end + 1
        else:
            # 超出预挂载窗口后，立即进入强制兜底，保证终局事件前一定触发。
            min_round = current_round
            max_round = current_round

        scheduled_any = bool(stage_scheduled)
        scheduled_keys = []
        for _ in range(4):
            scheduled_key = schedule_next_pre_final_gate(
                self.controller,
                include_default_final_boss=False,
                min_round=min_round,
                max_round=max_round,
            )
            if not scheduled_key:
                break
            scheduled_any = True
            scheduled_keys.append(scheduled_key)
        if "elf_rival_final_gate" in scheduled_keys:
            self.controller.add_message("【终局前事件】你在门廊里嗅到熟悉银羽杀意，飞贼清算战即将插入。")
        if "puppet_rematch_gate" in scheduled_keys:
            self.controller.add_message("【终局前事件】红噪门框开始闪烁，黑暗木偶补战正在逼近。")
        self.pre_final_last_check_round = current_round
        return scheduled_any

    def ensure_default_normal_ending_schedule(self) -> bool:
        """在第 200 回合且未开启分支时，强制挂载默认终局入口事件。"""
        self.ensure_pre_final_event_schedule()
        # 终局前事件未清空时，阻止任何结局入口事件挂载。
        if self._has_pending_blocking_pre_final_events():
            return False
        if self._has_started_long_story_branch():
            return False
        if "ending:default_normal_completed" in self.story_tags:
            return False
        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        if current_round < self.DEFAULT_ENDING_FORCE_ROUND:
            return False
        consequence_id = self.DEFAULT_ENDING_FORCE_CONSEQUENCE_ID
        if consequence_id in self.pending_consequences or consequence_id in self.consumed_consequences:
            return False
        cfg = PRE_FINAL_GATE_STORY_CONFIG.get("round200_default_first_gate", {})
        payload = cfg.get("payload", {})
        registered = self.register_consequence(
            choice_flag=str(cfg.get("choice_flag", "ending_default_normal_gate")),
            consequence_id=consequence_id,
            effect_key=str(cfg.get("effect_key", "force_story_event")),
            chance=1.0,
            trigger_door_types=list(ALL_PRE_FINAL_DOOR_TYPES),
            min_round=self.DEFAULT_ENDING_FORCE_ROUND,
            max_round=self.DEFAULT_ENDING_FORCE_ROUND,
            force_on_expire=True,
            force_door_type=str(cfg.get("force_door_type", "EVENT")),
            priority=int(cfg.get("priority", 1200)),
            payload=dict(payload) if isinstance(payload, dict) else {},
        )
        if registered:
            self.story_tags.add("ending:default_normal_scheduled")
        return registered

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
        """扩展端口：允许后果在触发时修改剧情指标（如木偶隐性参数）。"""
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

    def _consume_consequence(self, consequence: PendingConsequence) -> None:
        cid = consequence.consequence_id
        self.consumed_consequences.add(cid)
        self.story_tags.add(f"consumed:{cid}")
        self.pending_consequences.pop(cid, None)
        self._queue_chain_followups(consequence)

    def _should_defer_consumption(self, consequence: PendingConsequence, door: Any) -> bool:
        if consequence.effect_key not in ("revenge_ambush", "puppet_side_minion", "moon_bounty_mid_battle", "elf_rival_final_gate"):
            return False
        monster = getattr(door, "monster", None)
        if not monster:
            return False
        return bool(getattr(monster, "story_consume_on_defeat", False))

    def resolve_battle_consequence(self, monster: Any, defeated: bool) -> None:
        """战斗收尾：击败特定目标时结算后续影响；木偶最终战额外结算结局与奖励。"""
        if not monster:
            return
        if defeated and bool(getattr(monster, "story_default_final_boss", False)):
            self._resolve_default_final_outcome()
        if defeated and bool(getattr(monster, "story_puppet_final_boss", False)):
            self._resolve_puppet_final_outcome()
        if (not defeated) and bool(getattr(monster, "story_puppet_final_boss", False)):
            self._resolve_puppet_final_escape_outcome()
        if bool(getattr(monster, "story_elf_rival_final_boss", False)):
            if defeated:
                self._resolve_elf_rival_final_victory(monster)
            else:
                self._resolve_elf_rival_final_escape(monster)
        if bool(getattr(monster, "story_pre_final_dispatch", False)):
            self._schedule_next_pre_final_gate(after_battle=True, defeated=defeated)
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
        self._resolve_moon_bounty_mid_outcome(monster)

    def _resolve_elf_rival_final_victory(self, monster: Any) -> None:
        """终局前击败飞贼：给出少量终局提示。"""
        if "ending:elf_rival_final_victory" in self.story_tags:
            return
        self.story_tags.add("ending:elf_rival_final_victory")
        self.story_tags.add("ending:elf_rival_final_gate_done")
        self.choice_flags.add("ending_elf_rival_final_victory")
        self.elf_final_outcome = "rival_defeated"
        self.controller.add_message("【银羽终局·战败】她单膝撑地，笑得很勉强：'行，你这次赢了。'")
        hint = str(getattr(monster, "story_elf_rival_hint", "")).strip()
        if hint:
            self.controller.add_message(f"【银羽提示】{hint}")
        else:
            self.controller.add_message("【银羽提示】她低声提醒：'终局门里别被第一层答案骗了，真正的出口常藏在第二次选择之后。'")
        self._schedule_next_pre_final_gate(after_battle=True, defeated=True)

    def _resolve_elf_rival_final_escape(self, monster: Any) -> None:
        """终局前从飞贼战斗撤离：两人彻底别过。"""
        if "ending:elf_rival_parted" in self.story_tags:
            return
        self.story_tags.add("ending:elf_rival_parted")
        self.story_tags.add("ending:elf_rival_final_gate_done")
        self.choice_flags.add("ending_elf_rival_parted")
        self.elf_final_outcome = "rival_parted"
        self.controller.add_message("【银羽终局·错身】你借着烟幕撤离，她没有追上来，只在远处抛下一句：'下次不用再见了。'")
        self._schedule_next_pre_final_gate(after_battle=True, defeated=False)

    def _resolve_moon_bounty_mid_outcome(self, monster: Any) -> None:
        """月蚀链中继战斗收尾：记录日记证据并输出剧情提示。"""
        if not monster or not bool(getattr(monster, "story_moon_bounty_mid", False)):
            return
        story_note = getattr(monster, "story_moon_bounty_diary_note", "")
        truth_hint = getattr(monster, "story_moon_bounty_truth_hint", "")
        diary_source = getattr(monster, "story_moon_bounty_diary_source", "")
        route = getattr(monster, "story_moon_bounty_route", "")
        if isinstance(story_note, str) and story_note.strip():
            self.controller.add_message(story_note.strip())
        if isinstance(truth_hint, str) and truth_hint.strip():
            self.controller.add_message(truth_hint.strip())

        self.story_tags.add("moon_bounty_mid_battle_cleared")
        self.story_tags.add("moon_bounty_diary_obtained")
        if isinstance(diary_source, str) and diary_source.strip():
            self.story_tags.add(f"moon_bounty_diary_source:{diary_source.strip()}")
            self.moon_bounty_diary_source = diary_source.strip()
        if isinstance(route, str) and route.strip():
            self.story_tags.add(f"moon_bounty_route:{route.strip()}")

    def _resolve_puppet_final_outcome(self) -> None:
        evil = max(0, min(100, int(getattr(self, "puppet_evil_value", 55))))
        player = getattr(self.controller, "player", None)
        if player is None:
            return
        self.puppet_final_outcome = "defeated"
        self.story_tags.add("ending:puppet_final_defeated")
        low_flags = {"puppet_intro_hide", "puppet_signal_soft", "puppet_kind_echo_trust", "puppet_rift_kind", "puppet_descent_patch"}
        high_flags = {"puppet_intro_blackout", "puppet_intro_decoy", "puppet_signal_resell", "puppet_kind_echo_exploit", "puppet_rift_dark", "puppet_descent_dark_feed", "puppet_descent_cut_emotion"}
        flags = set(getattr(self, "choice_flags", set()))
        low_hits = len(low_flags.intersection(flags))
        high_hits = len(high_flags.intersection(flags))

        bonus_gold = 0
        bonus_items = []
        ending_text = ""
        if evil <= 25:
            bonus_gold = 90
            bonus_items = ["revive_scroll", "barrier"]
            ending_text = "【木偶结局·晨光修复】你把它从最深的噪声里拽了回来。机偶胸腔里残存的蓝色灯丝一根根亮起，善良人格把最后的控制权塞回你的手里。"
        elif evil <= 45:
            bonus_gold = 65
            bonus_items = ["attack_up_scroll"]
            ending_text = "【木偶结局·带伤停机】黑暗协议被压住大半，裂开的外壳还在冒火花。它靠着墙缓慢坐下，把补给仓权限转交给你。"
        elif evil <= 70:
            bonus_gold = 40
            ending_text = "【木偶结局·灰烬停摆】两个人格在同一段噪声里互相撕扯，最终同时沉默，只剩下可回收的战利品与断续电流声。"
        else:
            bonus_gold = 18
            ending_text = "【木偶结局·暗噪回响】你虽然赢了，但黑暗协议早把自身切成碎片散入地城深处。走廊尽头只回荡着失真的童谣。"

        ending_variants = []
        if "puppet_descent_patch" in flags and evil <= 45:
            ending_variants.append("善良人格在消散前留下一句：‘别让下一扇门只剩黑色。’ 余音落下后，蓝光像灰一样飘散。")
        if "puppet_rift_kind" in flags and evil <= 45:
            ending_variants.append("你在裂隙中保住的那道蓝色回路没有白费，核心日志里保留了她的签名与一句简短的谢谢。")
        if "puppet_signal_soft" in flags:
            ending_variants.append("你曾回放过的温和语音被自动归档成‘最后的人类样本’，机偶在停机前反复播放了三遍。")
        if "puppet_descent_cut_emotion" in flags and evil >= 55:
            ending_variants.append("你亲手切断情感模块的记录被标红锁定，黑暗侧用它完成了最后一次自我复制。")
        if "puppet_signal_resell" in flags and evil >= 55:
            ending_variants.append("你倒卖过的战术信号被反向追踪，结算日志上多出一行：‘债务已由下一位闯入者继承。’")
        if "puppet_descent_dark_feed" in flags and evil >= 70:
            ending_variants.append("你喂给核心的自毁协议并未彻底死去，地城远处传来新的机械心跳。")

        # 让此前选择也影响文本
        if low_hits >= 3 and evil <= 45:
            ending_variants.append("你先前多次选择保留善良侧信号，停机前系统向你弹出了隐藏物资权限。")
            bonus_items.append("giant_scroll")
        if high_hits >= 4 and evil >= 55:
            ending_variants.append("你曾多次借黑暗牟利，清算过程吞掉了一部分战利品。")
            bonus_gold = max(0, bonus_gold - 12)

        if ending_variants:
            ending_text = f"{ending_text} {' '.join(ending_variants)}"

        player.gold += bonus_gold
        item_names = []
        for item_key in bonus_items:
            item = self._create_story_item(item_key)
            if item is None:
                continue
            player.add_item(item)
            item_names.append(getattr(item, "name", item_key))

        self.controller.add_message("【木偶终曲】怪物倒下后，走廊响起一段残缺却温柔的收束旋律。")
        self.controller.add_message(ending_text)
        reward_msg = f"你获得额外 {bonus_gold}G。"
        if item_names:
            reward_msg += f" 额外宝物：{', '.join(item_names)}。"
        self.controller.add_message(f"【木偶终战奖励】邪恶值 {evil}/100，{reward_msg}")

    def _resolve_puppet_final_escape_outcome(self) -> None:
        """木偶终战逃跑分支：记录后续结局参数，不单独触发结局。"""
        if "ending:puppet_final_escape_recorded" in self.story_tags:
            return
        self.story_tags.add("ending:puppet_final_escape_recorded")
        self.choice_flags.add("puppet_final_escape")
        self.puppet_final_outcome = "escaped"
        self.puppet_patrol_state = "active"
        self.puppet_patrol_note = "木偶仍在走廊中来回游荡"
        escape_text = (
            "【木偶终战·撤离记录】你在最后一瞬选择抽身撤离。"
            "机偶没有倒下，它仍沿着那条昏暗走廊来回游荡，"
            "每次转身都像在寻找一个从未兑现的指令。"
            "你离开了战场，却把那段失真童谣永远留在了门后。"
        )
        self.controller.add_message("【木偶终曲】你借着火花与烟尘冲出核心井，脚步声在空廊里被无限拉长。")
        self.controller.add_message(escape_text)

    def _schedule_next_pre_final_gate(self, *, after_battle: bool, defeated: bool) -> None:
        """统一调度终局前门链：战后可继续挂载剩余门。"""
        try:
            from models.events import schedule_next_pre_final_gate
        except Exception:
            return
        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        scheduled_key = schedule_next_pre_final_gate(
            self.controller,
            include_default_final_boss=False,
            min_round=current_round + 1,
            max_round=current_round + 1,
        )
        if not scheduled_key:
            return
        if not after_battle:
            return
        if scheduled_key == "elf_rival_final_gate":
            self.controller.add_message("【终局调度】你刚脱离战斗，走廊另一端又出现一抹银羽杀意。")
        elif scheduled_key == "puppet_rematch_gate":
            if defeated:
                self.controller.add_message("【终局调度】你刚压住战场余震，红噪门框再次亮起：木偶还没彻底罢手。")
            else:
                self.controller.add_message("【终局调度】你抽身退开后，失真童谣又在前方门廊回荡。")

    def _build_final_ending_meta(self) -> Dict[str, Any]:
        """聚合可交给最终结局展示层的剧情参数。"""
        final_meta: Dict[str, Any] = {}
        outcome = str(getattr(self, "puppet_final_outcome", "")).strip()
        patrol_state = str(getattr(self, "puppet_patrol_state", "")).strip()
        patrol_note = str(getattr(self, "puppet_patrol_note", "")).strip()
        if outcome:
            final_meta["puppet_final_outcome"] = outcome
        if patrol_state:
            final_meta["puppet_patrol_state"] = patrol_state
        if patrol_note:
            final_meta["puppet_patrol_note"] = patrol_note
        return final_meta

    def _resolve_default_final_outcome(self) -> None:
        """普通结局：击败“选择困难症候群”后离开迷宫。"""
        if "ending:default_normal_completed" in self.story_tags:
            return
        self.story_tags.add("ending:default_normal_completed")
        self.choice_flags.add("ending_default_normal_completed")
        self.controller.add_message("【普通结局】你击倒了“选择困难症候群”。")
        self.controller.add_message("你抵达了这座迷宫的出口，从出口离开了。")
        trigger_clear = getattr(self.controller, "trigger_game_clear", None)
        if callable(trigger_clear):
            trigger_clear(
                ending_key="default_normal",
                ending_title="普通结局·迷宫出口",
                ending_description="你在回合二百的终局门廊做出选择，击倒“选择困难症候群”后终于离开了迷宫。",
                ending_meta=self._build_final_ending_meta(),
            )
        else:
            self.controller.scene_manager.go_to("game_over_scene")

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

    def _attach_door_extension(
        self,
        door: Any,
        extension_config: Dict[str, Any],
        *,
        apply_on_attach: bool = True,
    ) -> bool:
        """将事件改写封装到门扩展，并可在挂载时做一次兼容应用。"""
        if door is None or not isinstance(extension_config, dict):
            return False
        add_method = getattr(door, "add_door_extension", None)
        if not callable(add_method):
            add_method = getattr(door, "add_extension", None)
        if callable(add_method):
            add_method(extension_config)
        else:
            ext_list = getattr(door, "door_extensions", None)
            if not isinstance(ext_list, list):
                ext_list = []
                door.door_extensions = ext_list
            ext_list.append(extension_config)
        if apply_on_attach:
            self.apply_door_extension(door=door, extension=extension_config, hook="on_attach")
        return True

    @staticmethod
    def _get_extension_runtime(extension: Dict[str, Any]) -> Dict[str, Any]:
        runtime = extension.get("_runtime")
        if not isinstance(runtime, dict):
            runtime = {}
            extension["_runtime"] = runtime
        return runtime

    def _build_marked_reward(
        self,
        current_reward: Dict[Any, int],
        payload: Dict[str, Any],
    ) -> Tuple[Dict[Any, int], Any]:
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
        return new_reward, marked_item

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

        if effect == "puppet_side_minion":
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    "金属摩擦声忽远忽近，门后有一只锈蚀的木偶在等你。",
                )
            )
            minion = self._create_puppet_minion_monster()
            minion.story_consequence_id = consequence.consequence_id
            minion.story_consume_on_defeat = True
            hint = (payload.get("hunter_hint") or payload.get("hint") or "").strip() or "金属摩擦声忽远忽近，像有一台小型追猎体在你周围绕圈校准。"
            minion_door = DoorEnum.MONSTER.create_instance(
                controller=self.controller,
                monster=minion,
                hint=hint,
            )
            self._log_effect_result(consequence, minion.name)
            return True, minion_door

        if effect == "moon_bounty_mid_battle":
            mode = str(payload.get("battle_mode", "thief")).strip().lower()
            route = str(payload.get("route", "")).strip().lower()
            battle_profiles = {
                "thief": {
                    "name": "命运乐谱大盗",
                    "entry_message": "你撞见了被通缉的「命运乐谱大盗」。他先护住胸前那本旧册子，再举刀逼你后退。",
                    "hint": "门后站着的男人满手旧伤，他怀里紧压着一本磨损日记本。",
                    "diary_source": "thief_body",
                    "diary_note": "你击败命运乐谱大盗后，在他身上只搜到一本普通日记本：每一页都在记录他失踪女儿的线索，和一次次扑空的日期。",
                    "truth_hint": "案卷并没有因此更清楚，你只知道自己带走了一本父亲的日记，准备在月蚀审判上陈述。",
                },
                "guardian": {
                    "name": "命运乐章守护者",
                    "entry_message": "你刚把被通缉者推到身后，命运乐章守护者便持盾封住门口，宣称要当场清算。",
                    "hint": "守护者的盔甲上刻着「证物优先」，它把你也列入了阻拦名单。",
                    "diary_source": "thief_testimony",
                    "diary_note": "守护者倒下后，大盗喘着气告诉你：命运乐章不是他偷的。他把随身日记本交给你，请你在月蚀审判时替他说话。",
                    "truth_hint": "你翻开日记，只看到寻女记录与混乱的行程备注；真正的失窃线索仍像被人刻意擦去。",
                },
            }
            if mode == "random":
                selected_key = random.choice(["thief", "guardian"])
            elif mode in battle_profiles:
                selected_key = mode
            else:
                selected_key = "thief"
            profile = battle_profiles[selected_key]
            hunter = self._create_hunter_monster(preferred_name=profile["name"])
            hunter.story_consequence_id = consequence.consequence_id
            hunter.story_consume_on_defeat = bool(payload.get("consume_on_defeat", True))
            hunter.story_moon_bounty_mid = True
            hunter.story_moon_bounty_route = route
            hunter.story_moon_bounty_diary_source = profile["diary_source"]
            hunter.story_moon_bounty_diary_note = profile["diary_note"]
            hunter.story_moon_bounty_truth_hint = profile["truth_hint"]
            hint = payload.get("hunter_hint") or profile["hint"]
            mid_battle_door = DoorEnum.MONSTER.create_instance(
                controller=self.controller,
                monster=hunter,
                hint=hint,
            )
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    profile["entry_message"],
                )
            )
            if profile["entry_message"] != payload.get("message", ""):
                self.controller.add_message(profile["entry_message"])
            self._log_effect_result(consequence, hunter.name)
            return True, mid_battle_door

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
                self._attach_door_extension(
                    door=door,
                    extension_config={
                        "extension_type": "trap_rewrite_to_reward",
                        "reward": dict(getattr(reward_door, "reward", {})),
                        "hint": getattr(reward_door, "hint", "神佑余辉"),
                    },
                    apply_on_attach=False,
                )
                self._log_effect_result(
                    consequence,
                    f"险境被改写成馈赠：{self._describe_reward(reward_door)}",
                )
                return True, door
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
            event_door = door
            if getattr(getattr(event_door, "enum", None), "name", "") != "EVENT":
                event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
            event_key = payload.get("event_key")
            if not isinstance(event_key, str) or not event_key.strip():
                return False, door
            hint = payload.get("hint")
            self._attach_door_extension(
                door=event_door,
                extension_config={
                    "extension_type": "force_story_event",
                    "event_key": event_key.strip(),
                    "hint": hint,
                },
                apply_on_attach=True,
            )
            self.controller.add_message(
                self._resolve_message(payload, "message", "命运突然偏转，下一扇事件门被写上了你的名字。")
            )
            self._log_effect_result(consequence, "")
            return True, event_door

        if effect == "elf_side_reward_mark":
            door_type = getattr(getattr(door, "enum", None), "name", "")
            if door_type != "REWARD":
                return False, door
            chance = payload.get("chance", 0.2)
            chance = max(0.0, min(1.0, float(chance)))
            if random.random() >= chance:
                return False, door
            self._attach_door_extension(
                door=door,
                extension_config={
                    "extension_type": "elf_side_reward_mark",
                    "hint": payload.get("hint"),
                },
                apply_on_attach=True,
            )
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
            # 精灵飞贼需要帮助才说得通：按当前 tier 选一只较强的怪物替换门内怪
            from models.monster import Monster, _get_round_limited_max_tier
            current_round = getattr(self.controller, "round_count", 0) or 0
            unlocked = getattr(self.controller, "unlocked_monster_tier", 1) or 1
            round_cap = _get_round_limited_max_tier(current_round)
            strong_tier = max(2, min(round_cap, unlocked, GameConfig.MONSTER_MAX_TIER))
            strong_monster = Monster(tier=strong_tier)
            door.monster = strong_monster
            monster = strong_monster
            hint = payload.get("hint")
            hint_text = hint.strip() if isinstance(hint, str) and hint.strip() else ""
            self._attach_door_extension(
                door=door,
                extension_config={
                    "extension_type": "elf_side_monster_mark",
                    "hint": hint_text,
                },
                apply_on_attach=True,
            )
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
            self._attach_door_extension(
                door=door,
                extension_config={
                    "extension_type": "force_story_event",
                    "event_key": event_key.strip(),
                    "hint": payload.get("hint", "墙上的银色箭羽指向下一次相遇。"),
                },
                apply_on_attach=True,
            )
            self.controller.add_message(
                self._resolve_message(payload, "message", "门后的景象和你预想的不太一样……")
            )
            self._log_effect_result(consequence, "")
            return True, door

        if effect == "treasure_marked_item":
            if getattr(getattr(door, "enum", None), "name", "") != "REWARD":
                return False, door
            current_reward = getattr(door, "reward", {})
            if not isinstance(current_reward, dict):
                current_reward = {}
            new_reward, marked_item = self._build_marked_reward(current_reward=current_reward, payload=payload)
            self._attach_door_extension(
                door=door,
                extension_config={
                    "extension_type": "treasure_marked_item",
                    "resolved_reward": new_reward,
                },
                apply_on_attach=True,
            )
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
            self._attach_door_extension(
                door=door,
                extension_config={
                    "extension_type": "treasure_vanish",
                    "resolved_reward": {"gold": fake_gold} if fake_gold > 0 else {},
                },
                apply_on_attach=True,
            )
            self.controller.add_message(
                self._resolve_message(payload, "message", "你推开宝物门，只看到被提前洗劫的空架子。")
            )
            self._log_effect_result(
                consequence,
                "宝物已被掏空",
            )
            return True, door

        if effect == "elf_rival_final_gate":
            from models.monster import Monster, estimate_player_power, _apply_player_match_scaling

            door_type = getattr(getattr(door, "enum", None), "name", "")
            door_is_monster = door_type == "MONSTER"
            player = getattr(self.controller, "player", None)
            relation = int(payload.get("relation", getattr(self, "elf_relation", -4)))
            style = str(payload.get("style", "trickster")).strip().lower()
            extensions = payload.get("extensions", [])
            if not isinstance(extensions, list):
                extensions = []

            base_hp = 138
            base_atk = 24
            hp_scale = 1.18
            atk_scale = 1.14
            if relation <= -5:
                hp_scale += 0.08
                atk_scale += 0.08
            if "deep_grudge" in extensions:
                hp_scale += 0.05
                atk_scale += 0.05

            rival = Monster(
                name="银羽飞贼·莱希娅",
                hp=max(1, int(base_hp * hp_scale)),
                atk=max(1, int(base_atk * atk_scale)),
                tier=max(3, int(payload.get("tier", 4))),
                effect_probability=0.42,
            )
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            power_score = estimate_player_power(player=player, current_round=round_count)
            _apply_player_match_scaling(
                monster=rival,
                player=player,
                current_round=round_count,
                power_score=power_score,
            )

            if style == "vengeful":
                dialogue = "莱希娅甩开斗篷，语气像刀锋：'我不是来谈条件的。'"
                hint = "她喘着血气压低声音：'终局第二门后的笑声在引你犯错，别把第一反应当答案。'"
                state = {
                    "profile": "vengeful",
                    "extensions": extensions,
                    "shadowstep_boost": [0.30, 0.22],
                    "debuff_turns": [2],
                    "debuff_mode": "weak",
                    "lines": {
                        "shadowstep": "【银羽招式·裂影突袭】她踩墙折返，连斩逼得你后撤。",
                        "debuff": "【银羽招式·割喉假动作】她借假动作压低你的重心，你的出手明显发软。",
                    },
                }
            else:
                dialogue = "莱希娅指尖一转匕首：'你总算走到这里了，先把我们之间的账清掉。'"
                hint = "她抬手拭血，冷笑道：'终局门里真正致命的不是怪物，是你以为自己已经选对。'"
                state = {
                    "profile": "trickster",
                    "extensions": extensions,
                    "shadowstep_boost": [0.24],
                    "debuff_turns": [2],
                    "debuff_mode": "poison" if "ending_hook_hunted" in extensions else "weak",
                    "lines": {
                        "shadowstep": "【银羽招式·回身夺隙】她借你的攻击空档贴身反刺。",
                        "debuff": "【银羽招式·银羽粉】她扬起一把细碎粉末，呼吸与挥刀都被干扰。",
                    },
                }

            setattr(rival, "story_elf_rival_final_boss", True)
            setattr(rival, "story_consequence_id", consequence.consequence_id)
            setattr(rival, "story_consume_on_defeat", True)
            setattr(rival, "story_elf_rival_hint", hint)
            extension_cfg = {
                "extension_type": "elf_rival_final_boss",
                "monster_ref": rival,
                "state": state,
            }

            if door_is_monster:
                if hasattr(door, "add_battle_extension"):
                    door.add_battle_extension(extension_cfg)
                else:
                    door.battle_extensions = [extension_cfg]
                door.monster = rival
                target_door = door
            else:
                target_door = DoorEnum.MONSTER.create_instance(
                    controller=self.controller,
                    monster=rival,
                    battle_extensions=[extension_cfg],
                )

            hint_text = payload.get("hint") or "银羽残痕在门槛上交错，像是一封迟到的决斗书。"
            if isinstance(hint_text, str) and hint_text.strip():
                target_door.hint = hint_text.strip()
            self.controller.add_message(self._resolve_message(payload, "message", "走廊尽头忽然多出一扇怪物门，银羽斗篷从阴影里掠出。"))
            self.controller.add_message(dialogue)
            self._log_effect_result(consequence, f"{rival.name}拦路（关系 {relation}），生命 {rival.hp}，攻击 {rival.atk}")
            return True, target_door

        if effect == "default_final_boss":
            from models.monster import Monster, estimate_player_power, _apply_player_match_scaling

            player = getattr(self.controller, "player", None)
            stage = self._get_progress_stage()
            base_hp = max(80, int(payload.get("base_hp", 170 + stage * 26)))
            base_atk = max(10, int(payload.get("base_atk", 24 + stage * 4)))
            boss_name = str(payload.get("boss_name", "选择困难症候群")).strip() or "选择困难症候群"
            boss = Monster(
                name=boss_name,
                hp=base_hp,
                atk=base_atk,
                tier=max(3, int(payload.get("tier", 4))),
            )
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            power_score = estimate_player_power(player=player, current_round=round_count)
            _apply_player_match_scaling(
                monster=boss,
                player=player,
                current_round=round_count,
                power_score=power_score,
            )
            setattr(boss, "story_default_final_boss", True)
            hint = payload.get("hint") or "门后响起一阵咂舌声：'两百回合了，你还在犹豫？'"
            final_door = DoorEnum.MONSTER.create_instance(
                controller=self.controller,
                monster=boss,
                hint=hint,
            )
            self.controller.add_message(
                self._resolve_message(
                    payload,
                    "message",
                    "你推开最后一道门，一只披着问号披风的怪物拍手鼓掌：'终于肯进来了？'",
                )
            )
            taunts = payload.get("taunts", [])
            if isinstance(taunts, list):
                for taunt in taunts:
                    if isinstance(taunt, str) and taunt.strip():
                        self.controller.add_message(taunt.strip())
            self._log_effect_result(consequence, boss.name)
            return True, final_door

        if effect == "puppet_dark_boss":
            door_is_monster = getattr(getattr(door, "enum", None), "name", "") == "MONSTER"
            from models.monster import Monster, _apply_player_match_scaling, estimate_player_power

            base_hp = max(80, int(payload.get("base_hp", 220)))
            base_atk = max(10, int(payload.get("base_atk", 34)))
            boss_name = payload.get("boss_name", "堕暗机偶·弃线者")
            phase2_name = payload.get("phase2_name", "堕暗机偶·黑暗完全体")
            story_flags = self.choice_flags.union(self.story_tags)
            kind_name = payload.get("kind_persona_name", "绒心")
            dark_name = payload.get("dark_persona_name", "裂齿")

            default_kind_flags = {
                "puppet_intro_hide",
                "puppet_signal_soft",
                "puppet_kind_echo_trust",
                "puppet_kind_echo_comfort",
                "puppet_rift_kind",
                "puppet_descent_patch",
            }
            default_dark_flags = {
                "puppet_intro_blackout",
                "puppet_intro_decoy",
                "puppet_signal_resell",
                "puppet_kind_echo_exploit",
                "puppet_rift_dark",
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
            player = getattr(self.controller, "player", None)

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
            mark_as_final_boss = bool(payload.get("mark_as_final_boss", True))
            setattr(boss, "story_puppet_final_boss", mark_as_final_boss)
            if bool(payload.get("pre_final_dispatch", False)):
                setattr(boss, "story_pre_final_dispatch", True)
                self.story_tags.add("ending:puppet_rematch_gate_done")
            self.controller.add_message("【木偶音效】警报弦音与重低鼓点同时拉响。")
            if side_hit_count <= 0:
                self.controller.add_message(
                    self._resolve_message(
                        payload,
                        "no_side_event_message",
                        "你几乎没在中途触发那些支线干预，它的最终参数按核心读数直接结算，战斗走势更加不可预测。",
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

            puppet_state = self._build_puppet_battle_state(
                payload=payload,
                story_flags=story_flags,
                kind_name=kind_name,
                dark_name=dark_name,
                phase2_name=phase2_name,
            )
            self._apply_puppet_entry_modifiers(monster=boss, state=puppet_state, phase=1)
            puppet_state["phase1_max_hp"] = max(1, int(boss.hp))
            puppet_state["phase1_base_atk"] = max(1, int(boss.atk))
            extension_cfg = {
                "extension_type": "puppet_dark_boss",
                "monster_ref": boss,
                "state": puppet_state,
            }
            if door_is_monster:
                if hasattr(door, "add_battle_extension"):
                    door.add_battle_extension(extension_cfg)
                else:
                    door.battle_extensions = [extension_cfg]
                door.monster = boss
                target_door = door
            else:
                # 选中的是事件门等非怪物门：创建新的怪物门并挂上 Boss，保证与 log_trigger 一致
                target_door = DoorEnum.MONSTER.create_instance(
                    controller=self.controller,
                    monster=boss,
                    battle_extensions=[extension_cfg],
                )
            hint = payload.get("hunter_hint") or payload.get("hint")
            if isinstance(hint, str) and hint.strip():
                target_door.hint = hint.strip()
            self._log_effect_result(
                consequence,
                f"{boss.name} 降临（邪恶值 {evil_value}/100），生命 {boss.hp}，攻击 {boss.atk}",
            )
            return True, target_door

        return False, door

    def setup_test_gate_puppet_final_boss(self) -> Optional[Any]:
        """测试用：直接构建木偶最终 Boss 门（含扩展），不经过 pending_consequences 触发。
        返回可调用 enter() 的门实例；失败返回 None。"""
        consequence = PendingConsequence(
            consequence_id="test_puppet_final_boss",
            source_flag="test",
            effect_key="puppet_dark_boss",
            description="测试用木偶终战",
            payload={},
        )
        dummy_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        applied, new_door = self._apply_effect(consequence, dummy_door)
        return new_door if applied else None

    def _build_puppet_battle_state(
        self,
        payload: Dict[str, Any],
        story_flags: Set[str],
        kind_name: str,
        dark_name: str,
        phase2_name: str,
    ) -> Dict[str, Any]:
        """构建黑暗木偶双阶段战斗状态。"""
        try:
            threshold = float(payload.get("phase2_threshold_ratio", 0.45))
        except (TypeError, ValueError):
            threshold = 0.45
        threshold = max(0.12, min(0.75, threshold))
        try:
            burst_heal_ratio = float(payload.get("phase2_burst_heal_ratio", 0.22))
        except (TypeError, ValueError):
            burst_heal_ratio = 0.22
        burst_heal_ratio = max(0.08, min(0.5, burst_heal_ratio))
        try:
            burst_atk_ratio = float(payload.get("phase2_burst_atk_ratio", 1.12))
        except (TypeError, ValueError):
            burst_atk_ratio = 1.12
        burst_atk_ratio = max(1.03, min(1.5, burst_atk_ratio))
        try:
            phase2_min_hp_ratio = float(payload.get("phase2_min_hp_ratio", 0.0))
        except (TypeError, ValueError):
            phase2_min_hp_ratio = 0.0
        phase2_min_hp_ratio = max(0.0, min(0.85, phase2_min_hp_ratio))
        phase2_enabled = not bool(payload.get("disable_phase_two", False))

        state: Dict[str, Any] = {
            "phase": 1,
            "phase2_started": False,
            "phase2_enabled": phase2_enabled,
            "phase2_name": phase2_name.strip() if isinstance(phase2_name, str) and phase2_name.strip() else f"{dark_name}·黑暗完全体",
            "phase2_threshold_ratio": threshold,
            "phase2_burst_heal_ratio": burst_heal_ratio,
            "phase2_burst_atk_ratio": burst_atk_ratio,
            "phase2_min_hp_ratio": phase2_min_hp_ratio,
            "phase1_entry_modifiers": [],
            "phase2_entry_modifiers": [],
            "runtime_modifiers": [],
            "runtime_trigger_counts": {},
            "kind_name": kind_name,
            "dark_name": dark_name,
        }

        def _add_entry(
            flag: str,
            *,
            phase: int,
            target: str,
            direction: str,
            message: str,
            min_pct: float = 0.05,
            max_pct: float = 0.15,
        ) -> None:
            if flag not in story_flags:
                return
            key = "phase1_entry_modifiers" if phase == 1 else "phase2_entry_modifiers"
            state[key].append(
                {
                    "id": flag,
                    "target": target,
                    "direction": direction,
                    "message": message,
                    "min_pct": max(0.05, float(min_pct)),
                    "max_pct": min(0.15, float(max_pct)),
                }
            )

        def _add_runtime(
            flag: str,
            *,
            trigger: str,
            direction: str,
            message: str,
            chance: float = 0.35,
            active_phase: int = 0,
            min_pct: float = 0.05,
            max_pct: float = 0.15,
        ) -> None:
            if flag not in story_flags:
                return
            state["runtime_modifiers"].append(
                {
                    "id": flag,
                    "trigger": trigger,
                    "direction": direction,
                    "message": message,
                    "chance": max(0.01, min(1.0, float(chance))),
                    "active_phase": max(0, int(active_phase)),
                    "min_pct": max(0.05, float(min_pct)),
                    "max_pct": min(0.15, float(max_pct)),
                }
            )

        # 阶段一开场：只做百分比增减（5%~15%）。
        _add_entry(
            "consumed:puppet_side_minion_once",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你拆过锈蚀的小木偶，开场节奏被你读穿，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_signal_soft",
            phase=1,
            target="boss_hp",
            direction="down",
            message="你此前重放的温和语音样本仍在生效，核心输出收敛，黑暗木偶生命降低 {percent}%。",
        )
        _add_entry(
            "puppet_signal_soft",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你此前重放的温和语音样本干扰了抬手节奏，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_signal_log",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你此前分析过战术日志并补齐反制参数，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_kind_echo_trust",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你曾按善良人格给的路线前进，它仍在底层牵制，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_rift_kind",
            phase=1,
            target="boss_hp",
            direction="down",
            message="裂隙中你护住了善良侧信号通道，黑暗木偶生命降低 {percent}%。",
        )
        _add_entry(
            "puppet_descent_patch",
            phase=1,
            target="boss_hp",
            direction="down",
            message="你此前写入的修复补丁残留生效，黑暗木偶生命降低 {percent}%。",
        )

        # 阶段二开场：部分前情延迟到“完全体爆发”时结算。
        _add_entry(
            "consumed:puppet_side_shop_once",
            phase=2,
            target="boss_hp",
            direction="up",
            message="黑市替它补了装甲片，完全体生命上升 {percent}%。",
        )
        _add_entry(
            "consumed:puppet_side_shop_once",
            phase=2,
            target="boss_atk",
            direction="up",
            message="装甲驱动联动完成，完全体攻击上升 {percent}%。",
        )
        _add_entry(
            "puppet_signal_resell",
            phase=2,
            target="boss_hp",
            direction="up",
            message="你曾把污染片段打包转卖，完全体病毒回灌，生命上升 {percent}%。",
        )
        _add_entry(
            "puppet_rift_dark",
            phase=2,
            target="boss_atk",
            direction="up",
            message="裂隙里你向黑暗侧喂过自毁协议，完全体攻击上升 {percent}%。",
        )
        _add_entry(
            "puppet_descent_dark_feed",
            phase=2,
            target="boss_hp",
            direction="up",
            message="你曾随机录入指令试图控制木偶，指令集中兑现，完全体生命上升 {percent}%。",
        )
        _add_entry(
            "puppet_descent_dark_feed",
            phase=2,
            target="boss_atk",
            direction="up",
            message="你此前录入的随机指令彻底放开限制，完全体攻击上升 {percent}%。",
        )
        _add_entry(
            "puppet_kind_echo_comfort",
            phase=2,
            target="player_hp",
            direction="up",
            message="你曾追问它被抛弃的过去并稳定情绪，蓝光回路在爆发瞬间回补你 {percent}% 当前生命。",
        )

        # 运行时连锁：玩家攻击 / 木偶出招时可重复触发。
        _add_runtime(
            "consumed:puppet_side_trap_once",
            trigger="monster_attack",
            direction="up",
            message="陷阱回廊里木偶病毒曾劫持过你的节拍，在出招时重放，本次木偶伤害提高 {percent}%。",
            chance=0.33,
            active_phase=0,
        )
        _add_runtime(
            "consumed:puppet_side_reward_once",
            trigger="player_attack",
            direction="up",
            message="你曾拿到的应急结界发生器在挥击时校准受力，本次玩家伤害提高 {percent}%。",
            chance=0.36,
            active_phase=0,
        )
        _add_runtime(
            "consumed:puppet_side_reward_once",
            trigger="monster_attack",
            direction="down",
            message="应急结界在受击瞬间展开，本次木偶伤害降低 {percent}%。",
            chance=0.34,
            active_phase=0,
        )
        _add_runtime(
            "puppet_signal_soft",
            trigger="monster_attack",
            direction="down",
            message="你此前重放的温和语音样本拖慢了黑暗抬手，本次木偶伤害降低 {percent}%。",
            chance=0.35,
            active_phase=0,
        )
        _add_runtime(
            "puppet_signal_log",
            trigger="player_attack",
            direction="up",
            message="你此前分析战术日志补齐的反制参数提示了破绽，本次玩家伤害提高 {percent}%。",
            chance=0.4,
            active_phase=0,
        )
        _add_runtime(
            "puppet_kind_echo_trust",
            trigger="monster_attack",
            direction="down",
            message="你曾相信善良人格给的路线，它再次短暂争夺控制，本次木偶伤害降低 {percent}%。",
            chance=0.32,
            active_phase=0,
        )
        _add_runtime(
            "puppet_kind_echo_exploit",
            trigger="monster_attack",
            direction="up",
            message="你曾记录的情感弱点被反向放大，本次木偶伤害提高 {percent}%。",
            chance=0.34,
            active_phase=0,
        )
        _add_runtime(
            "puppet_rift_balance",
            trigger="player_attack",
            direction="up",
            message="你在裂隙维持的双侧平衡参数生效，本次玩家伤害提高 {percent}%。",
            chance=0.28,
            active_phase=0,
        )
        _add_runtime(
            "consumed:puppet_side_shop_once",
            trigger="player_attack",
            direction="down",
            message="黑市装甲片抵消了部分冲击，本次玩家伤害降低 {percent}%。",
            chance=0.35,
            active_phase=2,
        )
        _add_runtime(
            "puppet_signal_resell",
            trigger="monster_attack",
            direction="up",
            message="你此前转卖的污染片段在完全体中继续发酵，本次木偶伤害提高 {percent}%。",
            chance=0.37,
            active_phase=0,
        )
        _add_runtime(
            "puppet_descent_cut_emotion",
            trigger="monster_attack",
            direction="up",
            message="你此前切断了情感模块，完全体再无牵制，本次木偶伤害提高 {percent}%。",
            chance=0.4,
            active_phase=2,
        )
        _add_runtime(
            "puppet_descent_patch",
            trigger="monster_attack",
            direction="down",
            message="你此前写入的修复补丁在关键节点阻断杀意，本次木偶伤害降低 {percent}%。",
            chance=0.3,
            active_phase=0,
        )

        return state

    def _apply_puppet_entry_modifiers(self, monster: Any, state: Dict[str, Any], phase: int) -> None:
        if not isinstance(state, dict):
            return
        key = "phase1_entry_modifiers" if phase == 1 else "phase2_entry_modifiers"
        modifiers = state.get(key, [])
        if not isinstance(modifiers, list):
            return
        player = getattr(self.controller, "player", None)
        for mod in modifiers:
            if not isinstance(mod, dict):
                continue
            min_pct = max(0.05, float(mod.get("min_pct", 0.05)))
            max_pct = min(0.15, float(mod.get("max_pct", 0.15)))
            if max_pct < min_pct:
                min_pct, max_pct = max_pct, min_pct
            pct = random.uniform(min_pct, max_pct)
            pct_text = int(round(pct * 100))
            direction = mod.get("direction", "down")
            target = mod.get("target")
            amount = 0

            if target == "boss_hp":
                before = max(1, int(monster.hp))
                scale = (1.0 + pct) if direction == "up" else max(0.1, 1.0 - pct)
                monster.hp = max(1, int(round(before * scale)))
                amount = abs(monster.hp - before)
            elif target == "boss_atk":
                before = max(1, int(monster.atk))
                scale = (1.0 + pct) if direction == "up" else max(0.1, 1.0 - pct)
                monster.atk = max(1, int(round(before * scale)))
                amount = abs(monster.atk - before)
            elif target == "player_hp" and player is not None:
                base = max(1, int(getattr(player, "hp", 1)))
                delta = max(1, int(round(base * pct)))
                if direction == "up":
                    amount = player.heal(delta)
                else:
                    safe_delta = min(delta, max(0, player.hp - 1))
                    if safe_delta > 0:
                        player.take_damage(safe_delta)
                        amount = safe_delta
            message = mod.get("message", "")
            if isinstance(message, str) and message.strip():
                self.controller.add_message(message.format(percent=pct_text, value=amount))

    def _get_puppet_extension_runtime(self, extension: Dict[str, Any], attacker: Any, defender: Any):
        if not isinstance(extension, dict):
            return None, None
        if extension.get("extension_type") != "puppet_dark_boss":
            return None, None
        monster = extension.get("monster_ref")
        state = extension.get("state")
        if monster is None or not isinstance(state, dict):
            return None, None
        if attacker is not monster and defender is not monster:
            return None, None
        return monster, state

    def _try_trigger_puppet_phase_two(self, extension: Dict[str, Any], target: Any) -> bool:
        """在阶段一生命跌破阈值时，切入黑暗完全体。"""
        if not isinstance(extension, dict) or extension.get("extension_type") != "puppet_dark_boss":
            return False
        monster = extension.get("monster_ref")
        state = extension.get("state")
        if monster is None or target is not monster or not isinstance(state, dict):
            return False
        if not bool(state.get("phase2_enabled", True)):
            return False
        if int(state.get("phase", 1)) >= 2:
            return False
        phase1_max_hp = int(state.get("phase1_max_hp", max(1, int(getattr(monster, "hp", 1)))))
        threshold_ratio = float(state.get("phase2_threshold_ratio", 0.45))
        threshold_hp = max(1, int(round(phase1_max_hp * threshold_ratio)))
        if int(monster.hp) > threshold_hp and int(monster.hp) > 0:
            return False

        state["phase"] = 2
        state["phase2_started"] = True
        old_name = monster.name
        monster.name = state.get("phase2_name", monster.name)

        burst_heal_ratio = float(state.get("phase2_burst_heal_ratio", 0.22))
        burst_heal = max(1, int(round(phase1_max_hp * burst_heal_ratio)))
        phase2_min_hp_ratio = float(state.get("phase2_min_hp_ratio", 0.0))
        phase2_floor_hp = max(1, int(round(phase1_max_hp * max(0.0, phase2_min_hp_ratio))))
        monster.hp = max(max(1, int(monster.hp)) + burst_heal, phase2_floor_hp)

        old_atk = max(1, int(monster.atk))
        burst_atk_ratio = float(state.get("phase2_burst_atk_ratio", 1.12))
        monster.atk = max(1, int(round(old_atk * burst_atk_ratio)))

        self.controller.add_message(
            f"【阶段切换】{old_name}核心炸裂，{monster.name}爆发登场！恢复 {burst_heal} 点生命，攻击抬升至 {monster.atk}。"
        )
        self.controller.add_message("【木偶音效】失真童谣被重低音撕开，完全体战斗主题开始。")
        self._apply_puppet_entry_modifiers(monster=monster, state=state, phase=2)
        return True

    def _apply_puppet_runtime_modifiers(
        self,
        extension: Dict[str, Any],
        trigger: str,
        attacker: Any,
        defender: Any,
        damage: int,
    ) -> int:
        """对木偶最终战扩展应用战斗中可重复触发的百分比修正。"""
        try:
            raw_damage = max(1, int(damage))
        except (TypeError, ValueError):
            return damage
        if raw_damage <= 0:
            return raw_damage

        puppet_monster, state = self._get_puppet_extension_runtime(extension, attacker=attacker, defender=defender)
        if puppet_monster is None or not isinstance(state, dict):
            return raw_damage

        current_phase = max(1, int(state.get("phase", 1)))
        runtime_modifiers = state.get("runtime_modifiers", [])
        if not isinstance(runtime_modifiers, list) or not runtime_modifiers:
            return raw_damage

        factor = 1.0
        triggered = []
        counters = state.get("runtime_trigger_counts")
        if not isinstance(counters, dict):
            counters = {}
            state["runtime_trigger_counts"] = counters

        for mod in runtime_modifiers:
            if not isinstance(mod, dict):
                continue
            if mod.get("trigger") != trigger:
                continue
            active_phase = max(0, int(mod.get("active_phase", 0)))
            if active_phase and current_phase < active_phase:
                continue
            chance = max(0.01, min(1.0, float(mod.get("chance", 0.35))))
            if random.random() > chance:
                continue
            min_pct = max(0.05, float(mod.get("min_pct", 0.05)))
            max_pct = min(0.15, float(mod.get("max_pct", 0.15)))
            if max_pct < min_pct:
                min_pct, max_pct = max_pct, min_pct
            pct = random.uniform(min_pct, max_pct)
            if str(mod.get("direction", "up")).lower() == "down":
                factor *= max(0.15, 1.0 - pct)
            else:
                factor *= 1.0 + pct
            pct_text = int(round(pct * 100))
            msg = mod.get("message", "")
            if isinstance(msg, str) and msg.strip():
                triggered.append(msg.format(percent=pct_text))
            key = f"{mod.get('id', 'unknown')}:{trigger}"
            counters[key] = int(counters.get(key, 0)) + 1

        adjusted = max(1, int(round(raw_damage * factor)))
        for msg in triggered:
            self.controller.add_message(msg)
        if adjusted != raw_damage:
            actor = "木偶" if trigger == "monster_attack" else "玩家"
            self.controller.add_message(f"【连锁结算】{actor}本次伤害 {raw_damage}→{adjusted}。")
        return adjusted

    def apply_door_extension(
        self,
        door: Any,
        extension: Dict[str, Any],
        hook: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """统一门扩展入口：事件对门的改写逻辑集中在此。"""
        if door is None or not isinstance(extension, dict):
            return {}
        ext_type = extension.get("extension_type")
        door_type = getattr(getattr(door, "enum", None), "name", "")
        runtime = self._get_extension_runtime(extension)

        if ext_type == "force_story_event":
            event_key = extension.get("event_key")
            if door_type not in {"EVENT", "SHOP"}:
                return {}
            if not isinstance(event_key, str) or not event_key.strip():
                return {}
            door.story_forced_event_key = event_key.strip()
            hint = extension.get("hint")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            runtime["applied"] = True
            return {"applied": True}

        if ext_type == "elf_side_reward_mark":
            if door_type != "REWARD":
                return {}
            setattr(door, "elf_side_reward", True)
            hint = extension.get("hint")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            runtime["applied"] = True
            return {"applied": True}

        if ext_type == "elf_side_monster_mark":
            if door_type != "MONSTER":
                return {}
            monster = getattr(door, "monster", None)
            if monster is None:
                return {}
            setattr(monster, "elf_side_story", True)
            hint = extension.get("hint")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            runtime["applied"] = True
            return {"applied": True}

        if ext_type == "treasure_marked_item":
            if door_type != "REWARD":
                return {}
            if runtime.get("reward_written"):
                return {"applied": True}
            resolved_reward = extension.get("resolved_reward", {})
            if not isinstance(resolved_reward, dict):
                resolved_reward = {}
            door.reward = dict(resolved_reward)
            runtime["reward_written"] = True
            return {"applied": True}

        if ext_type == "treasure_vanish":
            if door_type != "REWARD":
                return {}
            if runtime.get("reward_written"):
                return {"applied": True}
            resolved_reward = extension.get("resolved_reward", {})
            if not isinstance(resolved_reward, dict):
                resolved_reward = {}
            door.reward = dict(resolved_reward)
            runtime["reward_written"] = True
            return {"applied": True}

        if ext_type == "trap_rewrite_to_reward":
            if door_type != "TRAP" or hook != "before_enter":
                return {}
            if runtime.get("converted"):
                return {"skip_default_enter": True}
            reward = extension.get("reward", {})
            if not isinstance(reward, dict):
                reward = {}
            reward_door = DoorEnum.REWARD.create_instance(
                controller=self.controller,
                reward=dict(reward),
                hint=extension.get("hint", "神佑余辉"),
            )
            runtime["converted"] = True
            return {"replacement_door": reward_door}

        return {}

    def apply_battle_extension(
        self,
        extension: Dict[str, Any],
        trigger: str,
        attacker: Any,
        defender: Any,
        damage: int,
    ) -> int:
        """统一扩展入口：仅处理当前怪物门声明的扩展。"""
        if not isinstance(extension, dict):
            return damage
        ext_type = extension.get("extension_type")
        if ext_type == "puppet_dark_boss":
            return self._apply_puppet_runtime_modifiers(
                extension=extension,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=damage,
            )
        if ext_type == "elf_rival_final_boss":
            return self._apply_elf_rival_runtime_modifiers(
                extension=extension,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=damage,
            )
        return damage

    def handle_battle_extension_post_player_attack(self, extension: Dict[str, Any], target: Any) -> None:
        """统一扩展后处理入口。"""
        if not isinstance(extension, dict):
            return
        ext_type = extension.get("extension_type")
        if ext_type == "puppet_dark_boss":
            self._try_trigger_puppet_phase_two(extension=extension, target=target)
        if ext_type == "elf_rival_final_boss":
            self._try_trigger_elf_rival_counter(extension=extension, target=target)

    # 兼容旧接口：若调用方仍直接走 StorySystem，则透传到当前战斗扩展。
    def apply_puppet_combat_modifiers(self, trigger: str, attacker: Any, defender: Any, damage: int) -> int:
        extensions = getattr(self.controller, "current_battle_extensions", []) or []
        adjusted = damage
        for ext in extensions:
            adjusted = self.apply_battle_extension(
                extension=ext,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=adjusted,
            )
        return adjusted

    def try_trigger_puppet_phase_two(self, monster: Any) -> bool:
        extensions = getattr(self.controller, "current_battle_extensions", []) or []
        switched = False
        for ext in extensions:
            switched = self._try_trigger_puppet_phase_two(extension=ext, target=monster) or switched
        return switched

    def _apply_elf_rival_runtime_modifiers(
        self,
        extension: Dict[str, Any],
        trigger: str,
        attacker: Any,
        defender: Any,
        damage: int,
    ) -> int:
        """银羽终局战斗扩展：根据关系分支提供台词与招式。"""
        state = extension.get("state")
        if not isinstance(state, dict):
            return damage
        runtime = state.setdefault("runtime", {})
        counts = runtime.setdefault("trigger_counts", {})

        adjusted = max(1, int(damage))
        if trigger == "monster_attack":
            idx = int(counts.get("monster_attack", 0))
            boosts = state.get("shadowstep_boost", [])
            lines = state.get("lines", {}) if isinstance(state.get("lines", {}), dict) else {}
            if idx < len(boosts):
                boost = max(0.0, float(boosts[idx]))
                adjusted = max(1, int(round(adjusted * (1.0 + boost))))
                line = lines.get("shadowstep", "")
                if isinstance(line, str) and line.strip():
                    self.controller.add_message(line.strip())
                self.controller.add_message(f"【银羽连携】她抓住你的一瞬迟疑，伤害 {damage}→{adjusted}。")
            counts["monster_attack"] = idx + 1
        return adjusted

    def _try_trigger_elf_rival_counter(self, extension: Dict[str, Any], target: Any) -> None:
        """玩家攻击后判定银羽的扰敌技。"""
        if not target or not bool(getattr(target, "story_elf_rival_final_boss", False)):
            return
        state = extension.get("state")
        if not isinstance(state, dict):
            return
        runtime = state.setdefault("runtime", {})
        counts = runtime.setdefault("trigger_counts", {})
        idx = int(counts.get("post_player_attack", 0))
        turn_cfg = state.get("debuff_turns", [])
        if idx >= len(turn_cfg):
            return
        duration = max(1, int(turn_cfg[idx]))
        mode = str(state.get("debuff_mode", "weak")).strip().lower()
        player = getattr(self.controller, "player", None)
        if player is None:
            return
        effect = StatusName.POISON if mode == "poison" else StatusName.WEAK
        player.apply_status(effect.create_instance(duration=duration, target=player))
        lines = state.get("lines", {}) if isinstance(state.get("lines", {}), dict) else {}
        line = lines.get("debuff", "")
        if isinstance(line, str) and line.strip():
            self.controller.add_message(line.strip())
        label = "中毒" if effect == StatusName.POISON else "虚弱"
        self.controller.add_message(f"【银羽压制】你的节奏被打断，获得{label}（{duration}回合）。")
        counts["post_player_attack"] = idx + 1

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
        # 若 payload 有 log_trigger，说明已在触发时展示合并文案，此处不再重复
        if self._resolve_message(consequence.payload, "log_trigger", ""):
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
        if effect == "default_final_boss":
            self.controller.add_message(f"终局门后的影子拍着手站起来了：{detail}。")
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

    def _create_puppet_minion_monster(self):
        """木偶支线专用：锈蚀追猎偶，独立于一般追猎复仇的数值。"""
        from models.monster import Monster

        round_count = getattr(self.controller, "round_count", 0)
        stage = self._get_progress_stage()
        name = "锈蚀追猎偶"
        if round_count <= 10:
            m = Monster(name=name, hp=42, atk=10, tier=2)
        elif round_count <= 20:
            m = Monster(name=name, hp=58, atk=14, tier=3)
        else:
            m = Monster(name=name, hp=76, atk=20, tier=4)
        if stage > 0:
            m.hp = max(1, int(m.hp * (1 + stage * 0.08)))
            m.atk = max(1, int(m.atk * (1 + stage * 0.06)))
        return m

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
