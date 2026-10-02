"""剧情后果 handler：黑市折扣 / 加价（作用于下一次商店刷新）。"""


def handle_black_market_discount(story, consequence, door):
    payload = consequence.payload
    if getattr(getattr(door, "enum", None), "name", "") != "SHOP":
        return False, door
    try:
        ratio = float(payload.get("ratio", 0.7))
    except (TypeError, ValueError):
        ratio = 0.7
    shop_targets = story._get_shop_targets(door)
    if not shop_targets:
        return False, door
    story._queue_shop_ratio(shop_targets, ratio)
    story._apply_shop_ratio(shop_targets, ratio)
    ratio_text = f"当前商品按约 {max(1, int(ratio * 100))}% 结算"
    story.controller.add_message(
        story._append_effect_values(
            story._resolve_message(
                payload,
                "message",
                f"商人认出你是熟客同路人，{ratio_text}。",
            ),
            ratio_text,
        )
    )
    story._log_effect_result(consequence, ratio_text)
    return True, door


def handle_black_market_markup(story, consequence, door):
    payload = consequence.payload
    if getattr(getattr(door, "enum", None), "name", "") != "SHOP":
        return False, door
    try:
        ratio = float(payload.get("ratio", 1.4))
    except (TypeError, ValueError):
        ratio = 1.4
    shop_targets = story._get_shop_targets(door)
    if not shop_targets:
        return False, door
    story._queue_shop_ratio(shop_targets, ratio)
    story._apply_shop_ratio(shop_targets, ratio)
    ratio_text = f"当前商品按约 {max(1, int(ratio * 100))}% 上浮"
    story.controller.add_message(
        story._append_effect_values(
            story._resolve_message(
                payload,
                "message",
                f"商人认出你惹过他们的人，{ratio_text}。",
            ),
            ratio_text,
        )
    )
    story._log_effect_result(consequence, ratio_text)
    return True, door
