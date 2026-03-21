"""故事标记集中模块的一致性检查。"""
import unittest

from models import story_flags as sf
from models.narrative.elf_rival_grudge import ELF_RIVAL_GRUDGE_BARK_ORDER


class StoryFlagsTests(unittest.TestCase):
    def test_choice_tag_matches_register_choice_prefix(self):
        self.assertEqual(sf.choice_tag("foo"), "choice:foo")

    def test_static_choice_string_constants_unique(self):
        values = list(sf._STATIC_FOR_TEST)
        self.assertEqual(len(values), len(set(values)), "重复的 flag 字符串常量")

    def test_elf_grudge_bark_order_matches_narrative_module(self):
        keys_from_flags = sf.ELF_GRUDGE_BARK_KEYS
        keys_from_narrative = tuple(k for k, _ in ELF_RIVAL_GRUDGE_BARK_ORDER)
        self.assertEqual(keys_from_flags, keys_from_narrative)

    def test_flag_index_sample_references_real_constants(self):
        for kind, value, _note in sf.FLAG_INDEX:
            if kind == "choice":
                self.assertIn(value, sf._STATIC_FOR_TEST, msg=value)
            if kind == "grudge":
                self.assertIn(value, sf.ELF_GRUDGE_BARK_KEYS, msg=value)


if __name__ == "__main__":
    unittest.main()
