"""飞贼清算战台词：与 ``story_flags.ELF_GRUDGE_*`` / ``events/elf_chain`` 写入的 choice_flags 顺序一致。"""

from typing import Any, Dict, List, Tuple

from models.story_flags import (
    ELF_GRUDGE_BARK_KEYS,
    ELF_GRUDGE_CAMP_MERCENARY,
    ELF_GRUDGE_CAMP_REFUSED_HELP,
    ELF_GRUDGE_EPILOGUE_BURNED,
    ELF_GRUDGE_HEIST_BETRAYED,
    ELF_GRUDGE_HEIST_SIDE_ROUTE,
    ELF_GRUDGE_HUNTER_FLED,
    ELF_GRUDGE_HUNTER_LOOT_GRAB,
    ELF_GRUDGE_INTRO_FAKE_GUARD,
    ELF_GRUDGE_MAP_SOLD_OUT,
    ELF_GRUDGE_ROOFTOP_SNEAK,
    ELF_GRUDGE_SHADOW_THREATEN,
    ELF_GRUDGE_STAGE_REFUSED,
    ELF_GRUDGE_TRAP_ORDERED,
)

_ELF_GRUDGE_LINES: Dict[str, str] = {
    ELF_GRUDGE_HEIST_BETRAYED: "钟塔档案库你敲的那下警铃——我每夜都听得见。",
    ELF_GRUDGE_HUNTER_FLED: "猎门那儿你脚底抹油，留我一人喂弩箭，今天换你站中间。",
    ELF_GRUDGE_EPILOGUE_BURNED: "余响门里你把话说到那份上，就别指望我还能手软。",
    ELF_GRUDGE_ROOFTOP_SNEAK: "屋脊上你偷袭那一下，我可没忘。",
    ELF_GRUDGE_INTRO_FAKE_GUARD: "第一次见面就敢装守卫讹我？你当我是瞎子？",
    ELF_GRUDGE_MAP_SOLD_OUT: "把我的标注当货卖给商人——你赚得挺开心啊。",
    ELF_GRUDGE_HUNTER_LOOT_GRAB: "猎门里只顾抢击杀抢掉落，你眼里有过搭档两个字吗？",
    ELF_GRUDGE_SHADOW_THREATEN: "暗巷里你放冷话威胁我——账本是谁记得久，现在见分晓。",
    ELF_GRUDGE_TRAP_ORDERED: "陷阱回廊你命令我救人？你以为你是谁。",
    ELF_GRUDGE_CAMP_REFUSED_HELP: "夜营火旁你说单干——行啊，那就单干到底。",
    ELF_GRUDGE_CAMP_MERCENARY: "火堆边先伸手要钱再谈帮忙，你那份佣兵价我记着。",
    ELF_GRUDGE_STAGE_REFUSED: "怪物门前我喊你练两招，你嫌麻烦甩手就走。",
    ELF_GRUDGE_HEIST_SIDE_ROUTE: "盗案你非要改走侧井快线，毒针弩机可都是我替你扛的消息。",
}

ELF_RIVAL_GRUDGE_BARK_ORDER: List[Tuple[str, str]] = [
    (key, _ELF_GRUDGE_LINES[key]) for key in ELF_GRUDGE_BARK_KEYS
]


def collect_elf_rival_grudge_barks(story: Any) -> List[str]:
    flags = set(getattr(story, "choice_flags", set()) or [])
    out: List[str] = []
    for key, line in ELF_RIVAL_GRUDGE_BARK_ORDER:
        if key in flags:
            out.append(line)
    return out[:6]


def elf_rival_grudge_fillers(profile: str) -> List[str]:
    """无 elf_grudge_* 支线标记时仍播莱希娅清算台词，避免战斗里只剩身法/伤害句。"""
    shared = [
        "关系跌到这份上，还用我说我们怎么闹僵的吗？",
        "钥匙与余地你都没留，今天只剩刀锋能对话。",
        "你以为沉默就能把旧账一笔勾销？",
        "终局里每个选择都有价——你也该付一付了。",
        "我记着的不止一两扇门，是你一路怎么把我推到对立面。",
    ]
    if str(profile).strip().lower() == "vengeful":
        return shared + [
            "我不是来叙旧的；你欠我的，我用这一战讨。",
        ]
    return shared + [
        "账总得算清——你先到这儿，算你有种。",
    ]
