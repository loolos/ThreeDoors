"""剧情事件系统：随机事件、剧情链（木偶/精灵等）及事件选项与回调。

实现拆分为子模块（`base`、`short_random`、`puppet_chain` 等），本包对外 API 与旧版单文件 `events.py` 保持一致。
"""
import random

from models.items import create_random_item, create_reward_door_item
from models.story_gates import (
    ALL_PRE_FINAL_DOOR_TYPES,
    ELF_THIEF_NAME,
    ENDING_EVENT_GATE_KEYS,
    PRE_FINAL_DISPATCH_ORDER,
    PRE_FINAL_GATE_STORY_CONFIG,
)

from models.events.base import Event, EventChoice

from models.events.short_random import (
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
from models.events.time_mirror_moon import MirrorTheaterEvent, TimePawnshopEvent
from models.events.moon_verdict import MoonBountyEvent, MoonVerdictEvent
from models.events.clockwork import ClockworkBazaarEvent, CogAuditEvent
from models.events.dream_echo import DreamWellEvent, EchoCourtEvent
from models.events.puppet_chain import (
    PuppetAbandonmentEvent,
    PuppetCoreDescentEvent,
    PuppetKindEchoEvent,
    PuppetPersonaRiftEvent,
    PuppetSignalEvent,
    build_puppet_final_boss_payload,
)
from models.events.elf_chain import (
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
    _adjust_elf_relation,
)
from models.events.stage_curtain import (
    DreamMirrorPreludeEvent,
    EndingFinalFirstGateEvent,
    EndingFinalSecondGateEvent,
    EndingPowerCurtainChoiceEvent,
    EndingPowerCurtainDirectEvent,
    EndingPuppetEchoAftermathEvent,
    EndingStageCurtainGateEvent,
    EndingStageKindPuppetDialogueEvent,
    StageCurtainKindPuppetDialogueMidEvent,
    _build_stage_epilogue_lines,
    _collect_stage_curtain_scores,
    _resolve_stage_curtain_outcome,
    _should_trigger_dream_mirror_prelude,
    _should_trigger_elf_rival_pre_final,
    _should_trigger_puppet_pre_final_gate,
    run_script_vault_recovery,
    schedule_next_pre_final_gate,
)
from models.events.dispatch import (
    LONG_EVENT_CLASSES,
    LONG_EVENT_STARTER_CLASSES,
    LONG_EVENT_STARTER_EARLIEST_ROUND,
    LONG_EVENT_STARTER_FIRST_TIME_BONUS,
    PREFERRED_LONG_EVENT_STARTERS,
    PREFERRED_LONG_EVENT_WEIGHT_MULTIPLIER,
    RECENT_EVENT_WINDOW,
    STARTER_EVENT_POOL,
    _build_event_weight,
    get_random_event,
    get_story_event_by_key,
)

__all__ = [
    "ALL_PRE_FINAL_DOOR_TYPES",
    "ELF_THIEF_NAME",
    "ENDING_EVENT_GATE_KEYS",
    "Event",
    "EventChoice",
    "LONG_EVENT_CLASSES",
    "LONG_EVENT_STARTER_CLASSES",
    "LONG_EVENT_STARTER_EARLIEST_ROUND",
    "LONG_EVENT_STARTER_FIRST_TIME_BONUS",
    "PREFERRED_LONG_EVENT_STARTERS",
    "PREFERRED_LONG_EVENT_WEIGHT_MULTIPLIER",
    "PRE_FINAL_DISPATCH_ORDER",
    "PRE_FINAL_GATE_STORY_CONFIG",
    "RECENT_EVENT_WINDOW",
    "STARTER_EVENT_POOL",
    "create_random_item",
    "create_reward_door_item",
    "random",
    "get_random_event",
    "get_story_event_by_key",
    "build_puppet_final_boss_payload",
    "schedule_next_pre_final_gate",
    "run_script_vault_recovery",
    "_collect_stage_curtain_scores",
    "_build_stage_epilogue_lines",
    "_resolve_stage_curtain_outcome",
    "_should_trigger_dream_mirror_prelude",
    "_should_trigger_elf_rival_pre_final",
    "_should_trigger_puppet_pre_final_gate",
    "_adjust_elf_relation",
    "_build_event_weight",
]
