"""终局门配置单一来源：阻塞顺序、consequence 派生与 StorySystem 对齐。"""

import unittest

import models.story_gates as story_gates
from models.story_system import StorySystem


class TestStoryGates(unittest.TestCase):
    def test_blocking_order_matches_documented_gate_sequence(self):
        """与 docs/storyline.md PRE_FINAL_BLOCKING_ORDER：银羽秘藏→木偶补战→飞贼清算→梦境镜子→木偶回声→善良木偶。"""
        expected_gate_keys = (
            "round200_stage_preface",
            "puppet_rematch_gate",
            "elf_rival_final_gate",
            "dream_mirror_prelude_gate",
            "puppet_echo_final_gate",
            "kind_puppet_dialogue_round200",
        )
        self.assertEqual(story_gates.PRE_FINAL_FULL_BLOCKING_GATE_ORDER, expected_gate_keys)
        derived = tuple(
            story_gates.PRE_FINAL_GATE_STORY_CONFIG[k]["consequence_id"] for k in expected_gate_keys
        )
        self.assertEqual(story_gates.PRE_FINAL_BLOCKING_ORDER, derived)

    def test_pre_ending_blocking_is_first_four_of_full_order(self):
        self.assertEqual(
            story_gates.PRE_ENDING_BLOCKING_GATE_KEYS,
            story_gates.PRE_FINAL_FULL_BLOCKING_GATE_ORDER[:4],
        )
        first_four_cids = story_gates.PRE_FINAL_BLOCKING_ORDER[:4]
        self.assertEqual(
            story_gates.PRE_ENDING_BLOCKING_CONSEQUENCE_IDS,
            frozenset(first_four_cids),
        )

    def test_blocking_consequence_sets_consistent(self):
        self.assertEqual(
            story_gates.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS,
            frozenset(story_gates.PRE_FINAL_BLOCKING_ORDER),
        )
        self.assertEqual(len(story_gates.PRE_FINAL_BLOCKING_ORDER), len(story_gates.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS))
        self.assertTrue(story_gates.PRE_ENDING_BLOCKING_CONSEQUENCE_IDS.issubset(story_gates.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS))

    def test_ending_event_consequence_ids_derived_from_gate_keys(self):
        expected = frozenset(
            story_gates.PRE_FINAL_GATE_STORY_CONFIG[k]["consequence_id"]
            for k in story_gates.ENDING_EVENT_GATE_KEYS
        )
        self.assertEqual(story_gates.ENDING_EVENT_CONSEQUENCE_IDS, expected)

    def test_round200_first_gate_consequence_ids(self):
        self.assertEqual(
            story_gates.ROUND200_FIRST_GATE_CONSEQUENCE_IDS,
            (
                story_gates.PRE_FINAL_GATE_STORY_CONFIG["round200_default_first_gate"]["consequence_id"],
                story_gates.PRE_FINAL_GATE_STORY_CONFIG["power_curtain_dialogue_round200"]["consequence_id"],
            ),
        )

    def test_dispatch_order_keys_exist_in_config(self):
        for k in story_gates.PRE_FINAL_DISPATCH_ORDER:
            self.assertIn(k, story_gates.PRE_FINAL_GATE_STORY_CONFIG)

    def test_story_system_reuses_story_gates_constants(self):
        """StorySystem 类属性与 story_gates 为同一对象，避免分叉维护。"""
        self.assertIs(StorySystem.PRE_FINAL_BLOCKING_ORDER, story_gates.PRE_FINAL_BLOCKING_ORDER)
        self.assertIs(StorySystem.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS, story_gates.PRE_FINAL_BLOCKING_CONSEQUENCE_IDS)
        self.assertIs(StorySystem.PRE_ENDING_BLOCKING_CONSEQUENCE_IDS, story_gates.PRE_ENDING_BLOCKING_CONSEQUENCE_IDS)
        self.assertIs(StorySystem.ENDING_EVENT_CONSEQUENCE_IDS, story_gates.ENDING_EVENT_CONSEQUENCE_IDS)
        self.assertIs(StorySystem.PRE_FINAL_BLOCKING_GATE_KEYS, story_gates.PRE_FINAL_BLOCKING_GATE_KEYS)
        self.assertEqual(StorySystem.DEFAULT_ENDING_FORCE_CONSEQUENCE_ID, story_gates.DEFAULT_ENDING_FORCE_CONSEQUENCE_ID)

    def test_events_reexports_match_story_gates(self):
        """models.events 的 re-export 与单一来源一致。"""
        from models import events

        self.assertIs(events.PRE_FINAL_GATE_STORY_CONFIG, story_gates.PRE_FINAL_GATE_STORY_CONFIG)
        self.assertIs(events.ENDING_EVENT_GATE_KEYS, story_gates.ENDING_EVENT_GATE_KEYS)
        self.assertIs(events.PRE_FINAL_DISPATCH_ORDER, story_gates.PRE_FINAL_DISPATCH_ORDER)
        self.assertEqual(events.ELF_THIEF_NAME, story_gates.ELF_THIEF_NAME)


if __name__ == "__main__":
    unittest.main()
