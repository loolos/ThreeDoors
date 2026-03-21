"""故事状态标记单一索引（choice_flags / story_tags 等）。

与叙事设计文档交叉引用：``docs/storyline.md`` §9「相关代码位置」。

**两类容器（``StorySystem``）**
- ``choice_flags``：玩家分支选项产生的**离散标记**（多为 ``register_choice`` / ``register_story_choice`` 写入）。
- ``story_tags``：更广义的剧情标签；其中 ``register_choice`` 会同步写入 ``choice:<flag>``，与 ``choice_flags`` 一一对应。

**勿与** ``models/story_gates.py`` **混淆**：后者是终局门型、阻塞顺序与 ``consequence_id`` 的配置；本模块是**字符串 flag 的登记与查阅**。

**木偶动态 choice_flag**：用 ``puppet_intro_flag`` / ``puppet_rift_flag`` / ``puppet_descent_flag`` 拼接；
  完整展开名另有 ``PUPPET_INTRO_HIDE`` 等常量（Boss payload 的 kind/dark 列表用）。
- ``puppet_evil_bucket:<bucket>``（邪恶值分桶，``story_system``）
- ``moon_bounty_diary_source:<...>``、``moon_bounty_route:<...>``（月蚀线）
- ``consumed:<consequence_id>``（已结算后果）
- 部分连锁后果默认 ``chain:<consequence_id>``（``story_system`` 内）
"""

from __future__ import annotations

from typing import Final, FrozenSet, Iterable, Tuple

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def choice_tag(choice_flag: str) -> str:
    """与 ``StorySystem.register_choice`` 写入的 ``story_tags`` 前缀一致。"""
    return f"choice:{choice_flag}"


def frozen_choice_values(locals_dict: dict) -> FrozenSet[str]:
    """收集本模块内 ``str`` 常量（全大写名、值非空），供测试做唯一性检查。"""
    out: set[str] = set()
    for k, v in locals_dict.items():
        if k.isupper() and isinstance(v, str) and v and not k.startswith("_"):
            out.add(v)
    return frozenset(out)


# ---------------------------------------------------------------------------
# 飞贼仇怨（``elf_chain._record_elf_grudge`` / 清算战台词顺序）
# ---------------------------------------------------------------------------

ELF_GRUDGE_HEIST_BETRAYED: Final = "elf_grudge_heist_betrayed"
ELF_GRUDGE_HUNTER_FLED: Final = "elf_grudge_hunter_fled"
ELF_GRUDGE_EPILOGUE_BURNED: Final = "elf_grudge_epilogue_burned"
ELF_GRUDGE_ROOFTOP_SNEAK: Final = "elf_grudge_rooftop_sneak"
ELF_GRUDGE_INTRO_FAKE_GUARD: Final = "elf_grudge_intro_fake_guard"
ELF_GRUDGE_MAP_SOLD_OUT: Final = "elf_grudge_map_sold_out"
ELF_GRUDGE_HUNTER_LOOT_GRAB: Final = "elf_grudge_hunter_loot_grab"
ELF_GRUDGE_SHADOW_THREATEN: Final = "elf_grudge_shadow_threaten"
ELF_GRUDGE_TRAP_ORDERED: Final = "elf_grudge_trap_ordered"
ELF_GRUDGE_CAMP_REFUSED_HELP: Final = "elf_grudge_camp_refused_help"
ELF_GRUDGE_CAMP_MERCENARY: Final = "elf_grudge_camp_mercenary"
ELF_GRUDGE_STAGE_REFUSED: Final = "elf_grudge_stage_refused"
ELF_GRUDGE_HEIST_SIDE_ROUTE: Final = "elf_grudge_heist_side_route"

# 台词优先顺序（与 ``narrative/elf_rival_grudge`` 中列表顺序必须一致）
ELF_GRUDGE_BARK_KEYS: Final[Tuple[str, ...]] = (
    ELF_GRUDGE_HEIST_BETRAYED,
    ELF_GRUDGE_HUNTER_FLED,
    ELF_GRUDGE_EPILOGUE_BURNED,
    ELF_GRUDGE_ROOFTOP_SNEAK,
    ELF_GRUDGE_INTRO_FAKE_GUARD,
    ELF_GRUDGE_MAP_SOLD_OUT,
    ELF_GRUDGE_HUNTER_LOOT_GRAB,
    ELF_GRUDGE_SHADOW_THREATEN,
    ELF_GRUDGE_TRAP_ORDERED,
    ELF_GRUDGE_CAMP_REFUSED_HELP,
    ELF_GRUDGE_CAMP_MERCENARY,
    ELF_GRUDGE_STAGE_REFUSED,
    ELF_GRUDGE_HEIST_SIDE_ROUTE,
)

# ---------------------------------------------------------------------------
# 短随机事件 ``events/short_random.py``
# ---------------------------------------------------------------------------

STRANGER_HELPED: Final = "stranger_helped"
STRANGER_ROBBED: Final = "stranger_robbed"
STRANGER_IGNORED: Final = "stranger_ignored"
SMUGGLER_BOUGHT_GOODS: Final = "smuggler_bought_goods"
SMUGGLER_REPORTED: Final = "smuggler_reported"
SMUGGLER_LEFT: Final = "smuggler_left"
SHRINE_PRAYED: Final = "shrine_prayed"
SHRINE_DESECRATED: Final = "shrine_desecrated"
SHRINE_INSPECTED: Final = "shrine_inspected"
GAMBLER_HIGH_STAKES: Final = "gambler_high_stakes"
GAMBLER_LOW_STAKES: Final = "gambler_low_stakes"
GAMBLER_DECLINED: Final = "gambler_declined"
LOST_CHILD_GUIDED_HOME: Final = "lost_child_guided_home"
LOST_CHILD_GAVE_GOLD: Final = "lost_child_gave_gold"
LOST_CHILD_IGNORED: Final = "lost_child_ignored"
CURSED_CHEST_OPENED: Final = "cursed_chest_opened"
CURSED_CHEST_PURIFIED: Final = "cursed_chest_purified"
CURSED_CHEST_LEFT: Final = "cursed_chest_left"
SAGE_POWER_CHOICE: Final = "sage_power_choice"
SAGE_WEALTH_CHOICE: Final = "sage_wealth_choice"
SAGE_HEALTH_CHOICE: Final = "sage_health_choice"
CARAVAN_DONATED: Final = "caravan_donated"
CARAVAN_EXTORTED: Final = "caravan_extorted"
CARAVAN_IGNORED: Final = "caravan_ignored"
KNIGHT_AIDED: Final = "knight_aided"
KNIGHT_LOOTED: Final = "knight_looted"
KNIGHT_LEFT: Final = "knight_left"

# ---------------------------------------------------------------------------
# 月蚀通缉 / 审判 ``events/moon_verdict.py``
# ---------------------------------------------------------------------------

MOON_BOUNTY_ACCEPT: Final = "moon_bounty_accept"
MOON_BOUNTY_PROTECT: Final = "moon_bounty_protect"
MOON_BOUNTY_DOUBLE: Final = "moon_bounty_double"
MOON_VERDICT_CLEAN: Final = "moon_verdict_clean"
MOON_VERDICT_BURNED: Final = "moon_verdict_burned"
MOON_VERDICT_EXTORTED: Final = "moon_verdict_extorted"

# ---------------------------------------------------------------------------
# 齿轮售票 / 查票 ``events/clockwork.py``
# ---------------------------------------------------------------------------

CLOCKWORK_CALIBRATED: Final = "clockwork_calibrated"
CLOCKWORK_HACKED: Final = "clockwork_hacked"
CLOCKWORK_SABOTAGED: Final = "clockwork_sabotaged"
COG_AUDIT_TAX_PAID: Final = "cog_audit_tax_paid"
COG_AUDIT_FAKED: Final = "cog_audit_faked"
COG_AUDIT_SILENCED: Final = "cog_audit_silenced"

# ---------------------------------------------------------------------------
# 时光当铺 / 镜面 ``events/time_mirror_moon.py``
# ---------------------------------------------------------------------------

TIME_PAWNED_FUTURE: Final = "time_pawned_future"
TIME_REDEEMED_DEBT: Final = "time_redeemed_debt"
TIME_BROKE_HOURGLASS: Final = "time_broke_hourglass"
MIRROR_PLAYED_HERO: Final = "mirror_played_hero"
MIRROR_PLAYED_VILLAIN: Final = "mirror_played_villain"
MIRROR_TORE_SCRIPT: Final = "mirror_tore_script"

# ---------------------------------------------------------------------------
# 梦境井 / 回声法庭 ``events/dream_echo.py``
# ---------------------------------------------------------------------------

DREAM_WELL_DRANK: Final = "dream_well_drank"
DREAM_WELL_SEALED: Final = "dream_well_sealed"
DREAM_WELL_SOLD: Final = "dream_well_sold"
ECHO_COURT_REDEEMED: Final = "echo_court_redeemed"
ECHO_COURT_TAXED: Final = "echo_court_taxed"
ECHO_COURT_TRADING: Final = "echo_court_trading"

# ---------------------------------------------------------------------------
# 木偶线 ``events/puppet_chain.py``（静态部分）
# ---------------------------------------------------------------------------

PUPPET_SIDE_REG: Final = "puppet_side_reg"
PUPPET_SIGNAL_SOFT: Final = "puppet_signal_soft"
PUPPET_SIGNAL_LOG: Final = "puppet_signal_log"
PUPPET_SIGNAL_RESELL: Final = "puppet_signal_resell"
PUPPET_KIND_ECHO_TRUST: Final = "puppet_kind_echo_trust"
PUPPET_KIND_ECHO_COMFORT: Final = "puppet_kind_echo_comfort"
PUPPET_KIND_ECHO_EXPLOIT: Final = "puppet_kind_echo_exploit"

PUPPET_INTRO_ROUTES: Final[Tuple[str, ...]] = ("hide", "blackout", "decoy")
PUPPET_RIFT_ROUTES: Final[Tuple[str, ...]] = ("kind", "balance", "dark")
PUPPET_DESCENT_ROUTES: Final[Tuple[str, ...]] = ("patch", "cut_emotion", "dark_feed")

PUPPET_INTRO_HIDE: Final = "puppet_intro_hide"
PUPPET_INTRO_BLACKOUT: Final = "puppet_intro_blackout"
PUPPET_INTRO_DECOY: Final = "puppet_intro_decoy"
PUPPET_RIFT_KIND: Final = "puppet_rift_kind"
PUPPET_RIFT_BALANCE: Final = "puppet_rift_balance"
PUPPET_RIFT_DARK: Final = "puppet_rift_dark"
PUPPET_DESCENT_PATCH: Final = "puppet_descent_patch"
PUPPET_DESCENT_CUT_EMOTION: Final = "puppet_descent_cut_emotion"
PUPPET_DESCENT_DARK_FEED: Final = "puppet_descent_dark_feed"
PUPPET_MAINLINE_CHOICE_PREFIX: Final = "puppet_mainline:"


def puppet_intro_flag(route: str) -> str:
    return f"puppet_intro_{route}"


def puppet_rift_flag(route_flag: str) -> str:
    return f"puppet_rift_{route_flag}"


def puppet_descent_flag(route: str) -> str:
    return f"puppet_descent_{route}"

# ---------------------------------------------------------------------------
# 飞贼线 ``events/elf_chain.py``
# ---------------------------------------------------------------------------

ELF_HUNTER_GATE_TEAM_UP: Final = "elf_hunter_gate_team_up"
ELF_SIDE_REG: Final = "elf_side_reg"

# ---------------------------------------------------------------------------
# 谢幕 / 终局门内选择 ``events/stage_curtain.py``
# ---------------------------------------------------------------------------

CURTAIN_SCRIPT_SECURED: Final = "curtain_script_secured"
CURTAIN_PRELUDE_ORDER: Final = "curtain_prelude_order"
CURTAIN_PRELUDE_FREEDOM: Final = "curtain_prelude_freedom"
CURTAIN_PRELUDE_POWER: Final = "curtain_prelude_power"
ENDING_STAGE_GATE_ORDER: Final = "ending_stage_gate_order"
ENDING_STAGE_GATE_FREEDOM: Final = "ending_stage_gate_freedom"
ENDING_STAGE_GATE_DEFAULT: Final = "ending_stage_gate_default"
ENDING_STAGE_GATE_POWER: Final = "ending_stage_gate_power"
ENDING_STAGE_GATE_ORDER_PRE_CHOSEN: Final = "ending_stage_gate_order_pre_chosen"
ENDING_STAGE_GATE_FREEDOM_PRE_CHOSEN: Final = "ending_stage_gate_freedom_pre_chosen"
ENDING_POWER_CURTAIN_DIRECT: Final = "ending_power_curtain_direct"
ENDING_POWER_CURTAIN_CHOICE: Final = "ending_power_curtain_choice"
ENDING_POWER_CURTAIN_CHOICE_DEFAULT: Final = "ending_power_curtain_choice_default"
ENDING_PUPPET_ECHO_AFTERMATH_DEFAULT: Final = "ending_puppet_echo_aftermath_default"
ENDING_DEFAULT_FIRST_GATE_HASTY: Final = "ending_default_first_gate_hasty"
ENDING_DEFAULT_FIRST_GATE_HESITATE: Final = "ending_default_first_gate_hesitate"
ENDING_DEFAULT_FIRST_GATE_WHATEVER: Final = "ending_default_first_gate_whatever"
ENDING_DEFAULT_SECOND_GATE_LEFT: Final = "ending_default_second_gate_left"
ENDING_DEFAULT_SECOND_GATE_MIDDLE: Final = "ending_default_second_gate_middle"
ENDING_DEFAULT_SECOND_GATE_RIGHT: Final = "ending_default_second_gate_right"

# ---------------------------------------------------------------------------
# ``story_system`` 直接写入的 choice_flags（非事件 register_story_choice）
# ---------------------------------------------------------------------------

ENDING_ELF_RIVAL_FINAL_VICTORY: Final = "ending_elf_rival_final_victory"
ENDING_ELF_RIVAL_PARTED: Final = "ending_elf_rival_parted"
PUPPET_FINAL_ESCAPE: Final = "puppet_final_escape"
ENDING_DEFAULT_NORMAL_COMPLETED: Final = "ending_default_normal_completed"
ELF_OUTCOME_HOSTILE: Final = "elf_outcome_hostile"
ELF_OUTCOME_ALLIANCE: Final = "elf_outcome_alliance"

ENDING_DEFAULT_NORMAL_ROUTE: Final = "ending_default_normal_route"
ENDING_DEFAULT_NORMAL_GATE: Final = "ending_default_normal_gate"

# ---------------------------------------------------------------------------
# 常用 story_tags（直接 ``story_tags.add``，无 choice: 前缀）
# ---------------------------------------------------------------------------

TAG_ENDING_STAGE_CURTAIN_SCHEDULED: Final = "ending:stage_curtain_scheduled"
TAG_ENDING_STAGE_CURTAIN_COMPLETED: Final = "ending:stage_curtain_completed"
TAG_ENDING_STAGE_CURTAIN_POWER: Final = "ending:stage_curtain:power"
TAG_ENDING_STAGE_CURTAIN_FREEDOM: Final = "ending:stage_curtain:freedom"
TAG_ENDING_DEFAULT_NORMAL_SCHEDULED: Final = "ending:default_normal_scheduled"
TAG_ENDING_DEFAULT_NORMAL_COMPLETED: Final = "ending:default_normal_completed"
TAG_ENDING_PUPPET_FINAL_DEFEATED: Final = "ending:puppet_final_defeated"
TAG_ENDING_PUPPET_FINAL_ESCAPE_RECORDED: Final = "ending:puppet_final_escape_recorded"
TAG_ENDING_PUPPET_ECHO_FINAL_DONE: Final = "ending:puppet_echo_final_done"
TAG_ENDING_PUPPET_REMATCH_GATE_PENDING: Final = "ending:puppet_rematch_gate_pending"
TAG_ENDING_PUPPET_REMATCH_GATE_DONE: Final = "ending:puppet_rematch_gate_done"
TAG_ENDING_ELF_RIVAL_FINAL_VICTORY: Final = "ending:elf_rival_final_victory"
TAG_ENDING_ELF_RIVAL_FINAL_GATE_DONE: Final = "ending:elf_rival_final_gate_done"
TAG_ENDING_ELF_RIVAL_PARTED: Final = "ending:elf_rival_parted"
TAG_MOON_BOUNTY_MID_BATTLE_CLEARED: Final = "moon_bounty_mid_battle_cleared"
TAG_MOON_BOUNTY_DIARY_OBTAINED: Final = "moon_bounty_diary_obtained"
TAG_ELF_CHAIN_ENDED: Final = "elf_chain_ended"
TAG_ELF_KEY_OBTAINED: Final = "elf_key_obtained"
TAG_ELF_MET: Final = "elf_met"
TAG_ELF_OUTCOME_HOSTILE: Final = "elf_outcome:hostile"
TAG_ENDING_HOOK_ELF_HOSTILE: Final = "ending_hook:elf_hostile"
TAG_ENDING_HOOK_ELF_ALLIANCE: Final = "ending_hook:elf_alliance"
TAG_PUPPET_ARC_ACTIVE: Final = "puppet_arc_active"
TAG_CURTAIN_CALL_SCRIPT_RECOVERED: Final = "curtain_call_script_recovered"
TAG_CURTAIN_CALL_TRUTH_REVEALED: Final = "curtain_call_truth_revealed"

# ---------------------------------------------------------------------------
# 文档用：分类索引（flag 或前缀、简短说明）
# ---------------------------------------------------------------------------

FLAG_INDEX: Final[Tuple[Tuple[str, str, str], ...]] = (
    ("choice", STRANGER_HELPED, "受伤陌生人：救助"),
    ("choice", STRANGER_ROBBED, "受伤陌生人：抢劫"),
    ("choice", STRANGER_IGNORED, "受伤陌生人：无视"),
    ("choice", SMUGGLER_BOUGHT_GOODS, "走私犯：购买"),
    ("choice", SMUGGLER_REPORTED, "走私犯：举报"),
    ("choice", SMUGGLER_LEFT, "走私犯：离开"),
    ("choice", MOON_BOUNTY_ACCEPT, "月蚀：接单追猎"),
    ("choice", MOON_BOUNTY_PROTECT, "月蚀：护送"),
    ("choice", MOON_BOUNTY_DOUBLE, "月蚀：双线欺诈"),
    ("tag", TAG_PUPPET_ARC_ACTIVE, "木偶主线已激活"),
    ("tag", TAG_ENDING_PUPPET_FINAL_DEFEATED, "木偶终战击败（结算用）"),
    ("pattern", "puppet_intro_*", "弃线木偶三路线 intro"),
    ("pattern", "puppet_rift_*", "人格裂隙三路线"),
    ("pattern", "puppet_descent_*", "核心下潜三路线"),
    ("grudge", ELF_GRUDGE_INTRO_FAKE_GUARD, "飞贼：初见装守卫"),
    ("grudge", ELF_GRUDGE_HEIST_BETRAYED, "飞贼：盗案敲警铃"),
    ("choice", ENDING_STAGE_GATE_ORDER, "谢幕：秩序终门选择"),
    ("choice", ENDING_STAGE_GATE_FREEDOM, "谢幕：自由终门选择"),
    ("choice", ENDING_STAGE_GATE_POWER, "谢幕：力量终门选择"),
    ("tag", TAG_ENDING_STAGE_CURTAIN_SCHEDULED, "已排程谢幕事件"),
)


def iter_documented_choice_flags() -> Iterable[str]:
    """``FLAG_INDEX`` 中 type==choice 或 grudge 的本体（含 grudge 与 choice 同源）。"""
    for kind, value, _ in FLAG_INDEX:
        if kind in ("choice", "grudge"):
            yield value


_STATIC_FOR_TEST: Final[FrozenSet[str]] = frozen_choice_values(globals())
