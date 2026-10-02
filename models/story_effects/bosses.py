"""剧情后果 handler：终局与长线 Boss 门（飞贼清算、木偶回声、选择困难症候群、黑暗木偶）。"""
from models.door import DoorEnum
from models.narrative import story_system_lines as narrative_lines
from models.narrative.elf_rival_grudge import (
    collect_elf_rival_grudge_barks,
    elf_rival_grudge_fillers,
)


def handle_elf_rival_final_gate(story, consequence, door):
    payload = consequence.payload
    from models.monster import Monster, estimate_player_power, _apply_player_match_scaling

    door_type = getattr(getattr(door, "enum", None), "name", "")
    door_is_monster = door_type == "MONSTER"
    player = getattr(story.controller, "player", None)
    relation = int(payload.get("relation", story.elf_relation))
    style = str(payload.get("style", "trickster")).strip().lower()
    extensions = payload.get("extensions", [])
    if not isinstance(extensions, list):
        extensions = []

    # 清算战基础血量 600；再乘关系/深怨系数，40 回合后另叠玩家强度缩放（见 _apply_player_match_scaling）
    base_hp = 600
    base_atk = 44
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
    round_count = max(0, int(getattr(story.controller, "round_count", 0)))
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
                "shadowstep": "她踩墙折返，连斩逼得你后撤。",
                "debuff": "她借假动作压低你的重心，你的出手明显发软。",
            },
            "attack_banter": [
                "她刃口一沉，没有废话，只有距离在缩短。",
                "斗篷扬起残影，下一击已经贴到你鼻息前。",
                "她把旧账折进这一刀里，出手干脆利落。",
                "你格挡的瞬间，她已换步到你侧后。",
            ],
        }
    else:
        dialogue = "你听到黑暗中有声音传来：'你总算走到这里了，先把我们之间的账清掉。'"
        hint = "她抬手拭血，冷笑道：'终局门里真正致命的不是怪物，是你以为自己已经选对。'说罢便退进了黑暗中。"
        state = {
            "profile": "trickster",
            "extensions": extensions,
            "shadowstep_boost": [0.24],
            "debuff_turns": [2],
            "debuff_mode": "poison" if "ending_hook_hunted" in extensions else "weak",
            "lines": {
                "shadowstep": "她借你的攻击空档贴身反刺。",
                "debuff": "她扬起一把细碎粉末，呼吸与挥刀都被干扰。",
            },
            "attack_banter": [
                "她像在说笑，手可一点没慢。",
                "残影掠过门槛，她的刃口又指向你咽喉。",
                "你刚稳住重心，她已经绕到你视线的死角。",
                "这一下不带解说——账都在刀锋上。",
            ],
        }

    state["grudge_barks"] = collect_elf_rival_grudge_barks(story)
    state["grudge_bark_fillers"] = elf_rival_grudge_fillers(state.get("profile", "trickster"))

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
            controller=story.controller,
            monster=rival,
            battle_extensions=[extension_cfg],
        )

    hint_text = payload.get("hint") or payload.get("message") or "银羽残痕在门槛上交错，像是一封迟到的决斗书。"
    if isinstance(hint_text, str) and hint_text.strip():
        target_door.hint = hint_text.strip()
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story.controller.add_message(dialogue)
    story._log_effect_result(consequence, f"{rival.name}拦路（关系 {relation}），生命 {rival.hp}，攻击 {rival.atk}")
    return True, target_door


def handle_puppet_echo_final_gate(story, consequence, door):
    payload = consequence.payload
    from models.monster import Monster

    door_type = getattr(getattr(door, "enum", None), "name", "")
    door_is_monster = door_type == "MONSTER"
    player = getattr(story.controller, "player", None)
    player_atk = max(1, int(getattr(player, "atk", 10)))
    # 血量至少为玩家攻击力的 5 倍；攻击力为玩家攻击力的一半，最高不超过 50
    base_hp = max(5 * player_atk, int(payload.get("base_hp", 5 * player_atk)))
    base_atk = min(50, max(1, player_atk // 2))
    boss_name = str(payload.get("boss_name", "木偶的回声")).strip() or "木偶的回声"
    echo_monster = Monster(
        name=boss_name,
        hp=base_hp,
        atk=base_atk,
        tier=max(3, int(payload.get("tier", 4))),
        effect_probability=0.0,
    )
    evil = story.get_puppet_evil_value()
    high_evil = evil > story.PUPPET_HIGH_EVIL_FOR_POWER_DIRECT
    echo_lines = story._build_puppet_echo_lines(high_evil=high_evil)
    if not echo_lines:
        echo_lines = ["回声在走廊里重复着你曾走过的路。"] if not high_evil else ["「呵……你做过的事，我可都记得。」"]
    extension_cfg = {
        "extension_type": "puppet_echo_final",
        "monster_ref": echo_monster,
        "state": {"echo_lines": echo_lines, "echo_index": 0, "high_evil": high_evil},
    }
    setattr(echo_monster, "story_puppet_echo_final_boss", True)
    setattr(echo_monster, "story_consequence_id", consequence.consequence_id)
    setattr(echo_monster, "story_consume_on_defeat", True)
    if door_is_monster:
        if hasattr(door, "add_battle_extension"):
            door.add_battle_extension(extension_cfg)
        else:
            door.battle_extensions = [extension_cfg]
        door.monster = echo_monster
        target_door = door
    else:
        target_door = DoorEnum.MONSTER.create_instance(
            controller=story.controller,
            monster=echo_monster,
            battle_extensions=[extension_cfg],
        )
    hint_text = payload.get("hint") or payload.get("message") or "门后传来你一路抉择的回响。"
    if isinstance(hint_text, str) and hint_text.strip():
        target_door.hint = hint_text.strip()
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(consequence, f"{echo_monster.name}（生命 {echo_monster.hp}，攻击 {echo_monster.atk}）")
    return True, target_door


def handle_default_final_boss(story, consequence, door):
    payload = consequence.payload
    from models.monster import Monster, estimate_player_power, _apply_player_match_scaling

    player = getattr(story.controller, "player", None)
    stage = story._get_progress_stage()
    base_hp = max(200, int(payload.get("base_hp", 870 + stage * 26)))
    base_atk = max(30, int(payload.get("base_atk", 24 + stage * 4)))
    boss_name = str(payload.get("boss_name", "选择困难症候群")).strip() or "选择困难症候群"
    boss = Monster(
        name=boss_name,
        hp=base_hp,
        atk=base_atk,
        tier=max(3, int(payload.get("tier", 4))),
    )
    round_count = max(0, int(getattr(story.controller, "round_count", 0)))
    power_score = estimate_player_power(player=player, current_round=round_count)
    _apply_player_match_scaling(
        monster=boss,
        player=player,
        current_round=round_count,
        power_score=power_score,
    )
    setattr(boss, "story_default_final_boss", True)
    hint = payload.get("hint") or payload.get("message") or "门后响起一阵咂舌声：'两百回合了，你还在犹豫？'"
    raw_attack = payload.get("attack_taunts", payload.get("taunts", []))
    attack_taunts = [
        t.strip()
        for t in (raw_attack if isinstance(raw_attack, list) else [])
        if isinstance(t, str) and t.strip()
    ]
    if attack_taunts:
        setattr(boss, "story_default_final_boss_attack_taunts", list(attack_taunts))
    final_door = DoorEnum.MONSTER.create_instance(
        controller=story.controller,
        monster=boss,
        hint=hint,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示；嘲讽在 Monster.attack 中随每次出手播出
    story._log_effect_result(consequence, boss.name)
    return True, final_door


def handle_puppet_dark_boss(story, consequence, door):
    payload = consequence.payload
    door_is_monster = getattr(getattr(door, "enum", None), "name", "") == "MONSTER"
    from models.monster import Monster, _apply_player_match_scaling, estimate_player_power

    base_hp = max(80, int(payload.get("base_hp", 220)))
    base_atk = max(10, int(payload.get("base_atk", 34)))
    boss_name = payload.get("boss_name", "堕暗机偶·弃线者")
    phase2_name = payload.get("phase2_name", "堕暗机偶·黑暗完全体")
    story_flags = story.choice_flags.union(story.story_tags)
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
    if story.puppet_evil_value is None:
        # 木偶线从未写入邪恶值：按玩家在各节点的善/暗选项推算
        evil_value = story.DEFAULT_PUPPET_EVIL_VALUE + dark_score * 8 - kind_score * 8
    else:
        evil_value = story.get_puppet_evil_value()
    if "evil_value" in payload:
        try:
            evil_value = int(payload.get("evil_value"))
        except (TypeError, ValueError):
            pass
    evil_value += (dark_score - kind_score) * 2
    evil_value = max(0, min(100, evil_value))
    side_hit_count = len([tag for tag in story.story_tags if str(tag).startswith("consumed:puppet_side_")])
    player = getattr(story.controller, "player", None)

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
    round_count = max(0, int(getattr(story.controller, "round_count", 0)))
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
        story.story_tags.add("ending:puppet_rematch_gate_done")
    story.controller.add_message(narrative_lines.MSG_PUPPET_REMATCH_ALARM)
    if side_hit_count <= 0:
        story.controller.add_message(
            story._resolve_message(
                payload,
                "no_side_event_message",
                "你几乎没在中途触发那些支线干预，它的最终参数按核心读数直接结算，战斗走势更加不可预测。",
            )
        )
    if awakened_kind:
        heal = min(100 - story.controller.player.hp, max(4, int(payload.get("kind_heal", 12))))
        if heal > 0:
            story.controller.player.heal(heal)
        story.controller.add_message(
            story._resolve_message(
                payload,
                "kind_awaken_message",
                f"病毒噪声里忽然响起温柔童谣，{kind_name}短暂夺回控制，悄悄替你挡下一轮杀意。",
            )
        )
    elif dark_overload:
        story.controller.add_message(
            story._resolve_message(
                payload,
                "dark_overload_message",
                f"你先前的选择不断喂养黑暗协议，{dark_name}完全接管了机偶核心。",
            )
        )
    else:
        story.controller.add_message(
            story._resolve_message(
                payload,
                "neutral_message",
                f"{kind_name}与{dark_name}仍在互相撕扯，黑暗协议暂时占了上风。",
            )
        )

    puppet_state = story._build_puppet_battle_state(
        payload=payload,
        story_flags=story_flags,
        kind_name=kind_name,
        dark_name=dark_name,
        phase2_name=phase2_name,
    )
    story._apply_puppet_entry_modifiers(monster=boss, state=puppet_state, phase=1)
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
            controller=story.controller,
            monster=boss,
            battle_extensions=[extension_cfg],
        )
    hint = payload.get("hunter_hint") or payload.get("hint") or payload.get("message")
    if isinstance(hint, str) and hint.strip():
        target_door.hint = hint.strip()
    if evil_value <= 25:
        core_hint = "核心读数偏稳，蓝光尚存"
    elif evil_value <= 45:
        core_hint = "核心暗噪被压至低语"
    elif evil_value <= 65:
        core_hint = "核心在红蓝之间剧烈摆动"
    elif evil_value <= 85:
        core_hint = "核心深处暗侧占优"
    else:
        core_hint = "核心暴走，黑暗协议主导"
    story._log_effect_result(
        consequence,
        f"{boss.name} 降临（{core_hint}），生命 {boss.hp}，攻击 {boss.atk}",
    )
    return True, target_door
