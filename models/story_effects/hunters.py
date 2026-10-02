"""剧情后果 handler：复仇追猎、木偶侧追猎体、月蚀通缉中段战等「改写成怪物门」的效果。"""
import random

from models.door import DoorEnum


def handle_revenge_ambush(story, consequence, door):
    payload = consequence.payload
    stage = story._get_progress_stage()
    revenge_profile = story.REVENGE_HUNTER_PROFILES.get(consequence.consequence_id, {})
    force_hunter_config = payload.get("force_hunter", None)
    convert_to_hunter = payload.get("convert_to_hunter", True)
    hunter_name = payload.get("hunter_name") or revenge_profile.get("hunter_name")
    source_door_type = getattr(getattr(door, "enum", None), "name", "")
    monster = getattr(door, "monster", None)
    if force_hunter_config is None:
        # 复仇事件默认强制改写怪物门，避免出现“前情与来敌对不上”的割裂感。
        if source_door_type == "MONSTER" and monster is not None:
            force_hunter = bool(payload.get("force_replace_monster_door", True))
        else:
            force_hunter = bool(convert_to_hunter)
    else:
        force_hunter = bool(force_hunter_config)
    if force_hunter or (monster is None and convert_to_hunter):
        hunter = story._create_hunter_monster(preferred_name=hunter_name)
        hp_ratio = payload.get("hp_ratio", 1.25)
        atk_ratio = payload.get("atk_ratio", 1.2)
        if stage > 0:
            hp_ratio = min(2.4, hp_ratio * (1.0 + stage * 0.08))
            atk_ratio = min(2.2, atk_ratio * (1.0 + stage * 0.07))
        if monster:
            hunter.hp = max(hunter.hp, int(monster.hp * hp_ratio))
            hunter.atk = max(hunter.atk, int(monster.atk * atk_ratio))
        story.controller.add_message(
            story._resolve_message(
                payload,
                "message",
                revenge_profile.get("message", "门后等待你的不是原住怪物，而是一路追杀而来的猎手。"),
            )
        )
        hunter_hint = payload.get("hunter_hint") or revenge_profile.get("hunter_hint") or "脚步声不是偶然，那是追猎者在校准你的呼吸。"
        hunter.story_consequence_id = consequence.consequence_id
        # 由非怪物门引出的追猎战，只有击倒才算真正了结。
        hunter.story_consume_on_defeat = bool(
            payload.get("consume_on_defeat", source_door_type != "MONSTER")
        )
        hunter_door = DoorEnum.MONSTER.create_instance(
            controller=story.controller,
            monster=hunter,
            hint=hunter_hint,
        )
        story._log_effect_result(consequence, hunter.name)
        return True, hunter_door
    if monster:
        hp_ratio = payload.get("hp_ratio", 1.25)
        atk_ratio = payload.get("atk_ratio", 1.2)
        if stage > 0:
            hp_ratio = min(2.4, hp_ratio * (1.0 + stage * 0.08))
            atk_ratio = min(2.2, atk_ratio * (1.0 + stage * 0.07))
        old_hp, old_atk = monster.hp, monster.atk
        monster.hp = max(1, int(monster.hp * hp_ratio))
        monster.atk = max(1, int(monster.atk * atk_ratio))
        story.controller.add_message(
            story._append_effect_values(
                story._resolve_message(payload, "message", "旧怨者设下伏击，怪物获得强化。"),
                f"{monster.name} 生命 {old_hp}->{monster.hp}",
                f"攻击 {old_atk}->{monster.atk}",
            )
        )
        story._log_effect_result(
            consequence,
            f"{monster.name} 的气势暴涨，生命 {old_hp}->{monster.hp}，攻击 {old_atk}->{monster.atk}",
        )
        return True, door
    dmg = payload.get("damage", random.randint(5, 12))
    dmg = story._scale_amount(dmg, positive=False, aggressive=True)
    old_hp = story.controller.player.hp
    story.controller.player.take_damage(dmg)
    actual_loss = max(0, old_hp - story.controller.player.hp)
    story.controller.add_message(
        story._append_effect_values(
            story._resolve_message(payload, "message", f"你遭到报复，受到 {dmg} 点伤害。"),
            f"生命 {old_hp}->{story.controller.player.hp}",
            f"实际损失 {actual_loss}",
        )
    )
    story._log_effect_result(
        consequence,
        f"你在伏击里失去 {dmg} 点生命（{old_hp}->{story.controller.player.hp}）",
    )
    return True, door


def handle_puppet_side_minion(story, consequence, door):
    payload = consequence.payload
    story.controller.add_message(
        story._resolve_message(
            payload,
            "message",
            "金属摩擦声忽远忽近，门后有一只锈蚀的木偶在等你。",
        )
    )
    minion = story._create_puppet_minion_monster()
    minion.story_consequence_id = consequence.consequence_id
    minion.story_consume_on_defeat = True
    hint = (payload.get("hunter_hint") or payload.get("hint") or "").strip() or "金属摩擦声忽远忽近，像有一台小型追猎体在你周围绕圈校准。"
    minion_door = DoorEnum.MONSTER.create_instance(
        controller=story.controller,
        monster=minion,
        hint=hint,
    )
    story._log_effect_result(consequence, minion.name)
    return True, minion_door


def handle_moon_bounty_mid_battle(story, consequence, door):
    payload = consequence.payload
    mode = str(payload.get("battle_mode", "thief")).strip().lower()
    route = str(payload.get("route", "")).strip().lower()
    battle_profiles = {
        "thief": {
            "name": "命运乐谱大盗",
            "entry_messages": [
                "你撞见了被通缉的「命运乐谱大盗」。他先护住胸前那本旧册子，再举刀逼你后退。",
                "他嗓音发哑，却死死盯着你：「别往前了。我是这里的提词人，不是来跟你们拼命的——我只想把我女儿找回来。」",
                "「通缉令上写的那什么『命运乐章』，我连摸都没摸过。这册子里只有她小时候画的银羽毛，和一堆扑空的日期。」",
                "他把刀尖压低半寸，像在下最后通牒：「让条路。你们若非要把我当成贼……那就别怪不客气了。」",
            ],
            "hint": "门后站着的男人满手旧伤，耳尖压在旧帽檐下，怀里紧压着一本磨损的日记本。",
            "diary_source": "thief_body",
            "diary_note": (
                "命运乐谱大盗被你打昏在地。你在他身上只搜到一本普通日记本：每一页都在记录他失踪女儿的线索、"
                "一次次扑空的日期，页边画满了银色的羽毛。"
            ),
            "truth_hint": "案卷并没有因此更清楚，你只知道自己带走了一本父亲的日记，准备在月蚀审判上陈述。",
        },
        "guardian": {
            "name": "命运乐章守护者",
            "entry_messages": [
                "你刚把被通缉者推到身后，命运乐章守护者便持盾封住门口，宣称要当场清算。",
            ],
            "hint": "守护者的盔甲上刻着「证物优先」，它把你也列入了阻拦名单。",
            "diary_source": "thief_testimony",
            "diary_note": (
                "守护者倒下后，大盗喘着气告诉你：命运乐章不是他偷的，他只是剧场的提词人，在找失踪的女儿。"
                "他把随身日记本交给你：「如果你见到一个总把银羽别在头发上的姑娘……替我把它交给她。」"
            ),
            "truth_hint": "你翻开日记，只看到寻女记录、混乱的行程备注，和页边一根根银色羽毛的涂鸦；真正的失窃线索像被人刻意擦去。",
        },
    }
    if mode == "random":
        selected_key = random.choice(["thief", "guardian"])
    elif mode in battle_profiles:
        selected_key = mode
    else:
        selected_key = "thief"
    profile = battle_profiles[selected_key]
    hunter = story._create_hunter_monster(preferred_name=profile["name"])
    hunter.story_consequence_id = consequence.consequence_id
    hunter.story_consume_on_defeat = bool(payload.get("consume_on_defeat", True))
    hunter.story_moon_bounty_mid = True
    hunter.story_moon_bounty_route = route
    hunter.story_moon_bounty_diary_source = profile["diary_source"]
    hunter.story_moon_bounty_diary_note = profile["diary_note"]
    hunter.story_moon_bounty_truth_hint = profile["truth_hint"]
    hint = payload.get("hunter_hint") or profile["hint"]
    mid_battle_door = DoorEnum.MONSTER.create_instance(
        controller=story.controller,
        monster=hunter,
        hint=hint,
    )
    # 注意：payload["message"] 已在 _apply_chosen_consequence() 里作为触发提示输出；
    # 这里仅输出战斗入场文案，避免同一段“前情”重复两遍。
    for line in profile["entry_messages"]:
        if isinstance(line, str) and line.strip():
            story.controller.add_message(line.strip())
    story._log_effect_result(consequence, hunter.name)
    return True, mid_battle_door
