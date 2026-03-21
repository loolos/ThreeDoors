"""models.narrative：飞贼仇句、复仇门配置与 story_system 叙事常量一致性。"""

import unittest

from models.narrative import elf_rival_grudge, revenge_hunters, story_system_lines
from models.narrative.stage_curtain_epilogue import build_stage_epilogue_lines


class TestNarrative(unittest.TestCase):
    def test_grudge_bark_flags_unique_order(self):
        keys = [k for k, _ in elf_rival_grudge.ELF_RIVAL_GRUDGE_BARK_ORDER]
        self.assertEqual(len(keys), len(set(keys)))

    def test_collect_grudge_respects_cap(self):
        keys = [k for k, _ in elf_rival_grudge.ELF_RIVAL_GRUDGE_BARK_ORDER]

        class S:
            pass

        story = S()
        story.choice_flags = set(keys[:7])
        barks = elf_rival_grudge.collect_elf_rival_grudge_barks(story)
        self.assertLessEqual(len(barks), 6)

    def test_revenge_profiles_have_required_keys(self):
        for cid, prof in revenge_hunters.REVENGE_HUNTER_PROFILES.items():
            self.assertIn("hunter_name", prof, msg=cid)
            self.assertIn("hunter_hint", prof, msg=cid)
            self.assertIn("message", prof, msg=cid)

    def test_story_system_lines_non_empty(self):
        self.assertTrue(story_system_lines.MSG_PUPPET_ECHO_SHATTERED)
        self.assertTrue(story_system_lines.MSG_DEFAULT_FINAL_BOSS_DEFEATED)
        self.assertIn("爆发登场", story_system_lines.format_puppet_phase2_entrance("A", "B", 10, 20))

    def test_stage_curtain_epilogue_order_alliance(self):
        lines = build_stage_epilogue_lines(
            "order",
            {"elf_outcome": "alliance", "order": 0, "power": 0, "risk": 0},
        )
        self.assertTrue(any("银羽飞贼" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
