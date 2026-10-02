"""剧情后果 handler：强制剧情事件、银羽秘藏、飞贼支线标记等「改写门内容」的效果。"""
import random

from models.door import DoorEnum
from models.game_config import GameConfig


def handle_force_story_event(story, consequence, door):
    payload = consequence.payload
    event_door = door
    if getattr(getattr(event_door, "enum", None), "name", "") != "EVENT":
        event_door = DoorEnum.EVENT.create_instance(controller=story.controller)
    event_key = payload.get("event_key")
    if not isinstance(event_key, str) or not event_key.strip():
        return False, door
    hint = payload.get("hint") or payload.get("message")
    story._attach_door_extension(
        door=event_door,
        extension_config={
            "extension_type": "force_story_event",
            "event_key": event_key.strip(),
            "hint": hint,
        },
        apply_on_attach=True,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(consequence, "")
    return True, event_door


def handle_stage_curtain_script_vault(story, consequence, door):
    payload = consequence.payload
    door_type = getattr(getattr(door, "enum", None), "name", "")
    if door_type != "REWARD":
        return False, door
    hint = payload.get("hint") or payload.get("message")
    story._attach_door_extension(
        door=door,
        extension_config={
            "extension_type": "stage_curtain_script_vault",
            "hint": hint,
        },
        apply_on_attach=True,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(consequence, "")
    return True, door


def handle_elf_side_reward_mark(story, consequence, door):
    payload = consequence.payload
    door_type = getattr(getattr(door, "enum", None), "name", "")
    if door_type != "REWARD":
        return False, door
    chance = payload.get("chance", 0.2)
    chance = max(0.0, min(1.0, float(chance)))
    if random.random() >= chance:
        return False, door
    story._attach_door_extension(
        door=door,
        extension_config={
            "extension_type": "elf_side_reward_mark",
            "hint": payload.get("hint") or payload.get("message"),
        },
        apply_on_attach=True,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(consequence, "")
    return True, door


def handle_elf_side_monster_mark(story, consequence, door):
    payload = consequence.payload
    door_type = getattr(getattr(door, "enum", None), "name", "")
    if door_type != "MONSTER":
        return False, door
    chance = payload.get("chance", 0.2)
    chance = max(0.0, min(1.0, float(chance)))
    if random.random() >= chance:
        return False, door
    # 精灵飞贼需要帮助才说得通：按当前 tier 选一只较强的怪物替换门内怪
    from models.monster import Monster, _get_round_limited_max_tier
    current_round = getattr(story.controller, "round_count", 0) or 0
    unlocked = getattr(story.controller, "unlocked_monster_tier", 1) or 1
    round_cap = _get_round_limited_max_tier(current_round)
    strong_tier = max(2, min(round_cap, unlocked, GameConfig.MONSTER_MAX_TIER))
    strong_monster = Monster(tier=strong_tier)
    door.monster = strong_monster
    hint = payload.get("hint") or payload.get("message")
    hint_text = hint.strip() if isinstance(hint, str) and hint.strip() else ""
    story._attach_door_extension(
        door=door,
        extension_config={
            "extension_type": "elf_side_monster_mark",
            "hint": hint_text,
        },
        apply_on_attach=True,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(consequence, "")
    return True, door


def handle_replace_with_elf_side_event(story, consequence, door):
    payload = consequence.payload
    door_type = getattr(getattr(door, "enum", None), "name", "")
    if door_type != "SHOP":
        return False, door
    chance = payload.get("chance", 0.2)
    chance = max(0.0, min(1.0, float(chance)))
    if random.random() >= chance:
        return False, door
    event_key = payload.get("event_key")
    if not isinstance(event_key, str) or not event_key.strip():
        return False, door
    story._attach_door_extension(
        door=door,
        extension_config={
            "extension_type": "force_story_event",
            "event_key": event_key.strip(),
            "hint": payload.get("hint", "墙上的银色箭羽指向下一次相遇。"),
        },
        apply_on_attach=True,
    )
    # 文案已在门出现时通过 _build_trigger_message 展示，此处不再重复
    story._log_effect_result(consequence, "")
    return True, door
