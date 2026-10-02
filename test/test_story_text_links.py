"""剧情文本串联：替补演员主角设定、月蚀线父亲与飞贼莱希娅的父女线。"""
import random
import unittest

from game import GameController
from models.events.elf_chain import ElfEpilogueEvent
from models.events.moon_verdict import MoonVerdictEvent
from models.narrative.elf_rival_grudge import (
    ELF_GRUDGE_FATHER_DIARY_LINE,
    collect_elf_rival_grudge_barks,
)
from models.narrative.stage_curtain_epilogue import build_stage_epilogue_lines


class TestUnderstudyProtagonist(unittest.TestCase):
    def test_opening_introduces_understudy(self):
        game = GameController()
        opening = "\n".join(game.messages)
        self.assertIn("替补", opening)

    def test_default_ending_is_maze_exit(self):
        game = GameController()
        game.story._resolve_default_final_outcome()
        self.assertEqual(game.game_clear_info["ending_title"], "结局：迷宫出口")
        self.assertIn("工作牌", "\n".join(game.messages))


class TestFatherDaughterThread(unittest.TestCase):
    def setUp(self):
        random.seed(7)
        self.game = GameController()
        self.story = self.game.story
        self.game.clear_messages()

    def _give_diary(self, source):
        self.story.story_tags.add("moon_bounty_diary_obtained")
        self.story.moon_bounty_diary_source = source

    def _epilogue(self, relation, choice):
        self.story.elf_relation = relation
        event = ElfEpilogueEvent(self.game)
        getattr(event, choice)()
        return "\n".join(self.game.messages)

    def test_epilogue_with_entrusted_diary_reunites_in_words(self):
        self._give_diary("thief_testimony")
        text = self._epilogue(4, "accept_bond")
        self.assertIn("他还在找我", text)

    def test_epilogue_after_knocking_father_out_asks_if_he_lives(self):
        self._give_diary("thief_body")
        text = self._epilogue(0, "close_clean")
        self.assertIn("他还活着吗", text)

    def test_hostile_epilogue_never_delivers_feather(self):
        self._give_diary("thief_testimony")
        text = self._epilogue(-3, "burn_bridge")
        self.assertIn("没有机会交给她", text)

    def test_no_diary_no_father_line(self):
        text = self._epilogue(4, "accept_bond")
        self.assertNotIn("日记", text)

    def test_verdict_mentions_feather_only_after_meeting_elf(self):
        self._give_diary("thief_body")
        without_elf = MoonVerdictEvent(self.game).description
        self.assertNotIn("银色羽毛", without_elf)
        self.story.story_tags.add("elf_met")
        with_elf = MoonVerdictEvent(self.game).description
        self.assertIn("银色羽毛", with_elf)

    def test_stage_epilogue_closes_father_daughter_thread(self):
        for route in ("order", "freedom", "power"):
            lines = build_stage_epilogue_lines(route, {"elf_outcome": "alliance", "diary_source": "thief_testimony"})
            self.assertTrue(any("父" in line or "提词人" in line or "旧日记" in line for line in lines), route)
            hostile = build_stage_epilogue_lines(route, {"elf_outcome": "hostile", "diary_source": "thief_body"})
            self.assertTrue(any("没能寄出去" in line for line in hostile), route)
            no_diary = build_stage_epilogue_lines(route, {"elf_outcome": "alliance"})
            self.assertFalse(any("旧日记" in line or "没能寄出去" in line for line in no_diary), route)

    def test_rival_fight_mentions_father_when_holding_diary(self):
        self.assertNotIn(ELF_GRUDGE_FATHER_DIARY_LINE, collect_elf_rival_grudge_barks(self.story))
        self._give_diary("thief_body")
        self.assertIn(ELF_GRUDGE_FATHER_DIARY_LINE, collect_elf_rival_grudge_barks(self.story))


if __name__ == "__main__":
    unittest.main()
