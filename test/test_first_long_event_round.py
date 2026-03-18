"""
统计「精灵飞贼」「黑暗木偶」两条长线起始事件，从游戏开局第一次被事件门随机到时的平均回合数。
每次试验：从 round 0 起逐回合模拟「本回合玩家选了事件门」，调用 get_random_event，
记录首次出现对应事件类的回合；多轮试验取平均。

长线起始在 models.events.LONG_EVENT_STARTER_EARLIEST_ROUND 之前不会进入随机池。
"""
import unittest

from server import GameController
from test.test_base import BaseTest
from models.events import (
    LONG_EVENT_STARTER_EARLIEST_ROUND,
    get_random_event,
    ElfThiefIntroEvent,
    PuppetAbandonmentEvent,
)


# 每条约 300 次试验，单次试验最多模拟到该回合（未触发则记为该值，用于平均上界）
NUM_TRIALS = 300
MAX_ROUNDS_PER_TRIAL = 80


def _first_trigger_rounds(controller_factory, event_class, num_trials, max_rounds):
    """返回 (触发回合列表, 未触发次数)。每次试验重置 controller，逐回合 get_random_event 直到命中或到 max_rounds。"""
    trigger_rounds = []
    no_trigger_count = 0
    event_name = event_class.__name__

    for _ in range(num_trials):
        controller = controller_factory()
        controller.reset_game()
        first_round = None
        for r in range(max_rounds):
            controller.round_count = r
            event = get_random_event(controller)
            if event.__class__.__name__ == event_name:
                first_round = r
                break
        if first_round is not None:
            trigger_rounds.append(first_round)
        else:
            no_trigger_count += 1

    return trigger_rounds, no_trigger_count


class TestFirstLongEventRound(BaseTest):
    """从开局测试两条长线起始事件首次触发的平均回合数。"""

    def test_elf_thief_intro_first_trigger_average_round(self):
        """精灵飞贼起始事件：首次被事件门随机到须不早于 LONG_EVENT_STARTER_EARLIEST_ROUND。"""
        trigger_rounds, no_trigger = _first_trigger_rounds(
            GameController,
            ElfThiefIntroEvent,
            num_trials=NUM_TRIALS,
            max_rounds=MAX_ROUNDS_PER_TRIAL,
        )
        # 允许少量试验在 MAX_ROUNDS 内未触发（随机性）
        self.assertGreaterEqual(
            len(trigger_rounds),
            int(NUM_TRIALS * 0.85),
            f"ElfThiefIntro should trigger in most trials: {len(trigger_rounds)}/{NUM_TRIALS}, no_trigger={no_trigger}",
        )
        mean_round = sum(trigger_rounds) / len(trigger_rounds)
        min_round = min(trigger_rounds)
        max_round = max(trigger_rounds)
        self.assertGreaterEqual(
            min_round,
            LONG_EVENT_STARTER_EARLIEST_ROUND,
            f"Long starters blocked before round {LONG_EVENT_STARTER_EARLIEST_ROUND}",
        )
        print(
            f"ElfThiefIntroEvent first trigger: mean_round={mean_round:.1f}, "
            f"min={min_round}, max={max_round}, triggered={len(trigger_rounds)}/{NUM_TRIALS}"
        )

    def test_puppet_abandonment_first_trigger_average_round(self):
        """黑暗木偶起始事件：首次被事件门随机到须不早于 LONG_EVENT_STARTER_EARLIEST_ROUND。"""
        trigger_rounds, no_trigger = _first_trigger_rounds(
            GameController,
            PuppetAbandonmentEvent,
            num_trials=NUM_TRIALS,
            max_rounds=MAX_ROUNDS_PER_TRIAL,
        )
        self.assertGreaterEqual(
            len(trigger_rounds),
            int(NUM_TRIALS * 0.7),
            f"PuppetAbandonment should trigger in most trials: {len(trigger_rounds)}/{NUM_TRIALS}, no_trigger={no_trigger}",
        )
        mean_round = sum(trigger_rounds) / len(trigger_rounds)
        min_round = min(trigger_rounds)
        max_round = max(trigger_rounds)
        self.assertGreaterEqual(
            min_round,
            LONG_EVENT_STARTER_EARLIEST_ROUND,
            f"Long starters blocked before round {LONG_EVENT_STARTER_EARLIEST_ROUND}",
        )
        print(
            f"PuppetAbandonmentEvent first trigger: mean_round={mean_round:.1f}, "
            f"min={min_round}, max={max_round}, triggered={len(trigger_rounds)}/{NUM_TRIALS}"
        )
