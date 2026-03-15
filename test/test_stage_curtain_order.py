# -*- coding: utf-8 -*-
"""
补全谢幕结局测试框架：验证「舞台谢幕·补全谢幕」路线所需 flag 与状态。

目标状态：
- 回合 190（处于终局前倒数窗口 185~190）
- 玩家 HP 800、ATK 200
- 精灵飞贼：所有事件已完成、关系较高、已拿到钥匙
- 黑暗木偶：已击败
- 邪恶值较低（≤45，善良人格主导）

用于断言 _is_stage_curtain_route_ready、银羽秘藏挂载、以及与善良木偶对话门就绪等。
"""
from test.test_base import BaseTest
from models.story_system import StorySystem


def setup_controller_for_stage_curtain_order(controller, round_count=190):
    """
    将控制器与剧情状态设为「补全谢幕」路线前置条件（与 server --test-gate=stage_curtain_order 一致）。

    - round_count: 当前回合，默认 190（在 185~190 窗口内可挂载银羽秘藏）
    - 玩家: HP 800, ATK 200
    - 精灵飞贼: elf_chain_ended=True, elf_relation=4, elf_key_obtained=True
    - 黑暗木偶: ending:puppet_final_defeated, puppet_evil_value=30
    - 未设置 curtain_call_script_recovered，以便可挂载银羽秘藏
    """
    controller.round_count = round_count
    controller.player.hp = 800
    controller.player._atk = 200
    controller.player_peak_hp = 800
    controller.player_peak_atk = 200

    story = controller.story
    story.elf_chain_ended = True
    story.elf_relation = 4
    story.elf_key_obtained = True
    story.story_tags.add("elf_chain_ended")
    story.story_tags.add("elf_key_obtained")
    story.story_tags.add("ending:puppet_final_defeated")
    story.puppet_evil_value = 30


class TestStageCurtainOrderFlags(BaseTest):
    """补全谢幕路线 flag 与调度逻辑测试。"""

    def setUp(self):
        super().setUp()
        self.controller.scene_manager.go_to("door_scene")

    def test_is_stage_curtain_route_ready_after_setup(self):
        """设置补全谢幕前置状态后，_is_stage_curtain_route_ready 应为 True。"""
        setup_controller_for_stage_curtain_order(self.controller)
        self.assertTrue(
            self.controller.story._is_stage_curtain_route_ready(),
            "飞贼收束+钥匙+木偶已击败+低邪恶值时应满足舞台谢幕前置",
        )

    def test_stage_curtain_route_ready_fails_without_key(self):
        """未拿钥匙时 _is_stage_curtain_route_ready 应为 False。"""
        setup_controller_for_stage_curtain_order(self.controller)
        self.controller.story.elf_key_obtained = False
        self.controller.story.story_tags.discard("elf_key_obtained")
        self.assertFalse(self.controller.story._is_stage_curtain_route_ready())

    def test_stage_curtain_route_ready_fails_without_puppet_defeated(self):
        """未击败黑暗木偶时 _is_stage_curtain_route_ready 应为 False。"""
        setup_controller_for_stage_curtain_order(self.controller)
        self.controller.story.story_tags.discard("ending:puppet_final_defeated")
        self.assertFalse(self.controller.story._is_stage_curtain_route_ready())

    def test_stage_curtain_route_ready_fails_high_evil(self):
        """邪恶值 > 45 时 _is_stage_curtain_route_ready 应为 False。"""
        setup_controller_for_stage_curtain_order(self.controller)
        self.controller.story.puppet_evil_value = 50
        self.assertFalse(self.controller.story._is_stage_curtain_route_ready())

    def test_ensure_stage_curtain_preface_schedule_registers_at_round_190(self):
        """回合 190 且满足前置时，ensure_stage_curtain_preface_schedule 应成功挂载银羽秘藏。"""
        setup_controller_for_stage_curtain_order(self.controller, round_count=190)
        story = self.controller.story
        registered = story.ensure_stage_curtain_preface_schedule()
        self.assertTrue(registered, "190 回合窗口内应挂载银羽秘藏")
        self.assertIn(
            story.STAGE_CURTAIN_FORCE_CONSEQUENCE_ID,
            story.pending_consequences,
            "pending_consequences 中应有银羽秘藏",
        )

    def test_player_and_round_state_after_setup(self):
        """setup 后玩家与回合数应符合预期。"""
        setup_controller_for_stage_curtain_order(self.controller, round_count=190)
        self.assertEqual(self.controller.round_count, 190)
        self.assertEqual(self.controller.player.hp, 800)
        self.assertEqual(self.controller.player.atk, 200)

    def test_kind_puppet_dialogue_ready_after_script_recovered(self):
        """取回剧本后、邪恶值低时，_is_kind_puppet_dialogue_ready 应为 True（与善良木偶对话门可挂载）。"""
        setup_controller_for_stage_curtain_order(self.controller)
        self.controller.round_count = 200
        self.controller.story.story_tags.add("curtain_call_script_recovered")
        self.assertTrue(
            self.controller.story._is_kind_puppet_dialogue_ready(),
            "已拿剧本+已击败木偶+邪恶值≤45 时应可挂载与善良木偶对话门",
        )
