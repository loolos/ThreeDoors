"""飞贼清算战台词：与 events 中 _record_elf_grudge 写入的 choice_flags 一一对应，前者优先（更伤关系的举动先被提起）。"""

from typing import Any, List, Tuple

ELF_RIVAL_GRUDGE_BARK_ORDER: List[Tuple[str, str]] = [
    ("elf_grudge_heist_betrayed", "钟塔档案库你敲的那下警铃——我每夜都听得见。"),
    ("elf_grudge_hunter_fled", "猎门那儿你脚底抹油，留我一人喂弩箭，今天换你站中间。"),
    ("elf_grudge_epilogue_burned", "余响门里你把话说到那份上，就别指望我还能手软。"),
    ("elf_grudge_rooftop_sneak", "屋脊上你偷袭那一下，我可没忘。"),
    ("elf_grudge_intro_fake_guard", "第一次见面就敢装守卫讹我？你当我是瞎子？"),
    ("elf_grudge_map_sold_out", "把我的标注当货卖给商人——你赚得挺开心啊。"),
    ("elf_grudge_hunter_loot_grab", "猎门里只顾抢击杀抢掉落，你眼里有过搭档两个字吗？"),
    ("elf_grudge_shadow_threaten", "暗巷里你放冷话威胁我——账本是谁记得久，现在见分晓。"),
    ("elf_grudge_trap_ordered", "陷阱回廊你命令我救人？你以为你是谁。"),
    ("elf_grudge_camp_refused_help", "夜营火旁你说单干——行啊，那就单干到底。"),
    ("elf_grudge_camp_mercenary", "火堆边先伸手要钱再谈帮忙，你那份佣兵价我记着。"),
    ("elf_grudge_stage_refused", "怪物门前我喊你练两招，你嫌麻烦甩手就走。"),
    ("elf_grudge_heist_side_route", "盗案你非要改走侧井快线，毒针弩机可都是我替你扛的消息。"),
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
