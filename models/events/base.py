"""剧情事件基类与 EventChoice。"""

class EventChoice:
    """单个事件选项：展示文案与选中时的回调。"""

    def __init__(self, text, callback):
        self.text = text
        self.callback = callback


class Event:
    """剧情事件基类：标题、描述、选项及触发条件（回合、概率等）。"""
    TRIGGER_BASE_PROBABILITY = 0.1
    MIN_TRIGGER_ROUND = 0
    MAX_TRIGGER_ROUND = None
    POSITIVE_STAGE_SCALE = (1.0, 1.12, 1.27, 1.45)
    NEGATIVE_STAGE_SCALE = (1.0, 1.1, 1.22, 1.35)
    ONLY_TRIGGER_ONCE = False

    def __init__(self, controller):
        self.controller = controller
        self.title = "Event"
        self.description = "Something happens."
        self.choices = []

    def get_choices(self):
        return [c.text for c in self.choices]

    def resolve_choice(self, index):
        if 0 <= index < len(self.choices):
            return self.choices[index].callback()
        return "Invalid choice."

    def add_message(self, msg):
        self.controller.add_message(msg)
    
    def get_player(self):
        return self.controller.player

    def register_story_choice(self, choice_flag, moral_delta=0, consequences=None):
        story = getattr(self.controller, "story", None)
        if not story:
            return
        story.register_choice(
            choice_flag=choice_flag,
            moral_delta=moral_delta,
            consequences=consequences or [],
        )

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(
            controller,
            min_round=getattr(cls, "MIN_TRIGGER_ROUND", 0),
        ) and cls._is_within_round_window(controller)

    @classmethod
    def _is_within_round_window(cls, controller):
        max_round = getattr(cls, "MAX_TRIGGER_ROUND", None)
        if max_round is None:
            return True
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        return round_count <= max_round

    @classmethod
    def get_trigger_probability(cls, controller):
        return cls.TRIGGER_BASE_PROBABILITY

    @classmethod
    def get_progress_stage(cls, controller):
        """按回合和基础攻击力估算当前事件强度阶段。"""
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        player = getattr(controller, "player", None)
        base_atk = 5
        if player is not None:
            base_atk = max(1, int(getattr(player, "_atk", getattr(player, "atk", 5))))
        score = round_count * 2 + base_atk * 4
        if score >= 130:
            return 3
        if score >= 90:
            return 2
        if score >= 55:
            return 1
        return 0

    @classmethod
    def is_unlocked(cls, controller, min_round=0, min_stage=0):
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        return round_count >= min_round and cls.get_progress_stage(controller) >= min_stage

    def scale_value(self, base_value, positive=True, aggressive=False, minimum=1):
        """按玩家阶段缩放事件数值。"""
        stage = self.get_progress_stage(self.controller)
        scales = self.POSITIVE_STAGE_SCALE if positive else self.NEGATIVE_STAGE_SCALE
        scale = scales[min(stage, len(scales) - 1)]
        if aggressive and stage > 0:
            scale += stage * 0.04
        scaled = int(round(base_value * scale))
        if base_value >= 0:
            return max(minimum, scaled)
        return min(-minimum, scaled)

