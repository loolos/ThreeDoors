import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from models.game_config import GameConfig
from models.door import DoorEnum
from models.items import (
    AttackUpScroll,
    Barrier,
    DepositedBackpack,
    FlyingHammer,
    GiantScroll,
    HealingScroll,
    ImmuneScroll,
    ReviveScroll,
    create_random_item,
)
import models.story_gates as story_gates
from models import story_effects
from models.story_extensions import StoryExtensionsMixin
from models.narrative.elf_rival_grudge import (
    collect_elf_rival_grudge_barks,
    elf_rival_grudge_fillers,
)
from models.narrative import revenge_hunters as narrative_revenge
from models.narrative import story_system_lines as narrative_lines

PRE_FINAL_GATE_STORY_CONFIG = story_gates.PRE_FINAL_GATE_STORY_CONFIG
ALL_PRE_FINAL_DOOR_TYPES = story_gates.ALL_PRE_FINAL_DOOR_TYPES
ENDING_EVENT_GATE_KEYS = story_gates.ENDING_EVENT_GATE_KEYS

# 兼容旧测试与外部 import
_collect_elf_rival_grudge_barks = collect_elf_rival_grudge_barks
_elf_rival_grudge_fillers = elf_rival_grudge_fillers


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


class StorySystem(StoryExtensionsMixin):
    """记录历史选择、道德值与后续影响。"""

    HIGH_MORAL = 30
    LOW_MORAL = -30
    DEFAULT_ENDING_FORCE_ROUND = 200
    PRE_FINAL_WINDOW_START_OFFSET = 15
    PRE_FINAL_WINDOW_END_OFFSET = 10
    PRE_FINAL_RECHECK_INTERVAL = 5
    DEFAULT_ENDING_FORCE_CONSEQUENCE_ID = story_gates.DEFAULT_ENDING_FORCE_CONSEQUENCE_ID
    STAGE_CURTAIN_FORCE_CONSEQUENCE_ID = story_gates.STAGE_CURTAIN_FORCE_CONSEQUENCE_ID
    PUPPET_PRE_FINAL_CONSEQUENCE_ID = story_gates.PUPPET_PRE_FINAL_CONSEQUENCE_ID
    ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID = story_gates.ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID
    DREAM_MIRROR_PRELUDE_CONSEQUENCE_ID = story_gates.DREAM_MIRROR_PRELUDE_CONSEQUENCE_ID
    PUPPET_ECHO_FINAL_CONSEQUENCE_ID = story_gates.PUPPET_ECHO_FINAL_CONSEQUENCE_ID
    KIND_PUPPET_DIALOGUE_ROUND200_CONSEQUENCE_ID = story_gates.KIND_PUPPET_DIALOGUE_ROUND200_CONSEQUENCE_ID
    POWER_CURTAIN_DIALOGUE_ROUND200_CONSEQUENCE_ID = story_gates.POWER_CURTAIN_DIALOGUE_ROUND200_CONSEQUENCE_ID
    STAGE_CURTAIN_KIND_PUPPET_DIALOGUE_CONSEQUENCE_ID = story_gates.STAGE_CURTAIN_KIND_PUPPET_DIALOGUE_CONSEQUENCE_ID

    # 结局事件（第一门）：仅默认第一门、接管谢幕；须在所有结局阻塞清空后才挂载。
    ROUND200_FIRST_GATE_CONSEQUENCE_IDS = story_gates.ROUND200_FIRST_GATE_CONSEQUENCE_IDS
    DEFAULT_SECOND_GATE_CONSEQUENCE_ID = story_gates.DEFAULT_SECOND_GATE_CONSEQUENCE_ID
    DEFAULT_FINAL_BOSS_CONSEQUENCE_ID = story_gates.DEFAULT_FINAL_BOSS_CONSEQUENCE_ID

    PRE_FINAL_BLOCKING_CONSEQUENCE_IDS = story_gates.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS
    PRE_ENDING_BLOCKING_CONSEQUENCE_IDS = story_gates.PRE_ENDING_BLOCKING_CONSEQUENCE_IDS
    ENDING_EVENT_CONSEQUENCE_IDS = story_gates.ENDING_EVENT_CONSEQUENCE_IDS
    PRE_FINAL_BLOCKING_ORDER = story_gates.PRE_FINAL_BLOCKING_ORDER
    # 仅结局前倒数事件：从 185 回合起统一检查并加入阻塞。结局事件仅第 200 回合挂载；门键见 models.story_gates.PRE_FINAL_BLOCKING_GATE_KEYS / ENDING_EVENT_GATE_KEYS。
    PRE_FINAL_BLOCKING_GATE_KEYS = story_gates.PRE_FINAL_BLOCKING_GATE_KEYS

    HIGH_MORAL_MONSTERS = {"树人", "天使", "创世神官", "幽灵", "精灵法师"}
    LOW_MORAL_MONSTERS = {"土匪", "狼人", "食人魔", "冥界使者", "暗影刺客"}
    REVENGE_HUNTER_PROFILES = narrative_revenge.REVENGE_HUNTER_PROFILES

    def __init__(self, controller: Any):
        self.controller = controller
        self.moral_score = 0
        self.choice_flags: Set[str] = set()
        self.story_tags: Set[str] = set()
        self.pending_consequences: Dict[str, PendingConsequence] = {}
        self.consumed_consequences: Set[str] = set()
        self.effect_handlers: Dict[str, Callable[[PendingConsequence, Any], Tuple[bool, Any]]] = {}

        # —— 长线剧情状态：在这里集中声明，各事件/结局直接读写，不再各自用 getattr 默认值 ——
        # 银羽飞贼线
        self.elf_relation: int = 0  # -6 ~ 6，≥2 友好，≤-4 触发终局前清算战
        self.elf_chain_started: bool = False
        self.elf_chain_ended: bool = False
        self.elf_key_obtained: bool = False
        self.elf_middle_queue: List[str] = []
        self.elf_final_outcome: str = ""
        # 黑暗木偶线
        # 0 ~ 100，≤45 善良人格主导，>45 暗侧主导；None 表示木偶线尚未写入（读取时按 55 处理，
        # 木偶终战则改按玩家选项推算），统一用 get_puppet_evil_value() 读取
        self.puppet_evil_value: Optional[int] = None
        self.puppet_kind_persona_name: str = story_gates.PUPPET_KIND_PERSONA_NAME
        self.puppet_dark_persona_name: str = story_gates.PUPPET_DARK_PERSONA_NAME
        self.puppet_side_registered: bool = False
        self.puppet_final_outcome: str = ""  # "" / "defeated" / "escaped"
        self.puppet_patrol_state: str = ""
        self.puppet_patrol_note: str = ""
        # 月蚀通缉线
        self.moon_bounty_diary_source: str = ""
        # 谢幕
        self.curtain_pre_choice: Optional[str] = None
        self.curtain_prelude_choice: Optional[str] = None
        # 终局前倒数窗口
        self.pre_final_last_check_round: Optional[int] = None

    DEFAULT_PUPPET_EVIL_VALUE = 55

    def get_puppet_evil_value(self) -> int:
        """木偶邪恶值（0~100）；木偶线尚未写入时为默认 55。"""
        if self.puppet_evil_value is None:
            return self.DEFAULT_PUPPET_EVIL_VALUE
        return max(0, min(100, int(self.puppet_evil_value)))

    def _get_progress_stage(self) -> int:
        """按回合与玩家基础攻击估算后续影响强度阶段。"""
        round_count = max(0, int(self.controller.round_count))
        player = self.controller.player
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

        current_round = max(0, int(self.controller.round_count))
        # 复仇追猎统一至少延后 3 回合触发，避免“刚结仇立刻遭遇”。
        if effect_key == "revenge_ambush":
            revenge_min_round = current_round + 3
            if min_round is None:
                min_round = revenge_min_round
            else:
                try:
                    min_round = max(int(min_round), revenge_min_round)
                except (TypeError, ValueError):
                    min_round = revenge_min_round
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

    def _is_ending_reached(self) -> bool:
        """是否已经达成任一最终结局。"""
        if self.controller.game_clear_info:
            return True
        return (
            "ending:default_normal_completed" in self.story_tags
            or "ending:stage_curtain_completed" in self.story_tags
        )

    def _is_ending_path_in_flight(self) -> bool:
        """是否已有一条结局门链在途（结局事件/谢幕门/默认第二门/默认 Boss 仍待触发，或战后结局事件待展示）。"""
        if any(cid in self.pending_consequences for cid in story_gates.ENDING_PATH_CONSEQUENCE_IDS):
            return True
        return bool(getattr(self.controller, "pending_post_battle_event_key", None))

    def _schedule_ending_fallback(self) -> bool:
        """兜底：第 200 回合后若阻塞已清空、没有结局门链在途且尚未达成结局，保证默认路线可走通。

        默认第一门尚未用过则挂载第一门；已用过（例如从默认 Boss 处逃跑）则重新挂载默认 Boss 门。
        """
        if self._is_ending_reached() or self._is_ending_path_in_flight():
            return False
        if self.DEFAULT_ENDING_FORCE_CONSEQUENCE_ID not in self.consumed_consequences:
            gate_key = "round200_default_first_gate"
        else:
            gate_key = "default_final_boss_gate"
            self.consumed_consequences.discard(self.DEFAULT_FINAL_BOSS_CONSEQUENCE_ID)
        cfg = PRE_FINAL_GATE_STORY_CONFIG[gate_key]
        payload = cfg.get("payload", {})
        registered = self.register_consequence(
            choice_flag=str(cfg["choice_flag"]),
            consequence_id=str(cfg["consequence_id"]),
            effect_key=str(cfg["effect_key"]),
            chance=1.0,
            trigger_door_types=list(ALL_PRE_FINAL_DOOR_TYPES),
            min_round=self.DEFAULT_ENDING_FORCE_ROUND,
            max_round=None,
            force_on_expire=False,
            force_door_type=str(cfg["force_door_type"]),
            priority=int(cfg.get("priority", 1200)),
            payload=dict(payload) if isinstance(payload, dict) else {},
        )
        if registered:
            self.story_tags.add("ending:default_normal_scheduled")
        return registered

    # 银羽秘藏（补全谢幕前置）仅当飞贼线收束、有钥匙、击败木偶终战且邪恶值偏低（善良人格主导）时挂载
    PUPPET_LOW_EVIL_FOR_CURTAIN = 45
    # 精灵关系友好：elf_relation >= 2；普通或恶劣：<= 1
    ELF_RELATION_FRIENDLY_THRESHOLD = 2
    # 邪恶值中高：> 45
    PUPPET_HIGH_EVIL_FOR_POWER_DIRECT = 45

    def _is_power_curtain_direct_ready(self) -> bool:
        """是否满足接管谢幕直通条件：飞贼事件未完结，或完结但关系为普通/恶劣；已击败黑暗木偶；邪恶值中高。（保留供兼容，决策树首分支已改为木偶回声门。）"""
        if "ending:puppet_final_defeated" not in self.story_tags:
            return False
        try:
            evil = self.get_puppet_evil_value()
        except (TypeError, ValueError):
            evil = 55
        if evil <= self.PUPPET_HIGH_EVIL_FOR_POWER_DIRECT:
            return False
        if not bool(self.elf_chain_ended):
            return True
        rel = int(self.elf_relation)
        return rel < self.ELF_RELATION_FRIENDLY_THRESHOLD

    def _is_puppet_echo_gate_ready(self) -> bool:
        """已击败木偶、未拿飞贼钥匙、与飞贼关系普通或不好时，第 200 回合挂载木偶回声怪物门；击败后即兴谢幕。"""
        if "ending:puppet_final_defeated" not in self.story_tags:
            return False
        key_obtained = bool(self.elf_key_obtained) or ("elf_key_obtained" in self.story_tags)
        if key_obtained:
            return False
        rel = int(self.elf_relation)
        return rel < self.ELF_RELATION_FRIENDLY_THRESHOLD

    def _is_kind_puppet_dialogue_ready(self) -> bool:
        """满足「从飞贼宝藏取回剧本、击败木偶最终 Boss、木偶邪恶值较低」时，第 200 回合可挂载与善良木偶对话结局门。与「邪恶值普通或较高」的接管选择门互斥（本项要求 evil ≤ 45）。"""
        if "curtain_call_script_recovered" not in self.story_tags:
            return False
        if "ending:puppet_final_defeated" not in self.story_tags:
            return False
        evil = self.get_puppet_evil_value()
        return evil <= self.PUPPET_LOW_EVIL_FOR_CURTAIN

    def _is_pre_ending_gate_condition_met(self, gate_key: str) -> bool:
        """结局前阻塞事件：按 gate_key 检查前置条件是否满足（仅条件，不包含是否已在 pending/consumed）。"""
        if gate_key == "round200_stage_preface":
            if not self._is_stage_curtain_route_ready():
                return False
            if "ending:default_normal_completed" in self.story_tags or "ending:stage_curtain_completed" in self.story_tags:
                return False
            return True
        if gate_key == "puppet_rematch_gate":
            try:
                from models.events import _should_trigger_puppet_pre_final_gate
                return bool(_should_trigger_puppet_pre_final_gate(self.controller))
            except Exception:
                return False
        if gate_key == "elf_rival_final_gate":
            try:
                from models.events import _should_trigger_elf_rival_pre_final
                return bool(_should_trigger_elf_rival_pre_final(self.controller))
            except Exception:
                return False
        if gate_key == "dream_mirror_prelude_gate":
            try:
                from models.events import _should_trigger_dream_mirror_prelude
                return bool(_should_trigger_dream_mirror_prelude(self.controller))
            except Exception:
                return False
        return False

    def _is_ending_event_gate(self, gate_key: str) -> bool:
        """是否为结局事件（木偶回声、善良木偶对话、默认第一门、接管谢幕）；此类事件仅到结局回合（第 200 回合）才可挂载/触发。"""
        return gate_key in ENDING_EVENT_GATE_KEYS

    def _is_power_curtain_dialogue_ready(self) -> bool:
        """满足「已拿剧本、已击败木偶、邪恶值普通或较高（> 45）」时，第 200 回合可挂载接管谢幕选择门。与善良木偶对话门互斥（本项要求 evil > 45）。"""
        if "curtain_call_script_recovered" not in self.story_tags:
            return False
        if "ending:puppet_final_defeated" not in self.story_tags:
            return False
        evil = self.get_puppet_evil_value()
        return evil > self.PUPPET_HIGH_EVIL_FOR_POWER_DIRECT

    def _build_puppet_echo_lines(self, high_evil: bool = False) -> list:
        """根据玩家在假面剧场、命运乐谱大盗、飞贼、梦境井、发条等事件中的选择，生成木偶回声战每回合的提及台词；high_evil 时用嘲讽语气，否则陈述。"""
        flags = self.choice_flags.union(self.story_tags)
        lines = []
        # 假面剧场
        if "mirror_played_hero" in flags:
            lines.append("你在假面剧场戴上了英雄的面具。" if not high_evil else "呵，英雄面具戴得可还舒服？")
        if "mirror_played_villain" in flags:
            lines.append("你在假面剧场选择了反派的那一面。" if not high_evil else "反派那面选得挺顺手嘛。")
        if "mirror_tore_script" in flags:
            lines.append("你曾在镜前撕掉过剧本。" if not high_evil else "撕剧本的时候，可没见你手软。")
        # 命运乐谱 / 大盗裁决
        if "moon_verdict_clean" in flags:
            lines.append("命运乐谱大盗的案子上，你判了清白。" if not high_evil else "判清白？你可真是个大善人。")
        if "moon_verdict_burned" in flags:
            lines.append("你在大盗的裁决里选择了焚烧证物。" if not high_evil else "一把火烧干净，省事啊。")
        if "moon_verdict_extorted" in flags:
            lines.append("你在大盗事件里选择了勒索或交易。" if not high_evil else "勒索那手玩得挺熟。")
        # 梦境井 / 回声法庭
        if "dream_well_sealed" in flags or "echo_court_redeemed" in flags:
            lines.append("你封上了梦境井，或让回声法庭得以赎罪。" if not high_evil else "封井、赎罪——你以为这样就能抹平？")
        if "dream_well_drank" in flags:
            lines.append("你喝下了梦境井里的东西。" if not high_evil else "井里的东西你也敢喝。")
        if "dream_well_sold" in flags or "echo_court_trading" in flags:
            lines.append("你把梦卖给了回声法庭。" if not high_evil else "卖梦的滋味如何？")
        # 发条 / 齿轮审计
        if "clockwork_calibrated" in flags:
            lines.append("你在发条事件里选择了校准与秩序。" if not high_evil else "校准、秩序——多听话啊。")
        if "clockwork_hacked" in flags:
            lines.append("你动过发条系统的黑手。" if not high_evil else "黑进发条的时候，可没见你讲规矩。")
        if "clockwork_sabotaged" in flags:
            lines.append("你选择了破坏发条。" if not high_evil else "搞破坏你倒是很在行。")
        # 飞贼结局
        if "elf_outcome:alliance" in flags or "elf_outcome_alliance" in flags:
            lines.append("你和银羽飞贼结成了同盟。" if not high_evil else "跟飞贼同盟？可惜这儿没有钥匙给你。")
        if "elf_outcome:neutral" in flags or "elf_outcome_neutral" in flags:
            lines.append("你和飞贼以中立收场。" if not high_evil else "中立？到头来你什么也没握住。")
        if "elf_outcome:hostile" in flags or "elf_outcome_hostile" in flags:
            lines.append("你和飞贼以敌对收场。" if not high_evil else "跟飞贼闹翻，钥匙自然没你的份。")
        # 木偶线
        if "puppet_kind_echo_trust" in flags or "puppet_rift_kind" in flags:
            lines.append("你曾偏向木偶善良侧的那条线。" if not high_evil else "善良侧？它已经没了。")
        if "puppet_kind_echo_exploit" in flags or "puppet_rift_dark" in flags:
            lines.append("你曾利用或助长了木偶的黑暗侧。" if not high_evil else "黑暗侧养得不错，最后还不是被你砍了。")
        return lines

    def _is_stage_curtain_route_ready(self) -> bool:
        """舞台谢幕链（银羽秘藏取剧本）前置：飞贼事件终结、已拿钥匙、已击败黑暗木偶终战、且尚未取回剧本。

        说明：银羽秘藏是「拿到剧本」的共同入口，既服务于低邪恶值分支（200 回合善良木偶对话），也服务于高邪恶值分支（200 回合接管谢幕选择门）。
        邪恶值门槛应由后续的结局门条件（善良木偶对话 vs 接管选择门）承担，而不是在取回剧本阶段提前切断。
        """
        if "curtain_call_script_recovered" in self.story_tags:
            return False
        key_obtained = bool(self.elf_key_obtained) or ("elf_key_obtained" in self.story_tags)
        if not key_obtained:
            return False
        if not bool(self.elf_chain_ended):
            return False
        if "ending:puppet_final_defeated" not in self.story_tags:
            return False
        return True

    def ensure_stage_curtain_preface_schedule(self) -> bool:
        """满足前置时将“银羽秘藏”纳入终局前倒数窗口调度（仅按门型触发；到 200 回合由「保证对应门型出现」按序触发，不做 max_round 强制替换）。
        现由 ensure_all_pre_ending_blocking_considered 统一调度，本方法保留供单测或兼容调用。"""
        return self._register_single_pre_ending_gate("round200_stage_preface") is not None

    def _register_single_pre_ending_gate(self, gate_key: str) -> Optional[str]:
        """为单个结局前 gate_key 检查条件并注册 consequence；成功返回 gate_key，否则返回 None。"""
        cfg = PRE_FINAL_GATE_STORY_CONFIG.get(gate_key, {})
        if not cfg:
            return None
        consequence_id = str(cfg.get("consequence_id", ""))
        if not consequence_id or consequence_id in self.pending_consequences or consequence_id in self.consumed_consequences:
            return None
        if not self._is_pre_ending_gate_condition_met(gate_key):
            return None
        current_round = max(0, int(self.controller.round_count))
        ending_round = int(self.DEFAULT_ENDING_FORCE_ROUND)
        if gate_key == "round200_stage_preface":
            trigger_door_types = ["REWARD"]
        else:
            trigger_door_types = list(cfg.get("trigger_door_types", []) or list(ALL_PRE_FINAL_DOOR_TYPES))
        payload = cfg.get("payload", {})
        registered = self.register_consequence(
            choice_flag=str(cfg.get("choice_flag", "ending_default_normal_route")),
            consequence_id=consequence_id,
            effect_key=str(cfg.get("effect_key", "force_story_event")),
            chance=1.0,
            trigger_door_types=trigger_door_types,
            min_round=current_round,
            max_round=ending_round,
            force_on_expire=False,
            force_door_type=str(cfg.get("force_door_type", "EVENT")),
            priority=int(cfg.get("priority", 1200)),
            payload=dict(payload) if isinstance(payload, dict) else {},
        )
        if not registered:
            return None
        if gate_key == "round200_stage_preface":
            self.story_tags.add("ending:stage_curtain_scheduled")
        return gate_key

    def ensure_all_pre_ending_blocking_considered(self) -> Tuple[bool, List[str]]:
        """从 185 回合起统一检查结局前倒数事件（银羽宝物、木偶补战、飞贼清算、梦境镜子前奏）；条件满足则加入阻塞。
        木偶回声、善良木偶对话属结局事件，仅在第 200 回合由 _try_schedule_blocking_echo_or_kind 挂载，不在此检查。
        返回 (是否挂载了至少一个, 本次新挂载的 gate_key 列表)。"""
        current_round = max(0, int(self.controller.round_count))
        ending_round = int(self.DEFAULT_ENDING_FORCE_ROUND)
        window_start = max(0, ending_round - int(self.PRE_FINAL_WINDOW_START_OFFSET))
        if current_round < window_start:
            return False, []
        if "ending:default_normal_completed" in self.story_tags or "ending:stage_curtain_completed" in self.story_tags:
            return False, []
        registered_keys = []
        for gate_key in self.PRE_FINAL_BLOCKING_GATE_KEYS:
            key = self._register_single_pre_ending_gate(gate_key)
            if key:
                registered_keys.append(key)
        if "elf_rival_final_gate" in registered_keys:
            self.controller.add_message(narrative_lines.MSG_PRE_FINAL_ELF_RIVAL_REGISTERED)
        if "puppet_rematch_gate" in registered_keys:
            self.controller.add_message(narrative_lines.MSG_PRE_FINAL_PUPPET_REMATCH_REGISTERED)
        return bool(registered_keys), registered_keys

    def _has_pending_blocking_pre_final_events(self) -> bool:
        """是否存在未清空的结局前倒数窗口事件；有则不能挂载默认终局（选择困难症候群）第一门。"""
        return any(cid in self.pending_consequences for cid in self.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS)

    def _all_pre_final_blocking_cleared(self) -> bool:
        """所有结局前倒数窗口事件已清空，可挂载默认终局。"""
        return not self._has_pending_blocking_pre_final_events()

    def get_first_pending_blocking_force_door_type(self) -> Optional[str]:
        """按 PRE_FINAL_BLOCKING_ORDER 返回第一个未清空的结局前阻塞事件所需门型，用于 generate_doors 保证至少一扇对应门出现（200 回合按序触发，不依赖 max_round 强制替换）。"""
        for cid in self.PRE_FINAL_BLOCKING_ORDER:
            c = self.pending_consequences.get(cid)
            if c is not None and getattr(c, "force_door_type", None):
                return str(c.force_door_type)
        return None

    def _get_first_pending_blocking_consequence(self) -> Optional[PendingConsequence]:
        """按 PRE_FINAL_BLOCKING_ORDER 返回第一个仍在 pending 中的结局前阻塞事件；用于第 200 回合强制依次清空列表。"""
        for cid in self.PRE_FINAL_BLOCKING_ORDER:
            c = self.pending_consequences.get(cid)
            if c is not None:
                return c
        return None

    def _all_pre_ending_blocking_cleared(self) -> bool:
        """四种结局前倒数事件（银羽秘藏、木偶补战、飞贼清算、梦境镜子前奏）是否均已清空；结局事件仅在此为 True 且回合≥200 时才可触发。"""
        return not any(cid in self.pending_consequences for cid in self.PRE_ENDING_BLOCKING_CONSEQUENCE_IDS)

    def get_required_door_type_for_next_ending(self, round_count: int) -> Optional[str]:
        """返回当前应保证出现的门型：先按序看结局前阻塞事件，再在 round>=200 时看第 200 回合第一门，再看第二门、默认最终 Boss。供 generate_doors 使用，与取消 force_on_expire 配套。"""
        for cid in self.PRE_FINAL_BLOCKING_ORDER:
            c = self.pending_consequences.get(cid)
            if c is not None and getattr(c, "force_door_type", None):
                return str(c.force_door_type)
        if round_count >= self.DEFAULT_ENDING_FORCE_ROUND:
            for cid in self.ROUND200_FIRST_GATE_CONSEQUENCE_IDS:
                c = self.pending_consequences.get(cid)
                if c is not None and getattr(c, "force_door_type", None):
                    return str(c.force_door_type)
        for cid in (self.DEFAULT_SECOND_GATE_CONSEQUENCE_ID, self.DEFAULT_FINAL_BOSS_CONSEQUENCE_ID):
            c = self.pending_consequences.get(cid)
            if c is not None and getattr(c, "force_door_type", None):
                return str(c.force_door_type)
        return None

    def _should_run_pre_final_recheck(self, *, current_round: int, window_start: int, ending_round: int) -> bool:
        """倒数窗口统一检查：窗口起点 + 每隔固定回合 + 终局回合兜底。"""
        if current_round == ending_round:
            return True
        if current_round == window_start:
            return True
        last_round = self.pre_final_last_check_round
        if not isinstance(last_round, int):
            return True
        return (current_round - last_round) >= int(self.PRE_FINAL_RECHECK_INTERVAL)

    def ensure_pre_final_event_schedule(self) -> bool:
        """从 185 回合起统一检查结局前倒数事件（银羽宝物、木偶补战、飞贼清算、梦境镜子前奏）；条件满足则加入阻塞。
        木偶回声、善良木偶对话为结局事件，仅在第 200 回合挂载；若到 200 仍未触发则由 get_required_door_type_for_next_ending 依序保证门型出现。"""
        if "ending:default_normal_completed" in self.story_tags:
            return False
        if "ending:stage_curtain_completed" in self.story_tags:
            return False

        current_round = max(0, int(self.controller.round_count))
        ending_round = int(self.DEFAULT_ENDING_FORCE_ROUND)
        window_start = max(0, ending_round - int(self.PRE_FINAL_WINDOW_START_OFFSET))
        if current_round < window_start:
            return False
        if not self._should_run_pre_final_recheck(
            current_round=current_round,
            window_start=window_start,
            ending_round=ending_round,
        ):
            return False

        scheduled_any, _ = self.ensure_all_pre_ending_blocking_considered()
        self.pre_final_last_check_round = current_round
        return scheduled_any

    def _try_schedule_blocking_echo_or_kind(self) -> bool:
        """回合 >=200 挂载结局事件：木偶回声或善良木偶对话（二选一按优先级）。

        结局门一旦满足条件就应持续可触发，避免因超过某一回合而失效。"""
        current_round = max(0, int(self.controller.round_count))
        if current_round < self.DEFAULT_ENDING_FORCE_ROUND:
            return False
        for gate_key in ("puppet_echo_final_gate", "kind_puppet_dialogue_round200"):
            if gate_key == "puppet_echo_final_gate" and not self._is_puppet_echo_gate_ready():
                continue
            if gate_key == "kind_puppet_dialogue_round200" and not self._is_kind_puppet_dialogue_ready():
                continue
            cfg = PRE_FINAL_GATE_STORY_CONFIG.get(gate_key, {})
            consequence_id = str(cfg.get("consequence_id", ""))
            if not consequence_id or consequence_id in self.pending_consequences or consequence_id in self.consumed_consequences:
                continue
            door_type = str(cfg.get("force_door_type", "EVENT"))
            payload = cfg.get("payload", {})
            registered = self.register_consequence(
                choice_flag=str(cfg.get("choice_flag", "ending_default_normal_route")),
                consequence_id=consequence_id,
                effect_key=str(cfg.get("effect_key", "force_story_event")),
                chance=1.0,
                trigger_door_types=[door_type],
                min_round=self.DEFAULT_ENDING_FORCE_ROUND,
                max_round=None,
                force_on_expire=False,
                force_door_type=door_type,
                priority=int(cfg.get("priority", 1200)),
                payload=dict(payload) if isinstance(payload, dict) else {},
            )
            if registered:
                return True
        return False

    def ensure_default_normal_ending_schedule(self) -> bool:
        """结局阻塞全部清空后，在第 200 回合挂载结局事件：默认第一门（选择困难症候群）或接管谢幕。木偶回声、善良木偶对话属结局前阻塞，须先清空。"""
        pre_scheduled = self.ensure_pre_final_event_schedule()
        current_round = max(0, int(self.controller.round_count))
        if current_round >= self.DEFAULT_ENDING_FORCE_ROUND and self._try_schedule_blocking_echo_or_kind():
            return True
        if not self._all_pre_final_blocking_cleared():
            return pre_scheduled
        if "ending:default_normal_completed" in self.story_tags:
            return False
        if "ending:stage_curtain_completed" in self.story_tags:
            return False
        if current_round < self.DEFAULT_ENDING_FORCE_ROUND:
            return False
        if self._is_ending_path_in_flight():
            return False
        # 结局事件（仅两种）：接管谢幕（有剧本+邪恶值高）或 默认第一门；都用过仍无结局时走兜底
        if self._is_power_curtain_dialogue_ready():
            gate_key = "power_curtain_dialogue_round200"
        else:
            gate_key = "round200_default_first_gate"
        cfg = PRE_FINAL_GATE_STORY_CONFIG.get(gate_key, {})
        consequence_id = str(cfg.get("consequence_id", "ending_default_force_gate_round_200"))
        if consequence_id in self.pending_consequences or consequence_id in self.consumed_consequences:
            return self._schedule_ending_fallback()
        payload = cfg.get("payload", {})
        registered = self.register_consequence(
            choice_flag=str(cfg.get("choice_flag", "ending_default_normal_gate")),
            consequence_id=consequence_id,
            effect_key=str(cfg.get("effect_key", "force_story_event")),
            chance=1.0,
            trigger_door_types=list(ALL_PRE_FINAL_DOOR_TYPES),
            min_round=self.DEFAULT_ENDING_FORCE_ROUND,
            max_round=None,
            force_on_expire=False,
            force_door_type=str(cfg.get("force_door_type", "EVENT")),
            priority=int(cfg.get("priority", 1200)),
            payload=dict(payload) if isinstance(payload, dict) else {},
        )
        if registered:
            self.story_tags.add("ending:default_normal_scheduled")
        return registered

    def apply_pre_enter_checks(self, door: Any, choice_round: Optional[int] = None) -> Any:
        """选门后、入门前触发检查：先后续影响，再道德影响。
        choice_round: 选门时的回合（若调用方在选门时已把 round_count +1，则传 round_count - 1），未传则用当前 round_count。"""
        door = self._trigger_pending_consequence(door, choice_round=choice_round)
        door = self._trigger_moral_influence(door)
        return door

    def _trigger_pending_consequence(self, door: Any, choice_round: Optional[int] = None) -> Any:
        round_count = self.controller.round_count
        # 选门时 round 已在 handle_choice 开头 +1，强制/匹配用「选门时的回合」判定，避免 190 点的门被当成 191 触发超窗强制
        choice_round = choice_round if choice_round is not None else round_count
        choice_round = max(0, choice_round)
        story_flags = self.choice_flags.union(self.story_tags)
        all_pending = list(self.pending_consequences.values())

        # 方案 A：到 200 回合后，若仍有终盘阻塞未清空，则无视门型按顺序强制清空。
        # 约束：木偶回声/善良木偶对话等「结局事件」必须在四个结局前倒数阻塞清空后才可触发。
        if choice_round >= self.DEFAULT_ENDING_FORCE_ROUND:
            # 1) 优先强制清空四个“结局前倒数阻塞事件”
            if not self._all_pre_ending_blocking_cleared():
                for cid in self.PRE_FINAL_BLOCKING_ORDER:
                    if cid not in self.PRE_ENDING_BLOCKING_CONSEQUENCE_IDS:
                        continue
                    c = self.pending_consequences.get(cid)
                    if c is None:
                        continue
                    apply_door = self._coerce_forced_door(door, c)
                    return self._apply_chosen_consequence(chosen=c, door=apply_door, fallback_door=door, forced=True)

            # 2) 倒数阻塞清空后，再强制清空后续“结局事件阻塞”（木偶回声 / 善良木偶对话）
            for cid in self.PRE_FINAL_BLOCKING_ORDER:
                if cid not in (self.PUPPET_ECHO_FINAL_CONSEQUENCE_ID, self.KIND_PUPPET_DIALOGUE_ROUND200_CONSEQUENCE_ID):
                    continue
                c = self.pending_consequences.get(cid)
                if c is None:
                    continue
                apply_door = self._coerce_forced_door(door, c)
                return self._apply_chosen_consequence(chosen=c, door=apply_door, fallback_door=door, forced=True)

        forced_candidates = [
            c for c in all_pending if c.should_force_trigger(round_count=choice_round, story_flags=story_flags)
        ]
        # 结局前事件不强制替换门：仅当门型匹配时通过下方 candidates 匹配路径触发；get_required_door_type_for_next_ending 保证出现对应门型供玩家选择。
        if forced_candidates:
            # 结局前倒数窗口事件按 PRE_FINAL_BLOCKING_ORDER 优先强制触发（银羽秘藏→木偶补战→飞贼清算），再按回合、优先级。
            order = self.PRE_FINAL_BLOCKING_ORDER
            blocking_ids = self.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS

            def _forced_key(c):
                if c.consequence_id in blocking_ids:
                    try:
                        idx = order.index(c.consequence_id)
                    except (ValueError, TypeError):
                        idx = 999
                else:
                    idx = 999
                return (
                    idx,
                    c.max_round if c.max_round is not None else 10**9,
                    -int(c.priority),
                    c.consequence_id,
                )

            forced_candidates.sort(key=_forced_key)
            chosen = forced_candidates[0]
            apply_door = self._coerce_forced_door(door, chosen)
            return self._apply_chosen_consequence(chosen=chosen, door=apply_door, fallback_door=door, forced=True)

        candidates = [
            c
            for c in all_pending
            if c.matches(door=door, round_count=choice_round, story_flags=story_flags)
        ]
        # 结局事件仅当回合≥200 且结局前阻塞已清空时才可（匹配）触发
        if choice_round < self.DEFAULT_ENDING_FORCE_ROUND or not self._all_pre_ending_blocking_cleared():
            candidates = [c for c in candidates if c.consequence_id not in self.ENDING_EVENT_CONSEQUENCE_IDS]
        door_type = getattr(getattr(door, "enum", None), "name", "")

        if not candidates:
            return door

        candidates = self._apply_pre_final_pending_priority(
            candidates=candidates,
            round_count=choice_round,
        )

        # 多个结局前阻塞事件同时命中时，按 PRE_FINAL_BLOCKING_ORDER 只保留第一个，保证按序触发
        if len(candidates) > 1 and all(
            c.consequence_id in self.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS for c in candidates
        ):
            order = self.PRE_FINAL_BLOCKING_ORDER
            candidates = sorted(
                candidates,
                key=lambda c: order.index(c.consequence_id) if c.consequence_id in order else 999,
            )
            candidates = [candidates[0]]

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

    def _is_in_pre_final_countdown_window(self, round_count: int) -> bool:
        ending_round = int(self.DEFAULT_ENDING_FORCE_ROUND)
        window_start = max(0, ending_round - int(self.PRE_FINAL_WINDOW_START_OFFSET))
        return round_count >= window_start and round_count < ending_round

    def _apply_pre_final_pending_priority(
        self,
        *,
        candidates: List[PendingConsequence],
        round_count: int,
    ) -> List[PendingConsequence]:
        """结局前倒数窗口内，若有未结清前置事件，则 80% 概率优先该事件集合。"""
        if not self._is_in_pre_final_countdown_window(round_count):
            return candidates
        if not self._has_pending_blocking_pre_final_events():
            return candidates

        priority_candidates = [
            c for c in candidates if c.consequence_id in self.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS
        ]
        if not priority_candidates:
            return candidates

        if random.random() >= float(GameConfig.PRE_FINAL_PENDING_PRIORITY_CHANCE):
            return candidates
        return priority_candidates

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
        applied, new_door = self._apply_effect(chosen, door)
        if forced and not applied and chosen.force_door_type:
            # 截止轮次的强制触发至少要保证门被改写到目标类型。
            applied, new_door = True, door
        if applied:
            trigger_message = self._build_trigger_message(chosen)
            if trigger_message:
                self.controller.add_message(trigger_message)
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
        current = self.get_puppet_evil_value()
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
        if consequence.effect_key not in ("revenge_ambush", "puppet_side_minion", "moon_bounty_mid_battle", "elf_rival_final_gate", "puppet_echo_final_gate"):
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
        if defeated and bool(getattr(monster, "story_puppet_echo_final_boss", False)):
            self._resolve_puppet_echo_final_outcome()
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

    def _resolve_puppet_echo_final_outcome(self) -> None:
        """击败木偶的回声后挂载后续事件门（三选一：两种即兴谢幕文案 + 选择困难症），由事件内触发结局。"""
        if "ending:puppet_echo_final_done" in self.story_tags:
            return
        self.story_tags.add("ending:puppet_echo_final_done")
        self.controller.add_message(narrative_lines.MSG_PUPPET_ECHO_SHATTERED)
        self.controller.add_message(narrative_lines.MSG_PUPPET_ECHO_NO_KEY_SCRIPT)
        setattr(self.controller, "pending_post_battle_event_key", "ending_puppet_echo_aftermath_event")

    def _resolve_elf_rival_final_victory(self, monster: Any) -> None:
        """终局前击败飞贼：给出少量终局提示。"""
        if "ending:elf_rival_final_victory" in self.story_tags:
            return
        self.story_tags.add("ending:elf_rival_final_victory")
        self.story_tags.add("ending:elf_rival_final_gate_done")
        self.choice_flags.add("ending_elf_rival_final_victory")
        self.elf_final_outcome = "rival_defeated"
        self.controller.add_message(narrative_lines.MSG_ELF_RIVAL_VICTORY)
        hint = str(getattr(monster, "story_elf_rival_hint", "")).strip()
        if hint:
            self.controller.add_message(hint)
        else:
            self.controller.add_message(narrative_lines.MSG_ELF_RIVAL_DEFAULT_HINT)
        self._schedule_next_pre_final_gate(after_battle=True, defeated=True)

    def _resolve_elf_rival_final_escape(self, monster: Any) -> None:
        """终局前从飞贼战斗撤离：两人彻底别过。"""
        if "ending:elf_rival_parted" in self.story_tags:
            return
        self.story_tags.add("ending:elf_rival_parted")
        self.story_tags.add("ending:elf_rival_final_gate_done")
        self.choice_flags.add("ending_elf_rival_parted")
        self.elf_final_outcome = "rival_parted"
        self.controller.add_message(narrative_lines.MSG_ELF_RIVAL_PARTED)
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
        evil = self.get_puppet_evil_value()
        player = self.controller.player
        if player is None:
            return
        self.puppet_final_outcome = "defeated"
        self.story_tags.add("ending:puppet_final_defeated")
        low_flags = {"puppet_intro_hide", "puppet_signal_soft", "puppet_kind_echo_trust", "puppet_rift_kind", "puppet_descent_patch"}
        high_flags = {"puppet_intro_blackout", "puppet_intro_decoy", "puppet_signal_resell", "puppet_kind_echo_exploit", "puppet_rift_dark", "puppet_descent_dark_feed", "puppet_descent_cut_emotion"}
        flags = set(self.choice_flags)
        low_hits = len(low_flags.intersection(flags))
        high_hits = len(high_flags.intersection(flags))

        bonus_gold = 0
        bonus_items = []
        ending_text = ""
        if evil <= 25:
            bonus_gold = 90
            bonus_items = ["revive_scroll", "barrier"]
            ending_text = "你把它从最深的噪声里拽了回来。机偶胸腔里残存的蓝色灯丝一根根亮起，善良人格把最后的控制权塞回你的手里。"
        elif evil <= 45:
            bonus_gold = 65
            bonus_items = ["attack_up_scroll"]
            ending_text = "黑暗协议被压住大半，裂开的外壳还在冒火花。它靠着墙缓慢坐下，把补给仓权限转交给你。"
        elif evil <= 70:
            bonus_gold = 40
            ending_text = "两个人格在同一段噪声里互相撕扯，最终同时沉默，只剩下可回收的战利品与断续电流声。"
        else:
            bonus_gold = 18
            ending_text = "你虽然赢了，但黑暗协议早把自身切成碎片散入地城深处。走廊尽头只回荡着失真的童谣。"

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

        self.controller.add_message(narrative_lines.MSG_PUPPET_FINAL_MELODY)
        self.controller.add_message(ending_text)
        reward_msg = f"你获得额外 {bonus_gold}G。"
        if item_names:
            reward_msg += f" 额外宝物：{', '.join(item_names)}。"
        if evil <= 25:
            evil_hint = "核心趋于平稳，蓝光曾短暂夺回主导。"
        elif evil <= 45:
            evil_hint = "核心暗噪被压至低语，暗侧未再抬头。"
        elif evil <= 70:
            evil_hint = "核心在红蓝撕扯后归于沉寂，余波未散。"
        else:
            evil_hint = "核心深处仍回荡着强控的余波，暗噪未散。"
        self.controller.add_message(f"{evil_hint} {reward_msg}")

    def _resolve_puppet_final_escape_outcome(self) -> None:
        """木偶终战逃跑分支：记录后续结局参数，不单独触发结局。"""
        if "ending:puppet_final_escape_recorded" in self.story_tags:
            return
        self.story_tags.add("ending:puppet_final_escape_recorded")
        self.choice_flags.add("puppet_final_escape")
        self.puppet_final_outcome = "escaped"
        self.puppet_patrol_state = "active"
        self.puppet_patrol_note = "木偶仍在走廊中来回游荡"
        escape_text = narrative_lines.PUPPET_FINAL_ESCAPE_BODY
        self.controller.add_message(narrative_lines.MSG_PUPPET_FINAL_ESCAPE_FLIGHT)
        self.controller.add_message(escape_text)

    def _schedule_next_pre_final_gate(self, *, after_battle: bool, defeated: bool) -> None:
        """统一调度终局前门链：战后可继续挂载剩余门。"""
        try:
            from models.events import schedule_next_pre_final_gate
        except Exception:
            return
        current_round = max(0, int(self.controller.round_count))
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
            self.controller.add_message(narrative_lines.MSG_AFTER_BATTLE_ELF_RIVAL_GATE)
        elif scheduled_key == "puppet_rematch_gate":
            if defeated:
                self.controller.add_message(narrative_lines.MSG_AFTER_BATTLE_PUPPET_REMATCH_WON)
            else:
                self.controller.add_message(narrative_lines.MSG_AFTER_BATTLE_PUPPET_REMATCH_FLED)

    def _build_final_ending_meta(self) -> Dict[str, Any]:
        """聚合可交给最终结局展示层的剧情参数。"""
        final_meta: Dict[str, Any] = {}
        outcome = str(self.puppet_final_outcome).strip()
        patrol_state = str(self.puppet_patrol_state).strip()
        patrol_note = str(self.puppet_patrol_note).strip()
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
        self.controller.add_message(narrative_lines.MSG_DEFAULT_FINAL_BOSS_DEFEATED)
        self.controller.add_message(narrative_lines.MSG_DEFAULT_NORMAL_EXIT)
        trigger_clear = getattr(self.controller, "trigger_game_clear", None)
        if callable(trigger_clear):
            trigger_clear(
                ending_key="default_normal",
                ending_title="结局:迷宫出口",
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
            self.controller.add_message(narrative_lines.MSG_ELF_SIDE_ALLY_WIN)
            self.elf_relation = max(-6, min(6, int(self.elf_relation) + 1))
        else:
            self.controller.add_message(narrative_lines.MSG_ELF_SIDE_FLEE)
            self.elf_relation = max(-6, min(6, int(self.elf_relation) - 1))

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
        """把一条后果应用到门上：先查运行时注册的 handler，再查 models.story_effects 中的内置 handler。

        返回 (是否生效, 生效后的门)。"""
        effect = consequence.effect_key
        custom_handler = self.effect_handlers.get(effect)
        if custom_handler:
            return custom_handler(consequence, door)
        handler = story_effects.EFFECT_HANDLERS.get(effect)
        if handler is None:
            return False, door
        return handler(self, consequence, door)

    def setup_test_gate_puppet_final_boss(self) -> Optional[Any]:
        """测试用：直接构建木偶最终 Boss 门（含扩展），不经过 pending_consequences 触发。
        从 events.build_puppet_final_boss_payload 取得与正式流程一致的参数，仅将二阶段 burst heal 比例调高以便测试。"""
        from models.events import build_puppet_final_boss_payload

        payload = build_puppet_final_boss_payload(
            self.controller,
            phase2_burst_heal_ratio=0.58,
        )
        consequence = PendingConsequence(
            consequence_id="test_puppet_final_boss",
            source_flag="test",
            effect_key="puppet_dark_boss",
            description="测试用木偶终战",
            payload=payload,
        )
        dummy_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        applied, new_door = self._apply_effect(consequence, dummy_door)
        return new_door if applied else None

    def setup_test_gate_stage_curtain_order(self) -> None:
        """测试用：将控制器与剧情状态设为「补全谢幕」路线前置条件（不挂载门，仅改状态）。
        条件：第 184 回合、玩家 HP 800 / ATK 200、精灵飞贼线已收束且关系高、已拿钥匙、
        已击败黑暗木偶、邪恶值较低；**未**取回剧本，以便 185 回合选门时能挂载并触发银羽秘藏（宝物门取剧本）。
        仅强制清空木偶补战、飞贼清算、梦境镜子前奏三种阻塞（不消费银羽秘藏），185 回合由 ensure_all_pre_ending_blocking_considered 将银羽秘藏加入 pending，选宝物门即触发；取剧本后可走约定对话，到 200 回合挂载善良木偶对话。"""
        c = self.controller
        c.round_count = 184
        p = c.player
        if p is not None:
            p.hp = 800
            p._atk = 200
            c.player_peak_hp = 800
            c.player_peak_atk = 200
        self.elf_chain_started = True
        self.elf_chain_ended = True
        self.elf_relation = 4
        self.elf_key_obtained = True
        self.story_tags.add("elf_chain_ended")
        self.story_tags.add("elf_key_obtained")
        self.story_tags.add("ending:puppet_final_defeated")
        self.puppet_final_outcome = "defeated"
        self.puppet_evil_value = 30
        # 不设置 curtain_call_script_recovered，满足 _is_stage_curtain_route_ready() 中「未取回剧本」条件，185 回合才能挂载银羽秘藏
        # 只清空另外三种结局前倒数事件，不消费银羽秘藏，让 185 回合时由调度把银羽秘藏加入 pending、选宝物门触发
        for cid in (
            self.PUPPET_PRE_FINAL_CONSEQUENCE_ID,
            self.ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID,
            self.DREAM_MIRROR_PRELUDE_CONSEQUENCE_ID,
        ):
            self.pending_consequences.pop(cid, None)
            self.consumed_consequences.add(cid)

    def setup_test_gate_puppet_echo(self) -> None:
        """测试用：将控制器与剧情状态设为「木偶回声门」前置（不挂载门，仅改状态）。
        条件：回合 190、玩家 HP 800 / ATK 200、飞贼线已完结但未拿钥匙（敌对收束）、
        与飞贼关系 ≤-4 以便在倒数窗口内触发飞贼清算战；木偶线已完结且为击败结局（非逃跑），较高邪恶值。
        调用方需在第 200 回合调用 ensure_default_normal_ending_schedule() 以挂载回声门等终局门。"""
        c = self.controller
        c.round_count = 190
        p = c.player
        if p is not None:
            p.hp = 800
            p._atk = 200
            c.player_peak_hp = 800
            c.player_peak_atk = 200
        self.elf_chain_ended = True
        self.elf_relation = -5
        self.elf_key_obtained = False
        self.story_tags.add("elf_chain_ended")
        self.story_tags.add("elf_outcome:hostile")
        self.story_tags.add("ending_hook:elf_hostile")
        self.story_tags.discard("elf_key_obtained")
        self.choice_flags.add("elf_outcome_hostile")
        self.story_tags.discard("puppet_arc_active")
        self.story_tags.discard("ending:puppet_final_escape_recorded")
        self.story_tags.add("ending:puppet_final_defeated")
        self.puppet_evil_value = 55

    def setup_test_gate_stage_curtain_power(self) -> None:
        """测试用：将控制器与剧情状态设为「接管谢幕」结局门更容易就绪的前置（不挂载门，仅改状态）。
        条件：回合 190、玩家 HP 800 / ATK 200、飞贼线已收束且关系较好、已拿钥匙；
        木偶线已完结且为击败结局（非逃跑），邪恶值较高（>45）。

        说明：该配置意在让玩家能在倒数窗口内触发银羽秘藏取回剧本，随后在 200 回合清空阻塞后，
        有机会挂载「接管谢幕选择门」（要求：已取回剧本 + 已击败木偶 + 邪恶值 > 45）。"""
        c = self.controller
        c.round_count = 190
        p = c.player
        if p is not None:
            p.hp = 800
            p._atk = 200
            c.player_peak_hp = 800
            c.player_peak_atk = 200

        self.elf_chain_ended = True
        self.elf_relation = 4
        self.elf_key_obtained = True
        self.story_tags.add("elf_chain_ended")
        self.story_tags.add("elf_key_obtained")
        self.story_tags.discard("elf_outcome:hostile")
        self.story_tags.discard("ending_hook:elf_hostile")
        self.choice_flags.discard("elf_outcome_hostile")
        self.choice_flags.add("elf_outcome_alliance")
        self.story_tags.add("ending_hook:elf_alliance")

        self.story_tags.discard("puppet_arc_active")
        self.story_tags.discard("ending:puppet_final_escape_recorded")
        self.story_tags.add("ending:puppet_final_defeated")
        self.puppet_evil_value = 55

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

    def _append_effect_values(self, message: str, *parts: str) -> str:
        detail_parts = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
        if not detail_parts:
            return message
        detail_text = "，".join(detail_parts)
        base = (message or "").strip()
        if not base:
            return f"（本次变化：{detail_text}）"
        return f"{base}（本次变化：{detail_text}）"

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
        if not custom and consequence.effect_key != "lose_gold":
            custom = self._resolve_message(consequence.payload, "message", "")
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
        # 若 payload 有 log_trigger 或 message（已用于触发文案），此处不再重复
        if self._resolve_message(consequence.payload, "log_trigger", "") or self._resolve_message(consequence.payload, "message", ""):
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
        if effect == "stage_curtain_script_vault":
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
            "deposit_backpack": lambda: DepositedBackpack(name="寄存的背包", cost=0),
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

        round_count = self.controller.round_count
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

        round_count = self.controller.round_count
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
