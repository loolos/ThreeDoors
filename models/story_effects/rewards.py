"""剧情后果 handler：奖励、祝福、诅咒、扣钱、宝物门改写等资源类效果。"""
import random

from models.status import StatusName


def handle_villagers_gift(story, consequence, door):
    payload = consequence.payload
    reward_door = story._make_reward_door(
        gold=payload.get("gold", random.randint(50, 100)),
        include_item=payload.get("include_item", True),
        hint=payload.get("hint", "旧事回响"),
    )
    reward_desc = story._describe_reward(reward_door)
    story.controller.add_message(
        story._append_effect_values(
            story._resolve_message(
                payload,
                "message",
                "你过往的行为被人记住了，对方直接把宝物交给了你。",
            ),
            f"获得 {reward_desc}",
        )
    )
    story._log_effect_result(consequence, f"谢礼是 {reward_desc}")
    return True, reward_door


def handle_guard_reward(story, consequence, door):
    payload = consequence.payload
    gold = payload.get("gold", random.randint(20, 60))
    heal = payload.get("heal", 0)
    gold = story._scale_amount(gold, positive=True, aggressive=True)
    if heal > 0:
        heal = story._scale_amount(heal, positive=True)
    old_gold, old_hp = story.controller.player.gold, story.controller.player.hp
    story.controller.player.gold += gold
    healed = 0
    if heal > 0:
        healed = story.controller.player.heal(heal)
    message = story._resolve_message(payload, "message", f"守卫感谢你的协助，奖励了你 {gold} 金币。")
    if isinstance(message, str):
        try:
            message = message.format(gold=gold, heal=heal, healed=healed)
        except (KeyError, IndexError, ValueError):
            pass
    story.controller.add_message(
        story._append_effect_values(
            message,
            f"金币 {old_gold}->{story.controller.player.gold}",
            f"生命 {old_hp}->{story.controller.player.hp}",
        )
    )
    story._log_effect_result(
        consequence,
        f"你的状态发生变化：金币 {old_gold}->{story.controller.player.gold}，生命 {old_hp}->{story.controller.player.hp}",
    )
    return True, door


def handle_shrine_blessing(story, consequence, door):
    payload = consequence.payload
    if getattr(getattr(door, "enum", None), "name", "") == "TRAP":
        reward_door = story._make_reward_door(gold=random.randint(25, 65), include_item=False, hint="神佑余辉")
        story.controller.add_message(
            story._append_effect_values(
                story._resolve_message(payload, "message", "圣坛余辉保护了你，陷阱化作馈赠。"),
                f"获得 {story._describe_reward(reward_door)}",
            )
        )
        story._attach_door_extension(
            door=door,
            extension_config={
                "extension_type": "trap_rewrite_to_reward",
                "reward": dict(getattr(reward_door, "reward", {})),
                "hint": getattr(reward_door, "hint", "神佑余辉"),
            },
            apply_on_attach=False,
        )
        story._log_effect_result(
            consequence,
            f"险境被改写成馈赠：{story._describe_reward(reward_door)}",
        )
        return True, door
    monster = getattr(door, "monster", None)
    if monster:
        old_atk = monster.atk
        monster.atk = max(1, int(monster.atk * 0.82))
        story.controller.add_message(
            story._append_effect_values(
                story._resolve_message(payload, "message", "你受到神佑，敌人的攻势被压制。"),
                f"{monster.name} 攻击 {old_atk}->{monster.atk}",
            )
        )
        story._log_effect_result(
            consequence,
            f"{monster.name} 的攻击被压制（{old_atk}->{monster.atk}）",
        )
        return True, door
    return False, door


def handle_shrine_curse(story, consequence, door):
    payload = consequence.payload
    duration = payload.get("duration", 2)
    if story._get_progress_stage() >= 2:
        duration += 1
    story.controller.player.apply_status(
        StatusName.WEAK.create_instance(duration=duration, target=story.controller.player)
    )
    story.controller.add_message(
        story._append_effect_values(
            story._resolve_message(payload, "message", f"诅咒追上了你，陷入虚弱 {duration} 回合。"),
            f"虚弱持续 {duration} 回合",
        )
    )
    story._log_effect_result(consequence, f"你陷入虚弱，持续 {duration} 回合")
    return True, door


def handle_atk_training(story, consequence, door):
    payload = consequence.payload
    delta = payload.get("delta", 2)
    if story._get_progress_stage() >= 2:
        delta += 1
    old_atk = story.controller.player._atk
    story.controller.player.change_base_atk(delta)
    story.controller.add_message(
        story._append_effect_values(
            story._resolve_message(payload, "message", "这段经历让你学会了更狠的出手方式。"),
            f"基础攻击 {old_atk}->{story.controller.player._atk}",
            f"本次提升 {delta}",
        )
    )
    story._log_effect_result(
        consequence,
        f"你的基础攻击提升了（{old_atk}->{story.controller.player._atk}）",
    )
    return True, door


def handle_lose_gold(story, consequence, door):
    payload = consequence.payload
    old_gold = story.controller.player.gold
    lost = min(story.controller.player.gold, payload.get("amount", random.randint(15, 45)))
    lost = min(story.controller.player.gold, story._scale_amount(lost, positive=False))
    story.controller.player.gold -= lost
    story.controller.add_message(
        story._append_effect_values(
            story._resolve_message(payload, "message", f"旧账找上门来，你被迫赔了 {lost} 金币。"),
            f"金币 {old_gold}->{story.controller.player.gold}",
            f"本次损失 {lost}",
        )
    )
    story._log_effect_result(
        consequence,
        f"你付出了代价，金币 {old_gold}->{story.controller.player.gold}",
    )
    return True, door


def handle_treasure_marked_item(story, consequence, door):
    payload = consequence.payload
    if getattr(getattr(door, "enum", None), "name", "") != "REWARD":
        return False, door
    current_reward = getattr(door, "reward", {})
    if not isinstance(current_reward, dict):
        current_reward = {}
    new_reward, marked_item = story._build_marked_reward(current_reward=current_reward, payload=payload)
    story._attach_door_extension(
        door=door,
        extension_config={
            "extension_type": "treasure_marked_item",
            "resolved_reward": new_reward,
        },
        apply_on_attach=True,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(
        consequence,
        f"宝物内容被改写：{story._describe_reward(door)}",
    )
    return True, door


def handle_treasure_vanish(story, consequence, door):
    payload = consequence.payload
    if getattr(getattr(door, "enum", None), "name", "") != "REWARD":
        return False, door
    fake_gold = max(0, int(payload.get("fake_gold", 0)))
    story._attach_door_extension(
        door=door,
        extension_config={
            "extension_type": "treasure_vanish",
            "resolved_reward": {"gold": fake_gold} if fake_gold > 0 else {},
        },
        apply_on_attach=True,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(
        consequence,
        "宝物已被掏空",
    )
    return True, door


def handle_treasure_deposit_backpack(story, consequence, door):
    payload = consequence.payload
    if getattr(getattr(door, "enum", None), "name", "") != "REWARD":
        return False, door
    story._attach_door_extension(
        door=door,
        extension_config={
            "extension_type": "treasure_deposit_backpack",
            "resolved_reward": story._build_deposit_backpack_reward(payload),
        },
        apply_on_attach=True,
    )
    story._log_effect_result(
        consequence,
        f"宝物内容被改写：{story._describe_reward(door)}",
    )
    return True, door
