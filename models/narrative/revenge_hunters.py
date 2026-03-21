"""随机事件后果 flag → 复仇门怪物与门后文案（与 StorySystem 中 consequence 调度一致）。"""

from typing import Any, Dict

REVENGE_HUNTER_PROFILES: Dict[str, Dict[str, str]] = {
    "stranger_help_thief_revenge": {
        "hunter_name": "地痞打手",
        "hunter_hint": "门后传来铜钱碰撞声和刀鞘摩擦声，你救人时得罪的那群打手堵在前面。",
        "message": "你救人时挡了地痞财路，复仇打手追到了门后。",
    },
    "stranger_rob_bounty_revenge": {
        "hunter_name": "赏金猎人",
        "hunter_hint": "悬赏令钉在门框上，画像和你的脸只差一笔。",
        "message": "你抢劫陌生人的恶行被挂上悬赏，赏金猎人按图索骥堵住了你。",
    },
    "smuggler_report_gang_revenge": {
        "hunter_name": "走私团伙打手",
        "hunter_hint": "潮湿巷味和黑火药味从门缝钻出，走私团伙已经在里面守株待兔。",
        "message": "你举报走私犯后，团伙打手带着旧账追上了你。",
    },
    "shrine_pray_fanatic_hunt": {
        "hunter_name": "祭坛狂信徒",
        "hunter_hint": "门后烛火乱晃，披灰袍的人正举着祭器低声祷告。",
        "message": "你在祭坛祈祷被狂信徒曲解，他们把你当成异端堵截。",
    },
    "gambler_high_debtor_revenge": {
        "hunter_name": "讨债打手",
        "hunter_hint": "骰子在门后滚了一圈又停住，几个讨债人正掂着棍子等你。",
        "message": "赌局输家雇来的讨债打手终于追上了你。",
    },
    "lost_child_fame_backfire": {
        "hunter_name": "赏金猎犬",
        "hunter_hint": "门后有猎犬嗅闻的低吼声，它们循着你的名声和气味追来。",
        "message": "你的善名暴露了行踪，赏金猎犬先一步追到了门后。",
    },
    "chest_purify_cult_revenge": {
        "hunter_name": "诅咒教徒",
        "hunter_hint": "门后挂满倒置符咒，几个教徒正围着被你净化过的残片低语。",
        "message": "你净化诅咒宝箱后，崇拜它的教徒把你列为清算目标。",
    },
    "caravan_donate_bandit_envy": {
        "hunter_name": "劫道匪徒",
        "hunter_hint": "门后散着断裂车轮和箭羽，盯上车队的劫匪转而盯上了你。",
        "message": "你援助车队惹怒了劫匪，来复仇的正是那批劫道人。",
    },
    "caravan_extort_enforcer_test": {
        "hunter_name": "地下行会执行人",
        "hunter_hint": "门后有人把玩着行会印戒，显然是来“验货”的清算执行人。",
        "message": "你勒索车队后，地下行会派执行人来试你的深浅。",
    },
    "knight_aid_traitor_revenge": {
        "hunter_name": "骑士团叛徒",
        "hunter_hint": "门后盔甲擦过墙面的声音很熟悉——追杀骑士的叛徒已经到了。",
        "message": "你救下骑士后，他的死对头叛徒把你也列进了追杀名单。",
    },
}
