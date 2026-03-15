# ending_roll.py
"""结局滚动画面文案生成：玩家状态、长事件选择摘要、结局综述。"""

# 长事件选择 flag -> 结局摘要中的一句剧情描述（用于“根据玩家在各长事件中的选择”部分）
CHOICE_NARRATIVE = {
    "stranger_helped": "你曾对受伤的陌生人伸出援手。",
    "stranger_robbed": "你曾在他人危难时选择搜刮。",
    "stranger_ignored": "你曾对陌生人的呼救置之不理。",
    "smuggler_bought_goods": "你与走私者做过交易。",
    "smuggler_reported": "你向秩序举报了走私者。",
    "smuggler_left": "你选择离开，未与走私者纠缠。",
    "shrine_prayed": "你在古老祭坛前祈祷。",
    "shrine_desecrated": "你亵渎了祭坛。",
    "shrine_inspected": "你仅止于查看祭坛。",
    "gambler_high_stakes": "你在赌局中押下高注。",
    "gambler_low_stakes": "你以低注参与了赌局。",
    "gambler_declined": "你拒绝了赌徒的邀请。",
    "lost_child_guided_home": "你曾将迷路的孩子送回家。",
    "lost_child_gave_gold": "你给了迷路的孩子一些金币。",
    "lost_child_ignored": "你未曾理会迷路的孩子。",
    "cursed_chest_opened": "你打开了诅咒宝箱。",
    "cursed_chest_purified": "你净化了诅咒宝箱。",
    "cursed_chest_left": "你选择离开诅咒宝箱。",
    "sage_power_choice": "智者问起时，你答为了力量。",
    "sage_wealth_choice": "智者问起时，你答为了财富。",
    "sage_health_choice": "智者问起时，你答为了生存。",
    "caravan_donated": "你曾向逃难队伍捐赠。",
    "caravan_extorted": "你曾向逃难队伍勒索。",
    "caravan_ignored": "你未曾理会逃难队伍。",
    "ending_hook:elf_alliance": "你与银羽飞贼最终结为同盟。",
    "ending_hook:elf_neutral": "你与银羽飞贼保持着若即若离的关系。",
    "ending_hook:elf_hostile": "你与银羽飞贼势同水火。",
    "ending_elf_rival_final_victory": "在终局前你击败了飞贼，她认输离去。",
    "ending_elf_rival_parted": "在终局前你与飞贼错身而过，各自走向终点。",
    "curtain_call_script_recovered": "你从飞贼手中取回了终幕剧本。",
    "ending:puppet_final_defeated": "你击败了木偶的最终形态。",
    "ending_default_normal_completed": "你击倒了选择困难症候群，从迷宫出口离开。",
    "ending_stage_gate_order": "你选择了补全谢幕，与善良人格一同完成终演。",
    "ending_stage_gate_freedom": "你选择了即兴谢幕，以证词与自由完成终演。",
    "ending_stage_gate_default": "你选择了直面选择困难症候群。",
    "ending_power_curtain_choice_route": "你以规则或意志接管了终幕。",
}

# 门类型中文名（用于“每个门经历了多少次”）
DOOR_NAMES = {
    "trap": "陷阱门",
    "reward": "奖励门",
    "monster": "怪物门",
    "shop": "商店门",
    "event": "事件门",
}

# 四种结局的综述文案（最后一段）
ENDING_SUMMARY = {
    "default_normal": (
        "你在这座没有出口的迷宫中，最终选择了直面「选择困难症候群」。"
        "击倒它之后，你终于找到了离开的出口。"
        "走廊深处的弦音与低语渐渐远去，这场冒险在此画上句点。"
    ),
    "stage_curtain_order": (
        "你按证词与秩序补齐了终幕结构，与木偶的善良人格一同完成谢幕。"
        "舞台的灯光暗下时，你与这段旅程中的选择一起被写进了结局。"
    ),
    "stage_curtain_freedom": (
        "你承认剧本无法完整复刻，带着众人的证词即兴完成了终演。"
        "即兴与自由，成为你这趟迷宫之旅的终章。"
    ),
    "stage_curtain_power": (
        "你以导演代理人身份接管了门廊规则，强行完成谢幕。"
        "力量与掌控，为这场冒险写下了句号。"
    ),
    "impromptu_curtain_call": (
        "你在无剧本的终局里即兴谢幕，把抉择当作台词，或向虚空鞠躬。"
        "即兴与自由，成为你这趟迷宫之旅的终章。"
    ),
}


def build_ending_roll_lines(controller) -> list:
    """
    根据当前控制器状态生成结局滚动画面的文案列表。
    顺序：玩家状态摘要 → 长事件选择摘要 → 结局综述 → 感谢游玩。
    """
    lines = []
    p = getattr(controller, "player", None)
    story = getattr(controller, "story", None)
    clear_info = getattr(controller, "game_clear_info", None) or {}
    door_counts = getattr(controller, "door_visit_counts", None) or {}
    monsters_defeated = getattr(controller, "monsters_defeated", 0)

    # ---------- 1. 玩家状态摘要 ----------
    lines.append("—— 终局之时 ——")
    lines.append("")
    if p is not None:
        lines.append(f"生命值：{p.hp}")
        lines.append(f"攻击力：{p.atk}")
        lines.append(f"金币：{p.gold}")
        moral = getattr(story, "moral_score", 0) if story else 0
        lines.append(f"道德值：{moral}")
    round_count = getattr(controller, "round_count", 0)
    lines.append(f"总回合数：{round_count}")
    lines.append(f"击败怪物数：{monsters_defeated}")
    lines.append("")
    if door_counts:
        lines.append("各门经历次数：")
        for key, name in DOOR_NAMES.items():
            count = door_counts.get(key, 0)
            lines.append(f"  {name}：{count} 次")
    lines.append("")
    lines.append("—— 旅途中的选择 ——")
    lines.append("")

    # ---------- 2. 长事件选择摘要 ----------
    choice_flags = set()
    if story is not None:
        choice_flags = getattr(story, "choice_flags", set()) or set()
        choice_flags |= getattr(story, "story_tags", set()) or set()
    for flag, narrative in CHOICE_NARRATIVE.items():
        if flag in choice_flags:
            lines.append(narrative)
    if not any(flag in choice_flags for flag in CHOICE_NARRATIVE):
        lines.append("你在迷宫中留下了无数细小的抉择，它们共同构成了这条终点。")
    lines.append("")
    lines.append("—— 结局 ——")
    lines.append("")

    # ---------- 3. 结局综述 ----------
    ending_key = str(clear_info.get("ending_key", "unknown")).strip()
    summary = ENDING_SUMMARY.get(ending_key)
    if summary:
        lines.append(summary)
    else:
        desc = str(clear_info.get("ending_description", "")).strip()
        if desc:
            lines.append(desc)
        else:
            lines.append("你的冒险在此告一段落。")
    lines.append("")
    lines.append("感谢游玩。")

    return lines
