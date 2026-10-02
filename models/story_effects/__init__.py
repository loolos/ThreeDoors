"""内置剧情后果（PendingConsequence.effect_key）的 handler 注册表。

每个 handler 签名为 handler(story, consequence, door) -> (applied: bool, door)，
由 StorySystem._apply_effect 分发。新增效果：在对应主题模块写 handle_<effect_key>，
再登记到下面的 EFFECT_HANDLERS。运行时也可用 StorySystem.register_effect_handler 覆盖。
"""
from typing import Any, Callable, Dict, Tuple

from models.story_effects import bosses, hunters, rewards, shop, story_doors

EffectHandler = Callable[[Any, Any, Any], Tuple[bool, Any]]


def _collect(*modules) -> Dict[str, EffectHandler]:
    handlers: Dict[str, EffectHandler] = {}
    for module in modules:
        for name in dir(module):
            if not name.startswith("handle_"):
                continue
            effect_key = name[len("handle_"):]
            if effect_key in handlers:
                raise RuntimeError(f"重复的剧情后果 handler: {effect_key}")
            handlers[effect_key] = getattr(module, name)
    return handlers


EFFECT_HANDLERS: Dict[str, EffectHandler] = _collect(rewards, shop, hunters, story_doors, bosses)
