# -*- coding: utf-8 -*-
"""
补全谢幕结局测试框架：验证「舞台谢幕·补全谢幕」路线所需 flag 与状态。

目标状态：
- 回合 190（处于终局前倒数窗口 185~190）
- 玩家 HP 800、ATK 200
- 精灵飞贼：所有事件已完成、关系较高、已拿到钥匙
- 黑暗木偶：已击败
- 邪恶值较低（≤45，善良人格主导）

用于断言 _is_stage_curtain_route_ready、并通过结局前判定流程自然挂载银羽秘藏、以及与善良木偶对话门就绪等。
"""
import unittest.mock

from models.door import DoorEnum
from test.test_base import BaseTest


def setup_controller_for_stage_curtain_order(controller, round_count=190):
    """
    将控制器与剧情状态设为「补全谢幕」路线前置条件（与 server --test-gate=stage_curtain_order 一致）。

    - round_count: 当前回合，默认 190（在 185~190 窗口内可挂载银羽秘藏）
    - 玩家: HP 800, ATK 200
    - 精灵飞贼: elf_chain_ended=True, elf_relation=4, elf_key_obtained=True
    - 黑暗木偶: ending:puppet_final_defeated, puppet_evil_value=30
    - 飞贼清算、木偶补战视为已完结，从 pending 移除并加入 consumed，不再触发
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
    story.pending_consequences.pop(story.PUPPET_PRE_FINAL_CONSEQUENCE_ID, None)
    story.pending_consequences.pop(story.ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID, None)
    story.consumed_consequences.add(story.PUPPET_PRE_FINAL_CONSEQUENCE_ID)
    story.consumed_consequences.add(story.ELF_RIVAL_PRE_FINAL_CONSEQUENCE_ID)


def setup_controller_for_stage_curtain_power(controller, round_count=190):
    """
    将控制器与剧情状态设为「接管谢幕」分支前置条件（与 server --test-gate=stage_curtain_power 一致）。

    - round_count: 当前回合，默认 190
    - 玩家: HP 800, ATK 200
    - 精灵飞贼: elf_chain_ended=True, elf_relation=-5（可触发清算战）, elf_key_obtained=False, elf_outcome:hostile
    - 黑暗木偶: ending:puppet_final_defeated（并明确非逃跑结局）, puppet_evil_value=55
    - 不设置 curtain_call_script_recovered（未拿钥匙无法取回剧本）
    """
    controller.round_count = round_count
    controller.player.hp = 800
    controller.player._atk = 200
    controller.player_peak_hp = 800
    controller.player_peak_atk = 200

    story = controller.story
    story.elf_chain_ended = True
    story.elf_relation = -5
    story.elf_key_obtained = False
    story.story_tags.add("elf_chain_ended")
    story.story_tags.add("elf_outcome:hostile")
    story.story_tags.add("ending_hook:elf_hostile")
    story.story_tags.discard("elf_key_obtained")
    story.choice_flags.add("elf_outcome_hostile")
    story.story_tags.discard("puppet_arc_active")
    story.story_tags.discard("ending:puppet_final_escape_recorded")
    story.story_tags.add("ending:puppet_final_defeated")
    story.puppet_evil_value = 55


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

    def test_pre_final_schedule_naturally_registers_stage_curtain_preface_at_round_190(self):
        """回合 190 且满足前置时，应由结局前事件调度判定自然挂载银羽秘藏，而非预先指定下一门。"""
        setup_controller_for_stage_curtain_order(self.controller, round_count=190)
        story = self.controller.story
        scheduled = story.ensure_pre_final_event_schedule()
        self.assertTrue(scheduled, "190 回合窗口内应纳入至少一个结局前事件")
        self.assertIn(
            story.STAGE_CURTAIN_FORCE_CONSEQUENCE_ID,
            story.pending_consequences,
            "pending_consequences 中应出现银羽秘藏后果",
        )

    def test_player_and_round_state_after_setup(self):
        """setup 后玩家与回合数应符合预期。"""
        setup_controller_for_stage_curtain_order(self.controller, round_count=190)
        self.assertEqual(self.controller.round_count, 190)
        self.assertEqual(self.controller.player.hp, 800)
        self.assertEqual(self.controller.player.atk, 200)

    def test_stage_curtain_preface_can_be_triggered_via_pre_final_conditions(self):
        """仅设置前置参数后，走结局前调度 + 进门检查，也应触发银羽秘藏并回收剧本。"""
        setup_controller_for_stage_curtain_order(self.controller, round_count=190)
        story = self.controller.story
        story.ensure_pre_final_event_schedule()

        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.random", return_value=0.95), unittest.mock.patch(
            "models.story_system.random.uniform", return_value=0.0
        ):
            changed = story.apply_pre_enter_checks(reward_door)

        self.assertEqual(changed.enum.name, "REWARD")
        self.assertIn("ending_stage_curtain_preface", story.consumed_consequences)
        self.assertIn("curtain_call_script_recovered", story.story_tags)

    def test_kind_puppet_dialogue_ready_after_script_recovered(self):
        """取回剧本后、邪恶值低时，_is_kind_puppet_dialogue_ready 应为 True（与善良木偶对话门可挂载）。"""
        setup_controller_for_stage_curtain_order(self.controller)
        self.controller.round_count = 200
        self.controller.story.story_tags.add("curtain_call_script_recovered")
        self.assertTrue(
            self.controller.story._is_kind_puppet_dialogue_ready(),
            "已拿剧本+已击败木偶+邪恶值≤45 时应可挂载与善良木偶对话门",
        )


class TestStageCurtainPowerFlags(BaseTest):
    """接管谢幕路线 flag 与调度逻辑测试。"""

    def setUp(self):
        super().setUp()
        self.controller.scene_manager.go_to("door_scene")

    def test_power_setup_matches_expected_state(self):
        """setup 后应符合接管分支预期参数。"""
        setup_controller_for_stage_curtain_power(self.controller, round_count=190)
        self.assertEqual(self.controller.round_count, 190)
        self.assertEqual(self.controller.player.hp, 800)
        self.assertEqual(self.controller.player.atk, 200)
        self.assertFalse(self.controller.story.elf_key_obtained)
        self.assertIn("elf_outcome:hostile", self.controller.story.story_tags)
        self.assertIn("elf_outcome_hostile", self.controller.story.choice_flags)
        self.assertIn("ending:puppet_final_defeated", self.controller.story.story_tags)
        self.assertNotIn("ending:puppet_final_escape_recorded", self.controller.story.story_tags)
        self.assertEqual(self.controller.story.puppet_evil_value, 55)
        self.assertLessEqual(self.controller.story.elf_relation, -4)
        self.assertIn("ending_hook:elf_hostile", self.controller.story.story_tags)

    def test_power_route_cannot_trigger_stage_curtain_preface(self):
        """未拿钥匙且邪恶值高时，不应挂载银羽秘藏。"""
        setup_controller_for_stage_curtain_power(self.controller, round_count=190)
        story = self.controller.story
        self.assertFalse(story._is_stage_curtain_route_ready())
        self.assertFalse(story.ensure_stage_curtain_preface_schedule())
        self.assertNotIn(story.STAGE_CURTAIN_FORCE_CONSEQUENCE_ID, story.pending_consequences)

    def test_round_200_prefers_puppet_echo_gate_without_key(self):
        """第 200 回合时，在无钥匙+高邪恶前置下应优先挂载木偶回声门。"""
        setup_controller_for_stage_curtain_power(self.controller, round_count=190)
        self.controller.round_count = 200
        story = self.controller.story

        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled)
        self.assertIn("ending_puppet_echo_final_gate", story.pending_consequences)
        self.assertNotIn("ending_power_curtain_dialogue_round200", story.pending_consequences)
