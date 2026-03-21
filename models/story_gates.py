"""终局门与阻塞顺序的单一配置源。

`PRE_FINAL_GATE_STORY_CONFIG` 为各 gate 的 consequence_id、门型与文案的唯一定义处；
阻塞顺序、结局事件门键与派生集合均由其推导，避免与 `StorySystem` 手写重复。

`models.events` 会 re-export 本模块常用符号以保持兼容。
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Tuple

ALL_PRE_FINAL_DOOR_TYPES: Tuple[str, ...] = ("TRAP", "REWARD", "MONSTER", "SHOP", "EVENT")
ELF_THIEF_NAME = "莱希娅"

PRE_FINAL_GATE_STORY_CONFIG: Dict[str, Dict] = {
    "round200_stage_preface": {
        "choice_flag": "ending_stage_curtain_route",
        "consequence_id": "ending_stage_curtain_preface",
        "effect_key": "stage_curtain_script_vault",
        "force_door_type": "REWARD",
        "priority": 1260,
        "payload": {
            "message": f"你终于明白了{ELF_THIEF_NAME}的就是整件事的起因。",
        },
    },
    "puppet_echo_final_gate": {
        "choice_flag": "ending_puppet_echo_route",
        "consequence_id": "ending_puppet_echo_final_gate",
        "effect_key": "puppet_echo_final_gate",
        "force_door_type": "MONSTER",
        "priority": 1200,
        "payload": {
            "boss_name": "木偶的回声",
            "base_hp": 380,
            "base_atk": 10,
            "tier": 4,
            "message": "门后传来你一路抉择的回响——假面剧场、命运乐谱、银羽飞贼……终局门前，木偶虽败其回声仍在，门扉推开，那些选择一句句被复诵。",
        },
    },
    "round200_default_first_gate": {
        "choice_flag": "ending_default_normal_gate",
        "consequence_id": "ending_default_force_gate_round_200",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_final_first_gate_event",
            "message": "你正要按常规选门，整条走廊的门牌同时翻面；尽头亮起终焉指示灯，三扇最终门从墙体里缓缓推出，迷宫把你推向最后的抉择。",
        },
    },
    "default_second_gate_event": {
        "choice_flag": "ending_default_normal_route",
        "consequence_id": "ending_default_second_gate",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_final_second_gate_event",
            "message": "你刚离开第一道门，前方又升起三扇写着不同命运注脚的门。",
        },
    },
    "stage_curtain_kind_puppet_dialogue": {
        "choice_flag": "ending_stage_curtain_route",
        "consequence_id": "ending_stage_kind_puppet_dialogue",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "stage_curtain_kind_puppet_dialogue_mid_event",
            "message": "你拿到剧本后，此前的机偶胸腔里残存的蓝光人格突然主动与你联络，说它就在后面等着你。",
        },
    },
    "kind_puppet_dialogue_round200": {
        "choice_flag": "ending_stage_curtain_route",
        "consequence_id": "ending_kind_puppet_dialogue_round200",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_stage_kind_puppet_dialogue_event",
            "message": "终局回廊亮起时，机偶胸腔里残存的蓝光人格主动与你联络——说它就在后面等着你。",
        },
    },
    "power_curtain_dialogue_round200": {
        "choice_flag": "ending_power_curtain_choice_route",
        "consequence_id": "ending_power_curtain_dialogue_round200",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_power_curtain_choice_event",
            "message": "终局回廊亮起时，只有你与剧本，你必须做出选择，否则你将永远无法离开。",
        },
    },
    "stage_curtain_gate_event": {
        "choice_flag": "ending_default_normal_route",
        "consequence_id": "ending_stage_curtain_gate",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_stage_curtain_gate_event",
            "message": "你收起剧本后，终局走廊被改写成了新的谢幕门廊，前方三扇门同时亮起。",
        },
    },
    "default_final_boss_gate": {
        "choice_flag": "ending_default_normal_route",
        "consequence_id": "ending_default_final_boss_gate",
        "effect_key": "default_final_boss",
        "force_door_type": "MONSTER",
        "priority": 1200,
        "payload": {
            "boss_name": "选择困难症候群",
            "message": "三扇终局门同时闭合，只剩中央一道裂隙；门后出现一张由问号拼成的笑脸，怪物弯腰行礼：'欢迎来到你的最终选择现场。'",
            "attack_taunts": [
                "\u201c看提示看了两百回合，眼睛还好吗？\u201d",
                "\u201c三扇门你每次都要想半天，这不就是选择困难症吗？\u201d",
                "\u201c来吧，把我打倒，证明你终于会做决定了。\u201d",
                "\u201c又僵住了？我听见你心里还在数门型呢。\u201d",
                "\u201c这一下不用选左中右——痛是单选题。\u201d",
                "\u201c你读事件文本那么细，躲拳头怎么慢半拍？\u201d",
                "\u201c问号挂门上，迟疑写你脸上，挺配。\u201d",
                "\u201c终局了还在算收益？先算算还能挨几下。\u201d",
                "\u201c你一路改主意改到现在，不如先决定要不要还手。\u201d",
                "\u201c别像在商店里比价了，这一拳可不打折。\u201d",
            ],
        },
    },
    "elf_rival_final_gate": {
        "choice_flag": "ending_default_second_gate_rival",
        "consequence_id": "ending_elf_rival_final_gate",
        "effect_key": "elf_rival_final_gate",
        "trigger_door_types": ("MONSTER",),
        "force_door_type": "MONSTER",
        "priority": 1250,
        "payload": {
            "message": "你刚推开门，前方墙体忽然裂开一条缝，银羽飞贼突然从阴影里掠出刺向你，你翻身躲过，她说：'还没结束，我们把旧账在这里算清。'",
        },
    },
    "dream_mirror_prelude_gate": {
        "choice_flag": "ending_dream_mirror_prelude",
        "consequence_id": "ending_dream_mirror_prelude_gate",
        "effect_key": "force_story_event",
        "trigger_door_types": ("EVENT",),
        "force_door_type": "EVENT",
        "priority": 1190,
        "payload": {
            "event_key": "dream_mirror_prelude_event",
            "message": "你推开门，却像跌进一段梦；镜面剧场的预演在梦中一帧一帧回放你曾做过的选择，梦还未醒，终幕的答案已在镜前等你。",
        },
    },
    "puppet_rematch_gate": {
        "choice_flag": "ending_default_second_gate_puppet",
        "consequence_id": "ending_puppet_pre_final_rematch_gate",
        "effect_key": "puppet_dark_boss",
        "trigger_door_types": ("MONSTER",),
        "force_door_type": "MONSTER",
        "priority": 1260,
        "payload": {
            "boss_name": "裂齿·夜魇·游荡残响",
            "phase2_name": "裂齿·夜魇·游荡残响",
            "base_hp": 880,
            "base_atk": 40,
            "tier": 5,
            "message": "你以为已经甩开那段童谣，门缝里却再度传来熟悉的低频拍点；侧墙忽然滑开一扇怪物门，失真的童谣再次响起：黑暗木偶追上来了。",
            "no_side_event_message": "这一次它像在复读你曾见过的战斗节拍，动作没有收束，只剩追杀意图。",
            "neutral_message": "黑暗木偶没有再展开，只是把旧战记录压缩成一段高频猎杀循环。",
            "disable_phase_two": True,
            "mark_as_final_boss": False,
            "pre_final_dispatch": True,
        },
    },
}

# 结局前倒数四类：与 docs/storyline.md PRE_FINAL_BLOCKING_GATE_KEYS 一致
PRE_ENDING_BLOCKING_GATE_KEYS: Tuple[str, ...] = (
    "round200_stage_preface",
    "puppet_rematch_gate",
    "elf_rival_final_gate",
    "dream_mirror_prelude_gate",
)

# 完整阻塞清空顺序：前四为倒数窗口检查项，后二为第 200 回合互斥结局门之一
PRE_FINAL_FULL_BLOCKING_GATE_ORDER: Tuple[str, ...] = PRE_ENDING_BLOCKING_GATE_KEYS + (
    "puppet_echo_final_gate",
    "kind_puppet_dialogue_round200",
)

PRE_FINAL_BLOCKING_GATE_KEYS = PRE_ENDING_BLOCKING_GATE_KEYS

# 结局事件：仅第 200 回合挂载/触发（另有调度侧检查）
ENDING_EVENT_GATE_KEYS: Tuple[str, ...] = (
    "puppet_echo_final_gate",
    "kind_puppet_dialogue_round200",
    "power_curtain_dialogue_round200",
    "round200_default_first_gate",
    "stage_curtain_kind_puppet_dialogue",
)

# schedule_next_pre_final_gate：与阻塞顺序不同，不含银羽秘藏
PRE_FINAL_DISPATCH_ORDER: Tuple[str, ...] = (
    "puppet_rematch_gate",
    "elf_rival_final_gate",
    "dream_mirror_prelude_gate",
    "default_final_boss_gate",
)


def _gate_consequence_id(gate_key: str) -> str:
    return PRE_FINAL_GATE_STORY_CONFIG[gate_key]["consequence_id"]


PRE_FINAL_BLOCKING_ORDER: Tuple[str, ...] = tuple(
    _gate_consequence_id(k) for k in PRE_FINAL_FULL_BLOCKING_GATE_ORDER
)
PRE_FINAL_BLOCKING_CONSEQUENCE_IDS: FrozenSet[str] = frozenset(PRE_FINAL_BLOCKING_ORDER)
PRE_ENDING_BLOCKING_CONSEQUENCE_IDS: FrozenSet[str] = frozenset(
    _gate_consequence_id(k) for k in PRE_ENDING_BLOCKING_GATE_KEYS
)
ENDING_EVENT_CONSEQUENCE_IDS: FrozenSet[str] = frozenset(
    _gate_consequence_id(k) for k in ENDING_EVENT_GATE_KEYS
)

ROUND200_FIRST_GATE_CONSEQUENCE_IDS: Tuple[str, ...] = (
    _gate_consequence_id("round200_default_first_gate"),
    _gate_consequence_id("power_curtain_dialogue_round200"),
)

DEFAULT_ENDING_FORCE_CONSEQUENCE_ID = _gate_consequence_id("round200_default_first_gate")
STAGE_CURTAIN_FORCE_CONSEQUENCE_ID = _gate_consequence_id("round200_stage_preface")
PUPPET_PRE_FINAL_CONSEQUENCE_ID = _gate_consequence_id("puppet_rematch_gate")
ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID = _gate_consequence_id("elf_rival_final_gate")
DREAM_MIRROR_PRELUDE_CONSEQUENCE_ID = _gate_consequence_id("dream_mirror_prelude_gate")
PUPPET_ECHO_FINAL_CONSEQUENCE_ID = _gate_consequence_id("puppet_echo_final_gate")
KIND_PUPPET_DIALOGUE_ROUND200_CONSEQUENCE_ID = _gate_consequence_id("kind_puppet_dialogue_round200")
POWER_CURTAIN_DIALOGUE_ROUND200_CONSEQUENCE_ID = _gate_consequence_id("power_curtain_dialogue_round200")
STAGE_CURTAIN_KIND_PUPPET_DIALOGUE_CONSEQUENCE_ID = _gate_consequence_id(
    "stage_curtain_kind_puppet_dialogue"
)
DEFAULT_SECOND_GATE_CONSEQUENCE_ID = _gate_consequence_id("default_second_gate_event")
DEFAULT_FINAL_BOSS_CONSEQUENCE_ID = _gate_consequence_id("default_final_boss_gate")
