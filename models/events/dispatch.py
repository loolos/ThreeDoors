"""见 models.events 包说明。"""
from models.status import StatusName
from models.story_gates import (
    ALL_PRE_FINAL_DOOR_TYPES,
    ELF_THIEF_NAME,
    ENDING_EVENT_GATE_KEYS,
    PRE_FINAL_DISPATCH_ORDER,
    PRE_FINAL_GATE_STORY_CONFIG,
)
from models.events.base import Event, EventChoice
from models.events._pkg import rng
from .short_random import (
    AncientShrineEvent,
    CursedChestEvent,
    FallenKnightEvent,
    GamblerEvent,
    LostChildEvent,
    RefugeeCaravanEvent,
    SmugglerEvent,
    StrangerEvent,
    WiseSageEvent,
)
from .time_mirror_moon import MirrorTheaterEvent, TimePawnshopEvent
from .moon_verdict import MoonBountyEvent, MoonVerdictEvent
from .clockwork import ClockworkBazaarEvent, CogAuditEvent
from .dream_echo import DreamWellEvent, EchoCourtEvent
from .puppet_chain import (
    PuppetAbandonmentEvent,
    PuppetCoreDescentEvent,
    PuppetKindEchoEvent,
    PuppetPersonaRiftEvent,
    PuppetSignalEvent,
)
from .elf_chain import (
    ElfEpilogueEvent,
    ElfFakeMapEvent,
    ElfFinalHeistEvent,
    ElfHunterGateEvent,
    ElfMonsterStageEvent,
    ElfNightCampEvent,
    ElfRooftopDuelEvent,
    ElfShadowMarkEvent,
    ElfSideMerchantDisguisedEvent,
    ElfSideMerchantEvent,
    ElfSideMonsterEvent,
    ElfThiefIntroEvent,
    ElfTrapRescueEvent,
)
from .stage_curtain import (
    DreamMirrorPreludeEvent,
    EndingFinalFirstGateEvent,
    EndingFinalSecondGateEvent,
    EndingPowerCurtainChoiceEvent,
    EndingPowerCurtainDirectEvent,
    EndingPuppetEchoAftermathEvent,
    EndingStageCurtainGateEvent,
    EndingStageKindPuppetDialogueEvent,
    StageCurtainKindPuppetDialogueMidEvent,
    schedule_next_pre_final_gate,
)


def get_story_event_by_key(event_key, controller):
    event_map = {
        "moon_verdict_event": MoonVerdictEvent,
        "cog_audit_event": CogAuditEvent,
        "echo_court_event": EchoCourtEvent,
        "puppet_signal_event": PuppetSignalEvent,
        "puppet_kind_echo_event": PuppetKindEchoEvent,
        "puppet_persona_rift_event": PuppetPersonaRiftEvent,
        "puppet_core_descent_event": PuppetCoreDescentEvent,
        "elf_shadow_mark_event": ElfShadowMarkEvent,
        "elf_rooftop_duel_event": ElfRooftopDuelEvent,
        "elf_fake_map_event": ElfFakeMapEvent,
        "elf_monster_stage_event": ElfMonsterStageEvent,
        "elf_night_camp_event": ElfNightCampEvent,
        "elf_trap_rescue_event": ElfTrapRescueEvent,
        "elf_hunter_gate_event": ElfHunterGateEvent,
        "elf_final_heist_event": ElfFinalHeistEvent,
        "elf_epilogue_event": ElfEpilogueEvent,
        "elf_side_monster_event": ElfSideMonsterEvent,
        "elf_side_merchant_disguised_event": ElfSideMerchantDisguisedEvent,
        "elf_side_merchant_event": ElfSideMerchantEvent,
        "dream_mirror_prelude_event": DreamMirrorPreludeEvent,
        "ending_stage_kind_puppet_dialogue_event": EndingStageKindPuppetDialogueEvent,
        "stage_curtain_kind_puppet_dialogue_mid_event": StageCurtainKindPuppetDialogueMidEvent,
        "ending_stage_curtain_gate_event": EndingStageCurtainGateEvent,
        "ending_power_curtain_direct_event": EndingPowerCurtainDirectEvent,
        "ending_power_curtain_choice_event": EndingPowerCurtainChoiceEvent,
        "ending_puppet_echo_aftermath_event": EndingPuppetEchoAftermathEvent,
        "ending_final_first_gate_event": EndingFinalFirstGateEvent,
        "ending_final_second_gate_event": EndingFinalSecondGateEvent,
    }
    event_cls = event_map.get(event_key)
    if not event_cls or not _is_event_available(controller, event_cls):
        return None
    return event_cls(controller)


STARTER_EVENT_POOL = [
    StrangerEvent,
    SmugglerEvent,
    AncientShrineEvent,
    GamblerEvent,
    LostChildEvent,
    CursedChestEvent,
    WiseSageEvent,
    RefugeeCaravanEvent,
    FallenKnightEvent,
    TimePawnshopEvent,
    MirrorTheaterEvent,
    MoonBountyEvent,
    ElfThiefIntroEvent,
    ClockworkBazaarEvent,
    DreamWellEvent,
    PuppetAbandonmentEvent,
]


LONG_EVENT_STARTER_CLASSES = {
    TimePawnshopEvent,
    MirrorTheaterEvent,
    MoonBountyEvent,
    ClockworkBazaarEvent,
    DreamWellEvent,
    PuppetAbandonmentEvent,
    ElfThiefIntroEvent,
}

# 随机事件门：长线起始最早可出现于该 round_count（含）；此前只从短线池抽，避免开局即进长线。
LONG_EVENT_STARTER_EARLIEST_ROUND = 21

LONG_EVENT_STARTER_FIRST_TIME_BONUS = 1.8
PREFERRED_LONG_EVENT_WEIGHT_MULTIPLIER = 3.0
PREFERRED_LONG_EVENT_STARTERS = {
    PuppetAbandonmentEvent,
    ElfThiefIntroEvent,
}


def _clamp_probability(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _weighted_pick(event_classes, weights):
    if not event_classes:
        return None
    safe_weights = [max(0.0, float(w)) for w in weights]
    total = sum(safe_weights)
    if total <= 0:
        return rng().choice(event_classes)
    roll = rng().random() * total
    acc = 0.0
    for event_cls, weight in zip(event_classes, safe_weights):
        acc += weight
        if roll <= acc:
            return event_cls
    return event_classes[-1]


RECENT_EVENT_WINDOW = 4  # 最近 N 次事件门内尽量不重复


def _get_event_trigger_counts(controller):
    counts = getattr(controller, "event_trigger_counts", None)
    if counts is None:
        counts = {}
        setattr(controller, "event_trigger_counts", counts)
    return counts


def _get_event_trigger_count(controller, event_cls):
    return int(_get_event_trigger_counts(controller).get(event_cls.__name__, 0))


def _mark_event_triggered(controller, event_cls):
    counts = _get_event_trigger_counts(controller)
    name = event_cls.__name__
    counts[name] = int(counts.get(name, 0)) + 1


def _is_event_available(controller, event_cls):
    if not getattr(event_cls, "ONLY_TRIGGER_ONCE", False):
        return True
    return _get_event_trigger_count(controller, event_cls) <= 0


def _build_event_weight(controller, event_cls):
    base = _clamp_probability(event_cls.get_trigger_probability(controller))
    trigger_count = _get_event_trigger_count(controller, event_cls)
    weight = base

    # 还未触发过的长线起始事件优先级更高。
    if event_cls in LONG_EVENT_STARTER_CLASSES and trigger_count <= 0:
        weight *= LONG_EVENT_STARTER_FIRST_TIME_BONUS

    # 指定长线起始事件（精灵飞贼/黑暗木偶）在随机池中提升到其他长事件的约 3 倍权重。
    if event_cls in PREFERRED_LONG_EVENT_STARTERS:
        weight *= PREFERRED_LONG_EVENT_WEIGHT_MULTIPLIER

    # 可重复事件按触发次数衰减：weight / (1 + 次数)
    if not getattr(event_cls, "ONLY_TRIGGER_ONCE", False):
        weight /= (1 + max(0, trigger_count))

    return max(0.0, weight)


def get_random_event(controller):
    import models.events as ev

    starter_pool = ev.STARTER_EVENT_POOL
    rc = max(0, int(getattr(controller, "round_count", 0)))
    block_long_starters = rc < LONG_EVENT_STARTER_EARLIEST_ROUND

    def _long_starter_ok(event_cls):
        if block_long_starters and event_cls in LONG_EVENT_STARTER_CLASSES:
            return False
        return True

    candidates = [
        event_cls
        for event_cls in starter_pool
        if _long_starter_ok(event_cls)
        and event_cls.is_trigger_condition_met(controller)
        and _is_event_available(controller, event_cls)
    ]
    if not candidates:
        candidates = [
            event_cls
            for event_cls in starter_pool
            if _long_starter_ok(event_cls) and _is_event_available(controller, event_cls)
        ]

    if not candidates:
        candidates = [event_cls for event_cls in starter_pool if _long_starter_ok(event_cls)]

    if not candidates:
        candidates = list(starter_pool)

    rng().shuffle(candidates)

    # 非后续事件门：优先排除最近出现过的类型
    recent = set(getattr(controller, "recent_event_classes", []))
    fresh = [c for c in candidates if c.__name__ not in recent]
    if fresh:
        candidates = fresh

    candidate_weights = [_build_event_weight(controller, event_cls) for event_cls in candidates]
    event_cls = _weighted_pick(candidates, candidate_weights)
    if event_cls is None:
        event_cls = rng().choice(candidates)
    _mark_event_triggered(controller, event_cls)
    return event_cls(controller)


LONG_EVENT_CLASSES = (
    TimePawnshopEvent,
    MirrorTheaterEvent,
    MoonBountyEvent,
    MoonVerdictEvent,
    ClockworkBazaarEvent,
    CogAuditEvent,
    DreamWellEvent,
    EchoCourtEvent,
    PuppetAbandonmentEvent,
    PuppetSignalEvent,
    PuppetKindEchoEvent,
    PuppetPersonaRiftEvent,
    PuppetCoreDescentEvent,
    ElfThiefIntroEvent,
    ElfShadowMarkEvent,
    ElfRooftopDuelEvent,
    ElfFakeMapEvent,
    ElfMonsterStageEvent,
    ElfNightCampEvent,
    ElfTrapRescueEvent,
    ElfHunterGateEvent,
    ElfFinalHeistEvent,
    ElfEpilogueEvent,
)

for _event_cls in LONG_EVENT_CLASSES:
    _event_cls.ONLY_TRIGGER_ONCE = True
