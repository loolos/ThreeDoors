import unittest.mock
import random

from models.door import DoorEnum
from models.events import (
    build_puppet_final_boss_payload,
    MoonBountyEvent,
    MoonVerdictEvent,
    ElfThiefIntroEvent,
    ElfSideMerchantDisguisedEvent,
    ElfRooftopDuelEvent,
    run_script_vault_recovery,
    EndingStageCurtainGateEvent,
    EndingStageKindPuppetDialogueEvent,
    EndingPowerCurtainDirectEvent,
    EndingPowerCurtainChoiceEvent,
    RefugeeCaravanEvent,
    PuppetAbandonmentEvent,
    PuppetSignalEvent,
    PuppetKindEchoEvent,
    PuppetPersonaRiftEvent,
    PuppetCoreDescentEvent,
    EndingFinalFirstGateEvent,
    EndingFinalSecondGateEvent,
    _collect_stage_curtain_scores,
    _resolve_stage_curtain_outcome,
)
from models.items import FlyingHammer
from models.monster import Monster
from models.game_config import GameConfig
from test.test_base import BaseTest


class TestStorySystem(BaseTest):
    def test_build_puppet_final_boss_payload_default_phase2_ratios(self):
        """终战 payload 默认二阶段：满血门槛 + 爆发治疗比例。"""
        payload = build_puppet_final_boss_payload(self.controller)
        self.assertEqual(payload.get("phase2_min_hp_ratio"), 1.0)
        self.assertEqual(payload.get("phase2_burst_heal_ratio"), 0.42)
        payload_override = build_puppet_final_boss_payload(
            self.controller, phase2_burst_heal_ratio=0.58
        )
        self.assertEqual(payload_override.get("phase2_burst_heal_ratio"), 0.58)
        self.assertEqual(payload_override.get("phase2_min_hp_ratio"), 1.0)

    def setUp(self):
        super().setUp()
        # 测试中禁用事件门「候选<5 时 30% 跳过改写」，使单次只应用一条后果的断言可预测
        self._skip_rewrite_patcher = unittest.mock.patch.object(
            GameConfig, "EVENT_DOOR_SKIP_REWRITE_CHANCE", 0.0
        )
        self._skip_rewrite_patcher.start()

    def tearDown(self):
        if hasattr(self, "_skip_rewrite_patcher"):
            self._skip_rewrite_patcher.stop()
        super().tearDown()
    def test_elf_chain_followup_is_scheduled_between_5_and_15_rounds(self):
        story = self.controller.story
        self.controller.round_count = 12
        event = ElfThiefIntroEvent(self.controller)
        event.resolve_choice(0)

        self.assertTrue(getattr(story, "elf_chain_started", False))
        pending = list(story.pending_consequences.values())
        # 1 条主链下一环 + 3 条支线（怪物门/商店门未认出/认出）
        self.assertGreaterEqual(len(pending), 1)
        shadow = next((c for c in pending if c.payload.get("event_key") == "elf_shadow_mark_event"), None)
        self.assertIsNotNone(shadow, "应有登记下一环银羽暗号的后果")
        self.assertEqual(shadow.effect_key, "force_story_event")
        self.assertEqual(shadow.min_round, 17)   # 12 + 5
        self.assertIsNone(shadow.max_round)     # 精灵链不设上限，避免错过事件门后链断

    def test_elf_side_monster_payload_hint_is_printed_on_trigger(self):
        story = self.controller.story
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=30, atk=6, tier=1),
            hint="原始提示",
        )
        story.register_consequence(
            choice_flag="elf_side_reg",
            consequence_id="elf_side_monster_print_once",
            effect_key="elf_side_monster_mark",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={
                "chance": 1.0,
                "message": "门后有人喊你名字，你还没站稳就被拽进战圈。",
                "hint": "她被追兵缠住，正在把你强拉进并肩作战。",
            },
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.0
        ):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertTrue(getattr(changed_door.monster, "elf_side_story", False))
        self.assertEqual(changed_door.hint, "她被追兵缠住，正在把你强拉进并肩作战。")
        self.assertIn("门后有人喊你名字，你还没站稳就被拽进战圈。", self.controller.messages)
        # hint 文案已合并到门描述，不再重复加入 controller.messages

    def test_one_choice_can_register_multiple_consequences(self):
        story = self.controller.story
        story.register_choice(
            choice_flag="test_choice",
            moral_delta=0,
            consequences=[
                {
                    "consequence_id": "multi_pos",
                    "effect_key": "guard_reward",
                    "trigger_door_types": ["EVENT"],
                },
                {
                    "consequence_id": "multi_neg",
                    "effect_key": "lose_gold",
                    "trigger_door_types": ["SHOP"],
                },
            ],
        )
        self.assertEqual(len(story.pending_consequences), 2)

    def test_same_consequence_id_only_registered_once(self):
        story = self.controller.story
        first = story.register_consequence(
            choice_flag="x",
            consequence_id="once_id",
            effect_key="guard_reward",
        )
        second = story.register_consequence(
            choice_flag="x",
            consequence_id="once_id",
            effect_key="guard_reward",
        )
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(story.pending_consequences), 1)

    def test_same_followup_effect_triggers_once(self):
        story = self.controller.story
        self.player.gold = 0
        story.register_consequence(
            choice_flag="x",
            consequence_id="one_time_reward",
            effect_key="guard_reward",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"gold": 30},
        )

        event_door_1 = DoorEnum.EVENT.create_instance(controller=self.controller)
        event_door_2 = DoorEnum.EVENT.create_instance(controller=self.controller)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(event_door_1)
            gold_after_first = self.player.gold
            story.apply_pre_enter_checks(event_door_2)

        self.assertEqual(gold_after_first, 30)
        self.assertEqual(self.player.gold, 30)
        self.assertIn("one_time_reward", story.consumed_consequences)

    def test_positive_and_negative_followups_from_same_behavior(self):
        story = self.controller.story
        self.player.gold = 100
        first_shop_item_cost = self.controller.current_shop.shop_items[0].cost
        story.register_choice(
            choice_flag="mixed_behavior",
            consequences=[
                {
                    "consequence_id": "mixed_discount",
                    "effect_key": "black_market_discount",
                    "chance": 1.0,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.5},
                },
                {
                    "consequence_id": "mixed_penalty",
                    "effect_key": "lose_gold",
                    "chance": 1.0,
                    "trigger_door_types": ["EVENT"],
                    "payload": {"amount": 20},
                },
            ],
        )

        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)
            story.apply_pre_enter_checks(event_door)

        self.assertLess(self.controller.current_shop.shop_items[0].cost, first_shop_item_cost)
        self.assertEqual(self.player.gold, 80)
        self.assertIn("mixed_discount", story.consumed_consequences)
        self.assertIn("mixed_penalty", story.consumed_consequences)

    def test_high_moral_can_convert_sensitive_monster_encounter(self):
        story = self.controller.story
        story.moral_score = 60
        angel = Monster(name="天使", hp=80, atk=16, tier=5)
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller, monster=angel)

        # 无候选后果，只走道德判定；需 patch random.random 使 0.22 与 0.5 判定通过
        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed_door.enum.name, "REWARD")

    def test_high_moral_does_not_affect_irrelevant_monster(self):
        story = self.controller.story
        story.moral_score = 60
        slime = Monster(name="史莱姆", hp=18, atk=2, tier=1)
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller, monster=slime)
        hp_before = monster_door.monster.hp

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed_door.enum.name, "MONSTER")
        self.assertEqual(changed_door.monster.hp, hp_before)

    def test_chain_followups_can_be_queued_after_trigger(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="chain_root",
            consequence_id="chain_start",
            effect_key="guard_reward",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={
                "gold": 10,
                "chain_followups": [
                    {
                        "consequence_id": "chain_second",
                        "effect_key": "lose_gold",
                        "chance": 1.0,
                        "trigger_door_types": ["SHOP"],
                        "payload": {"amount": 5},
                    }
                ],
            },
        )
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(event_door)

        self.assertIn("chain_second", story.pending_consequences)
        self.assertIn("consumed:chain_start", story.story_tags)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)
        self.assertIn("chain_second", story.consumed_consequences)


    def test_delay_rounds_defers_consequence_trigger(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="delay_case",
            consequence_id="delay_gold_loss",
            effect_key="lose_gold",
            chance=1.0,
            trigger_door_types=["EVENT"],
            delay_rounds=3,
            payload={"amount": 15},
        )
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        self.player.gold = 100

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(event_door)
        self.assertEqual(self.player.gold, 100)
        self.assertIn("delay_gold_loss", story.pending_consequences)

        self.controller.round_count = 3
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(event_door)
        self.assertEqual(self.player.gold, 85)
        self.assertIn("delay_gold_loss", story.consumed_consequences)

    def test_force_on_expire_can_rewrite_non_matching_door(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="expire_force_case",
            consequence_id="expire_force_event_once",
            effect_key="force_story_event",
            chance=0.1,
            trigger_door_types=["EVENT"],
            max_round=5,
            force_on_expire=True,
            force_door_type="EVENT",
            payload={"event_key": "moon_verdict_event"},
        )
        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller)

        self.controller.round_count = 4
        unchanged = story.apply_pre_enter_checks(reward_door)
        self.assertEqual(unchanged.enum.name, "REWARD")
        self.assertIn("expire_force_event_once", story.pending_consequences)

        self.controller.round_count = 5
        changed = story.apply_pre_enter_checks(reward_door)
        self.assertEqual(changed.enum.name, "EVENT")
        self.assertEqual(getattr(changed, "story_forced_event_key", ""), "moon_verdict_event")
        self.assertIn("expire_force_event_once", story.consumed_consequences)

    def test_force_on_expire_can_force_revenge_battle_from_any_door(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="expire_revenge_case",
            consequence_id="expire_revenge_once",
            effect_key="revenge_ambush",
            chance=0.0,
            trigger_door_types=["EVENT"],
            max_round=2,
            force_on_expire=True,
            force_door_type="MONSTER",
            payload={"force_hunter": True, "hunter_name": "追债者"},
        )
        self.controller.round_count = 2
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        changed = story.apply_pre_enter_checks(shop_door)

        self.assertEqual(changed.enum.name, "MONSTER")
        self.assertEqual(changed.monster.name, "追债者")
        self.assertIn("expire_revenge_once", story.consumed_consequences)

    def test_caravan_extort_registers_deadline_forced_revenge(self):
        story = self.controller.story
        self.controller.round_count = 7
        event = RefugeeCaravanEvent(self.controller)
        event.extort()

        consequence = story.pending_consequences.get("caravan_extort_deadline_revenge")
        self.assertIsNotNone(consequence)
        self.assertEqual(consequence.effect_key, "revenge_ambush")
        self.assertEqual(consequence.max_round, 17)
        self.assertTrue(consequence.force_on_expire)
        self.assertEqual(consequence.force_door_type, "MONSTER")
        self.assertTrue(consequence.payload.get("force_hunter", False))

    def test_can_register_custom_effect_handler(self):
        story = self.controller.story
        marker = {"called": False}

        def custom_handler(consequence, door):
            marker["called"] = True
            self.controller.add_message("自定义处理器已触发")
            return True, door

        story.register_effect_handler("custom_effect", custom_handler)
        story.register_consequence(
            choice_flag="custom",
            consequence_id="custom_id",
            effect_key="custom_effect",
            chance=1.0,
            trigger_door_types=["EVENT"],
        )
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(event_door)

        self.assertTrue(marker["called"])
        self.assertIn("custom_id", story.consumed_consequences)

    def test_revenge_ambush_from_event_door_waits_for_defeat_to_consume(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="revenge_case",
            consequence_id="revenge_hunter_case",
            effect_key="revenge_ambush",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"force_hunter": True},
        )
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(event_door)

        self.assertEqual(changed_door.enum.name, "MONSTER")
        hunter_names = {"土匪", "野狼", "蝙蝠", "小哥布林", "狼人", "食人魔", "美杜莎", "幽灵", "吸血鬼",
                       "暗影刺客", "死亡骑士", "冥界使者", "海妖", "雷鸟"}
        self.assertIn(changed_door.monster.name, hunter_names)
        self.assertIn("revenge_hunter_case", story.pending_consequences)
        self.assertNotIn("revenge_hunter_case", story.consumed_consequences)
        self.assertTrue(getattr(changed_door.monster, "story_consume_on_defeat", False))

    def test_shop_discount_applies_to_selected_shop_door(self):
        story = self.controller.story
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        original_cost = shop_door.shop.shop_items[0].cost
        story.register_consequence(
            choice_flag="discount_case",
            consequence_id="shop_discount_case",
            effect_key="black_market_discount",
            chance=1.0,
            trigger_door_types=["SHOP"],
            payload={"ratio": 0.5},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(shop_door)

        self.assertEqual(changed_door.enum.name, "SHOP")
        self.assertLess(changed_door.shop.shop_items[0].cost, original_cost)
        self.assertIn("shop_discount_case", story.consumed_consequences)

    def test_followup_logs_are_user_friendly_without_technical_ids(self):
        """后续影响应展示可读性描述，不展示技术性 ID"""
        story = self.controller.story
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        story.register_consequence(
            choice_flag="log_case",
            consequence_id="log_discount_case",
            effect_key="black_market_discount",
            chance=1.0,
            trigger_door_types=["SHOP"],
            payload={"ratio": 0.5},
        )
        self.controller.messages.clear()

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)

        combined = "\n".join(self.controller.messages)
        self.assertNotIn("旧事", combined)
        self.assertIn("掌柜就改了价签", combined)
        self.assertNotIn("【后续影响", combined)
        self.assertNotIn("log_discount_case", combined)

    def test_knight_revenge_log_is_diegetic(self):
        story = self.controller.story
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        story.register_consequence(
            choice_flag="knight_aided",
            consequence_id="knight_aid_traitor_revenge",
            effect_key="revenge_ambush",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"force_hunter": True, "hunter_name": "暗影刺客"},
        )
        self.controller.messages.clear()

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(event_door)

        combined = "\n".join(self.controller.messages)
        self.assertIn("因为你之前救了骑士", combined)
        self.assertIn("来追杀你了", combined)
        self.assertIn("暗影刺客", combined)

    def test_force_story_event_can_override_next_event_door(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="force_event_case",
            consequence_id="force_moon_verdict_once",
            effect_key="force_story_event",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"event_key": "moon_verdict_event"},
        )
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(event_door)

        self.assertEqual(getattr(changed_door, "story_forced_event_key", ""), "moon_verdict_event")
        changed_door.enter()
        self.assertEqual(self.controller.current_event.title, "月蚀审判")

    def test_force_story_event_attaches_to_door_extension_port(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="force_event_extension_case",
            consequence_id="force_event_extension_once",
            effect_key="force_story_event",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"event_key": "moon_verdict_event", "hint": "门后正在开庭。"},
        )
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(event_door)

        extension_types = [ext.get("extension_type") for ext in getattr(changed_door, "door_extensions", [])]
        self.assertIn("force_story_event", extension_types)
        self.assertEqual(getattr(changed_door, "story_forced_event_key", ""), "moon_verdict_event")

    def test_treasure_marked_item_rewrites_reward_door(self):
        story = self.controller.story
        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller, reward={"gold": 20})
        story.register_consequence(
            choice_flag="treasure_case",
            consequence_id="treasure_marked_once",
            effect_key="treasure_marked_item",
            chance=1.0,
            trigger_door_types=["REWARD"],
            payload={"item_key": "giant_scroll", "gold_bonus": 10},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(reward_door)

        reward = changed_door.reward
        item_names = [getattr(key, "name", "") for key in reward.keys() if key != "gold"]
        self.assertIn("巨大卷轴", item_names)
        self.assertEqual(reward.get("gold", 0), 30)

    def test_treasure_marked_extension_is_idempotent_on_reapply(self):
        story = self.controller.story
        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller, reward={"gold": 15})
        story.register_consequence(
            choice_flag="treasure_extension_idempotent_case",
            consequence_id="treasure_extension_idempotent_once",
            effect_key="treasure_marked_item",
            chance=1.0,
            trigger_door_types=["REWARD"],
            payload={"item_key": "giant_scroll", "gold_bonus": 5},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(reward_door)

        ext = next(
            (cfg for cfg in getattr(changed_door, "door_extensions", []) if cfg.get("extension_type") == "treasure_marked_item"),
            None,
        )
        self.assertIsNotNone(ext)
        reward_before = dict(changed_door.reward)
        apply_result = story.apply_door_extension(door=changed_door, extension=ext, hook="before_enter")
        self.assertEqual(dict(changed_door.reward), reward_before)
        self.assertTrue(apply_result.get("applied"))

    def test_treasure_vanish_can_empty_reward_door(self):
        story = self.controller.story
        reward_door = DoorEnum.REWARD.create_instance(
            controller=self.controller,
            reward={"gold": 66, FlyingHammer(name="临时飞锤", cost=1): 1},
        )
        story.register_consequence(
            choice_flag="treasure_void_case",
            consequence_id="treasure_void_once",
            effect_key="treasure_vanish",
            chance=1.0,
            trigger_door_types=["REWARD"],
            payload={"fake_gold": 6},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(reward_door)

        self.assertEqual(changed_door.reward, {"gold": 6})

    def test_trap_extension_can_replace_default_trap_enter(self):
        trap_door = DoorEnum.TRAP.create_instance(controller=self.controller)
        trap_door.add_door_extension(
            {
                "extension_type": "trap_rewrite_to_reward",
                "reward": {"gold": 19},
                "hint": "神佑余辉",
            }
        )
        hp_before = self.player.hp
        self.player.gold = 0

        entered = trap_door.enter()

        self.assertTrue(entered)
        self.assertEqual(self.player.hp, hp_before)
        self.assertEqual(self.player.gold, 19)
        self.assertNotIn("你触发了机关！", self.controller.messages)

    def test_run_door_extensions_dispatches_each_extension_config(self):
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        event_door.add_door_extension({"extension_type": "unit_test_one"})
        event_door.add_door_extension({"extension_type": "unit_test_two"})
        original_handler = self.controller.story.apply_door_extension
        mock_handler = unittest.mock.Mock(
            side_effect=[{"applied": True, "index": 1}, None]
        )
        self.controller.story.apply_door_extension = mock_handler
        try:
            outputs = event_door.run_door_extensions(hook="before_enter")
        finally:
            self.controller.story.apply_door_extension = original_handler

        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0].get("index"), 1)
        self.assertEqual(mock_handler.call_count, 2)

    def test_long_chain_can_progress_from_mid_battle_to_forced_verdict(self):
        story = self.controller.story
        moon_event = MoonBountyEvent(self.controller)
        moon_event.resolve_choice(0)
        self.assertIn("moon_chain_accept_mid_battle", story.pending_consequences)

        first_event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            mid_battle_door = story.apply_pre_enter_checks(first_event_door)
        self.assertEqual(mid_battle_door.enum.name, "MONSTER")
        self.assertEqual(mid_battle_door.monster.name, "命运乐谱大盗")
        self.assertTrue(hasattr(mid_battle_door.monster, "story_consequence_id"))
        self.assertIn("moon_chain_accept_mid_battle", story.pending_consequences)

        story.resolve_battle_consequence(mid_battle_door.monster, defeated=True)
        self.assertIn("moon_chain_accept_force_verdict", story.pending_consequences)
        self.assertIn("moon_bounty_diary_obtained", story.story_tags)
        self.assertEqual(getattr(story, "moon_bounty_diary_source", ""), "thief_body")

        second_event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            forced_event_door = story.apply_pre_enter_checks(second_event_door)
        self.assertEqual(getattr(forced_event_door, "story_forced_event_key", ""), "moon_verdict_event")

    def test_moon_protect_route_battle_sets_guardian_diary_state(self):
        story = self.controller.story
        moon_event = MoonBountyEvent(self.controller)
        moon_event.resolve_choice(1)
        self.assertIn("moon_chain_protect_mid_battle", story.pending_consequences)

        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            mid_battle_door = story.apply_pre_enter_checks(event_door)
        self.assertEqual(mid_battle_door.enum.name, "MONSTER")
        self.assertEqual(mid_battle_door.monster.name, "命运乐章守护者")

        story.resolve_battle_consequence(mid_battle_door.monster, defeated=True)
        self.assertEqual(getattr(story, "moon_bounty_diary_source", ""), "thief_testimony")
        self.assertIn("moon_chain_protect_force_verdict", story.pending_consequences)

        verdict_event = MoonVerdictEvent(self.controller)
        self.assertIn("我没偷那份命运的乐谱", verdict_event.description)

    def test_puppet_intro_schedules_mainline_rift_in_20_to_30_rounds(self):
        story = self.controller.story
        self.controller.round_count = 9
        event = PuppetAbandonmentEvent(self.controller)
        event.resolve_choice(0)

        self.assertIn("puppet_arc_active", story.story_tags)
        self.assertIn("puppet_mainline_intro_to_puppet_persona_rift_event", story.pending_consequences)
        rift = story.pending_consequences["puppet_mainline_intro_to_puppet_persona_rift_event"]
        self.assertEqual(rift.min_round, 29)  # 9 + 20
        self.assertEqual(rift.max_round, 39)  # 9 + 30
        self.assertTrue(rift.force_on_expire)
        self.assertEqual(rift.force_door_type, "EVENT")
        self.assertIn("puppet_arc_active", rift.required_flags)
        self.assertIn("puppet_side_minion_once", story.pending_consequences)
        self.assertIn("puppet_side_signal_once", story.pending_consequences)

    def test_puppet_chain_can_force_signal_event_after_minion_defeat(self):
        story = self.controller.story
        self.controller.round_count = 10
        PuppetAbandonmentEvent(self.controller).resolve_choice(0)

        self.controller.round_count = 11
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            minion_door = story.apply_pre_enter_checks(event_door)
        self.assertEqual(minion_door.enum.name, "MONSTER")
        self.assertEqual(minion_door.monster.name, "锈蚀追猎偶")
        self.assertIn("puppet_side_minion_once", story.pending_consequences)

        story.resolve_battle_consequence(minion_door.monster, defeated=True)
        self.assertIn("puppet_side_minion_once", story.consumed_consequences)

        self.controller.round_count = 17
        next_event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            forced_event_door = story.apply_pre_enter_checks(next_event_door)
        self.assertEqual(forced_event_door.enum.name, "EVENT")
        self.assertEqual(getattr(forced_event_door, "story_forced_event_key", ""), "puppet_signal_event")

    def test_puppet_rift_schedules_core_in_20_to_30_rounds(self):
        story = self.controller.story
        self.controller.round_count = 20
        PuppetPersonaRiftEvent(self.controller).resolve_choice(0)
        self.assertIn("puppet_mainline_rift_to_puppet_core_descent_event", story.pending_consequences)
        core = story.pending_consequences["puppet_mainline_rift_to_puppet_core_descent_event"]
        self.assertEqual(core.min_round, 40)  # 20 + 20
        self.assertEqual(core.max_round, 50)  # 20 + 30
        self.assertTrue(core.force_on_expire)
        self.assertEqual(core.force_door_type, "EVENT")

    def test_puppet_core_schedules_final_boss_in_20_to_30_rounds(self):
        story = self.controller.story
        self.controller.round_count = 40
        PuppetCoreDescentEvent(self.controller).resolve_choice(0)
        self.assertIn("puppet_mainline_final_boss_gate", story.pending_consequences)
        final_boss = story.pending_consequences["puppet_mainline_final_boss_gate"]
        self.assertEqual(final_boss.min_round, 60)  # 40 + 20
        self.assertEqual(final_boss.max_round, 70)  # 40 + 30
        self.assertTrue(final_boss.force_on_expire)
        self.assertEqual(final_boss.force_door_type, "MONSTER")
        self.assertEqual(final_boss.effect_key, "puppet_dark_boss")

    def test_puppet_kind_echo_choice_can_reduce_evil_value(self):
        story = self.controller.story
        story.puppet_evil_value = 60
        self.controller.round_count = 21
        PuppetKindEchoEvent(self.controller).resolve_choice(0)
        self.assertLess(story.puppet_evil_value, 60)

    def test_puppet_dark_boss_can_be_weakened_by_kind_persona(self):
        story = self.controller.story
        story.choice_flags.update({"puppet_intro_hide", "puppet_signal_soft", "puppet_descent_patch"})
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_final_kind_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 200, "base_atk": 30},
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed.enum.name, "MONSTER")
        self.assertEqual(changed.monster.name, "堕暗机偶·弃线者")
        self.assertLess(changed.monster.hp, 200)
        self.assertLess(changed.monster.atk, 30)
        self.assertTrue(any("夺回控制" in msg for msg in self.controller.messages))

    def test_puppet_dark_boss_can_be_forced_and_strengthened(self):
        story = self.controller.story
        story.choice_flags.update(
            {
                "puppet_intro_blackout",
                "puppet_intro_decoy",
                "puppet_signal_resell",
                "puppet_descent_dark_feed",
            }
        )
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_final_dark_case",
            effect_key="puppet_dark_boss",
            chance=0.0,
            trigger_door_types=["EVENT"],
            max_round=2,
            force_on_expire=True,
            force_door_type="MONSTER",
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 200, "base_atk": 30},
        )
        self.controller.round_count = 2
        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.random", return_value=0.9):
            changed = story.apply_pre_enter_checks(reward_door)

        self.assertEqual(changed.enum.name, "MONSTER")
        self.assertEqual(changed.monster.name, "堕暗机偶·弃线者")
        self.assertGreater(changed.monster.hp, 200)
        self.assertGreater(changed.monster.atk, 30)


    def test_puppet_final_boss_defeat_grants_low_evil_bonus_rewards(self):
        story = self.controller.story
        story.puppet_evil_value = 20
        monster = Monster(name="裂齿·夜魇·堕暗机偶", hp=10, atk=2, tier=2)
        setattr(monster, "story_puppet_final_boss", True)

        gold_before = self.player.gold
        story.resolve_battle_consequence(monster, defeated=True)

        self.assertGreaterEqual(self.player.gold - gold_before, 90)
        self.assertTrue(any("你获得额外" in msg for msg in self.controller.messages))
        self.assertTrue(any("晨光" in msg or "拽了回来" in msg for msg in self.controller.messages))

    def test_puppet_final_boss_ending_contains_kind_persona_farewell_when_choices_are_kind(self):
        story = self.controller.story
        story.puppet_evil_value = 22
        story.choice_flags.update({"puppet_descent_patch", "puppet_rift_kind", "puppet_signal_soft"})
        monster = Monster(name="裂齿·夜魇·堕暗机偶", hp=10, atk=2, tier=2)
        setattr(monster, "story_puppet_final_boss", True)

        story.resolve_battle_consequence(monster, defeated=True)

        ending_logs = "\n".join(self.controller.messages)
        self.assertIn("善良人格在消散前留下一句", ending_logs)
        self.assertIn("最后的人类样本", ending_logs)

    def test_puppet_final_boss_defeat_high_evil_has_lower_reward(self):
        story = self.controller.story
        story.puppet_evil_value = 90
        story.choice_flags.update({"puppet_intro_blackout", "puppet_intro_decoy", "puppet_signal_resell", "puppet_rift_dark", "puppet_descent_dark_feed"})
        monster = Monster(name="裂齿·夜魇·堕暗机偶", hp=10, atk=2, tier=2)
        setattr(monster, "story_puppet_final_boss", True)

        gold_before = self.player.gold
        story.resolve_battle_consequence(monster, defeated=True)

        self.assertLessEqual(self.player.gold - gold_before, 18)
        self.assertTrue(any("暗噪" in msg or "你虽然赢了" in msg for msg in self.controller.messages))

    def test_puppet_final_boss_no_script_writes_params_no_immediate_clear(self):
        """击败木偶且未拿剧本时只写终局参数，不立即触发结局。"""
        story = self.controller.story
        story.puppet_evil_value = 30
        monster = Monster(name="裂齿·夜魇·堕暗机偶", hp=10, atk=2, tier=2)
        setattr(monster, "story_puppet_final_boss", True)

        story.resolve_battle_consequence(monster, defeated=True)

        self.assertIsNone(getattr(self.controller, "game_clear_info", None))
        self.assertIn("ending:puppet_final_defeated", story.story_tags)

    def test_impromptu_curtain_call_triggered_when_finale_reads_params_low_evil(self):
        """终局事件读取参数时：已击败木偶且未拿剧本、邪恶值低 → 即兴谢幕，善良人格鼓励。"""
        story = self.controller.story
        story.story_tags.add("ending:puppet_final_defeated")
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 30
        self.assertNotIn("curtain_call_script_recovered", story.story_tags)
        self.assertNotIn("curtain_call_script_recovered", story.choice_flags)

        score_payload = _collect_stage_curtain_scores(story)
        self.assertTrue(score_payload.get("puppet_final_defeated"))
        self.assertFalse(score_payload.get("script_recovered"))
        ending_payload = _resolve_stage_curtain_outcome("freedom", score_payload)

        self.assertEqual(ending_payload.get("ending_key"), "impromptu_curtain_call")
        self.assertEqual(ending_payload.get("ending_title"), "即兴谢幕")
        desc = ending_payload.get("ending_description", "")
        self.assertIn("没有剧本也没关系", desc)
        self.assertIn("你早就比任何台词都更像主角", desc)
        self.assertIn("即兴完成最后一幕", desc)
        self.assertIn("谢幕", desc)

    def test_impromptu_curtain_call_triggered_when_finale_reads_params_high_evil(self):
        """终局事件读取参数时：已击败木偶且未拿剧本、邪恶值高 → 即兴谢幕，黑暗侧嘲讽。"""
        story = self.controller.story
        story.story_tags.add("ending:puppet_final_defeated")
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 70

        score_payload = _collect_stage_curtain_scores(story)
        ending_payload = _resolve_stage_curtain_outcome("freedom", score_payload)

        self.assertEqual(ending_payload.get("ending_key"), "impromptu_curtain_call")
        desc = ending_payload.get("ending_description", "")
        self.assertIn("不过是顶替我的替身罢了", desc)
        self.assertIn("即兴完成最后一幕", desc)

    def test_puppet_final_boss_with_script_no_impromptu_on_finale_read(self):
        """已拿剧本时终局事件读取参数不解析为即兴谢幕，走正常路线。"""
        story = self.controller.story
        story.story_tags.add("ending:puppet_final_defeated")
        story.story_tags.add("curtain_call_script_recovered")
        story.choice_flags.add("curtain_call_script_recovered")
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 30

        score_payload = _collect_stage_curtain_scores(story)
        self.assertTrue(score_payload.get("script_recovered"))
        ending_payload = _resolve_stage_curtain_outcome("freedom", score_payload)

        self.assertEqual(ending_payload.get("ending_key"), "stage_curtain_freedom")

    def test_puppet_final_boss_escape_records_meta_for_later_final_ending(self):
        story = self.controller.story
        puppet_boss = Monster(name="裂齿·夜魇·堕暗机偶", hp=10, atk=2, tier=2)
        setattr(puppet_boss, "story_puppet_final_boss", True)

        story.resolve_battle_consequence(puppet_boss, defeated=False)

        self.assertIn("ending:puppet_final_escape_recorded", story.story_tags)
        self.assertEqual(getattr(story, "puppet_final_outcome", ""), "escaped")
        self.assertEqual(getattr(story, "puppet_patrol_state", ""), "active")
        self.assertIn("走廊中来回游荡", getattr(story, "puppet_patrol_note", ""))
        self.assertIsNone(getattr(self.controller, "game_clear_info", None))

        default_boss = Monster(name="选择困难症候群", hp=10, atk=2, tier=4)
        setattr(default_boss, "story_default_final_boss", True)
        story.resolve_battle_consequence(default_boss, defeated=True)

        clear_info = getattr(self.controller, "game_clear_info", {})
        self.assertEqual(clear_info.get("ending_key"), "default_normal")
        ending_meta = clear_info.get("ending_meta", {})
        self.assertEqual(ending_meta.get("puppet_final_outcome"), "escaped")
        self.assertEqual(ending_meta.get("puppet_patrol_state"), "active")
        self.assertIn("走廊中来回游荡", ending_meta.get("puppet_patrol_note", ""))
        self.assertTrue(any("抽身撤离" in msg or "最后一瞬" in msg for msg in self.controller.messages))

    def test_puppet_dark_boss_gets_direct_modifier_from_signal_soft(self):
        story = self.controller.story
        story.choice_flags.add("puppet_signal_soft")
        story.story_tags.add("consumed:puppet_side_signal_once")
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_direct_signal_soft_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 200, "base_atk": 30, "evil_value": 55},
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)

        self.assertLess(changed.monster.hp, 200)
        self.assertLess(changed.monster.atk, 30)
        self.assertTrue(any("温和语音样本" in msg or "温和样本" in msg for msg in self.controller.messages))

    def test_puppet_dark_boss_can_transform_to_dark_complete_form(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_phase_two_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={
                "boss_name": "堕暗机偶·弃线者",
                "phase2_name": "裂齿·夜魇·黑暗完全体",
                "base_hp": 200,
                "base_atk": 30,
                "phase2_min_hp_ratio": 0.62,
                "evil_value": 55,
            },
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)

        monster = changed.monster
        self.controller.current_battle_extensions = getattr(changed, "battle_extensions", [])
        monster.hp = 1
        with unittest.mock.patch("models.player.random.randint", return_value=0), unittest.mock.patch(
            "models.story_system.random.uniform", return_value=0.1
        ), unittest.mock.patch("models.story_system.random.random", return_value=0.9):
            defeated = self.player.attack(monster)

        self.assertGreater(len(self.controller.current_battle_extensions), 0, "expected one battle extension")
        state = self.controller.current_battle_extensions[0]["state"]
        self.assertFalse(defeated)
        self.assertEqual(monster.name, "裂齿·夜魇·黑暗完全体")
        self.assertEqual(state.get("phase"), 2)
        self.assertGreater(monster.hp, 0)
        self.assertGreaterEqual(monster.hp, int(round(state.get("phase1_max_hp", 1) * state.get("phase2_min_hp_ratio", 0.0))))
        self.assertTrue(any("完全体" in msg or "战斗主题开始" in msg for msg in self.controller.messages))

    def test_puppet_dark_boss_applies_shop_side_buff_when_entering_phase_two(self):
        story = self.controller.story
        story.story_tags.add("consumed:puppet_side_shop_once")
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_direct_shop_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 200, "base_atk": 30, "evil_value": 55},
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)
        monster = changed.monster
        self.controller.current_battle_extensions = getattr(changed, "battle_extensions", [])
        atk_before = monster.atk
        monster.hp = 1
        with unittest.mock.patch("models.player.random.randint", return_value=0), unittest.mock.patch(
            "models.story_system.random.uniform", return_value=0.1
        ), unittest.mock.patch("models.story_system.random.random", return_value=0.9):
            defeated = self.player.attack(monster)

        self.assertGreater(len(self.controller.current_battle_extensions), 0, "expected one battle extension")
        state = self.controller.current_battle_extensions[0]["state"]
        self.assertFalse(defeated)
        self.assertEqual(state.get("phase"), 2)
        self.assertGreater(monster.atk, atk_before)
        self.assertTrue(any("补了装甲片" in msg for msg in self.controller.messages))

    def test_puppet_dark_boss_runtime_modifier_can_trigger_multiple_times(self):
        story = self.controller.story
        story.story_tags.add("consumed:puppet_side_reward_once")
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_direct_reward_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 200, "base_atk": 30, "evil_value": 55},
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)
        monster = changed.monster
        self.controller.current_battle_extensions = getattr(changed, "battle_extensions", [])
        monster.hp = 1200

        with unittest.mock.patch("models.player.random.randint", return_value=0), unittest.mock.patch(
            "models.story_system.random.uniform", return_value=0.1
        ), unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            self.player.attack(monster)
            self.player.attack(monster)

        self.assertGreater(len(self.controller.current_battle_extensions), 0, "expected one battle extension")
        trigger_counts = self.controller.current_battle_extensions[0]["state"].get("runtime_trigger_counts", {})
        self.assertGreaterEqual(trigger_counts.get("consumed:puppet_side_reward_once:player_attack", 0), 2)
        self.assertTrue(any("结界" in msg for msg in self.controller.messages))

    def test_puppet_dark_boss_incoming_damage_modifier_works_in_both_phases(self):
        story = self.controller.story
        story.story_tags.add("consumed:puppet_side_reward_once")
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_incoming_both_phase_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 220, "base_atk": 30, "evil_value": 55},
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)
        monster = changed.monster
        self.controller.current_battle_extensions = getattr(changed, "battle_extensions", [])
        self.assertGreater(len(self.controller.current_battle_extensions), 0, "expected one battle extension")
        extension = self.controller.current_battle_extensions[0]

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.0
        ):
            phase1_dmg = story.apply_battle_extension(
                extension=extension,
                trigger="monster_attack",
                attacker=monster,
                defender=self.player,
                damage=100,
            )
        self.assertLess(phase1_dmg, 100)

        monster.hp = 1
        self.controller.on_player_attack_resolved(monster)
        self.assertEqual(extension["state"].get("phase"), 2)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.0
        ):
            phase2_dmg = story.apply_battle_extension(
                extension=extension,
                trigger="monster_attack",
                attacker=monster,
                defender=self.player,
                damage=100,
            )
        self.assertLess(phase2_dmg, 100)

    def test_puppet_signal_resell_incoming_damage_bonus_works_in_both_phases(self):
        story = self.controller.story
        story.choice_flags.add("puppet_signal_resell")
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_signal_resell_both_phase_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 220, "base_atk": 30, "evil_value": 55},
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)
        monster = changed.monster
        self.controller.current_battle_extensions = getattr(changed, "battle_extensions", [])
        self.assertGreater(len(self.controller.current_battle_extensions), 0, "expected one battle extension")
        extension = self.controller.current_battle_extensions[0]

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.0
        ):
            phase1_dmg = story.apply_battle_extension(
                extension=extension,
                trigger="monster_attack",
                attacker=monster,
                defender=self.player,
                damage=100,
            )
        self.assertGreater(phase1_dmg, 100)

        monster.hp = 1
        self.controller.on_player_attack_resolved(monster)
        self.assertEqual(extension["state"].get("phase"), 2)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.1), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.0
        ):
            phase2_dmg = story.apply_battle_extension(
                extension=extension,
                trigger="monster_attack",
                attacker=monster,
                defender=self.player,
                damage=100,
            )
        self.assertGreater(phase2_dmg, 100)

    def test_puppet_dark_boss_has_fallback_message_when_no_side_event_happened(self):
        story = self.controller.story
        story.register_consequence(
            choice_flag="puppet_test",
            consequence_id="puppet_direct_no_side_case",
            effect_key="puppet_dark_boss",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"boss_name": "堕暗机偶·弃线者", "base_hp": 200, "base_atk": 30, "evil_value": 55},
        )
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=20, atk=4, tier=1),
        )
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            story.apply_pre_enter_checks(monster_door)

        self.assertTrue(any("核心读数" in msg for msg in self.controller.messages))

    def test_revenge_ambush_on_monster_door_can_buff_existing_monster(self):
        story = self.controller.story
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=30, atk=6, tier=1),
        )
        story.register_consequence(
            choice_flag="monster_revenge_case",
            consequence_id="monster_revenge_buff",
            effect_key="revenge_ambush",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"force_hunter": False, "hp_ratio": 1.5, "atk_ratio": 1.4},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed_door.enum.name, "MONSTER")
        self.assertEqual(changed_door.monster.name, "史莱姆")
        self.assertEqual(changed_door.monster.hp, 45)
        self.assertEqual(changed_door.monster.atk, 8)

    def test_revenge_ambush_on_monster_door_can_replace_monster(self):
        story = self.controller.story
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=30, atk=6, tier=1),
        )
        story.register_consequence(
            choice_flag="monster_revenge_case",
            consequence_id="monster_revenge_replace",
            effect_key="revenge_ambush",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"hp_ratio": 1.5, "atk_ratio": 1.4},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed_door.enum.name, "MONSTER")
        self.assertNotEqual(changed_door.monster.name, "史莱姆")
        self.assertIn("monster_revenge_replace", story.consumed_consequences)

    def test_revenge_ambush_uses_event_matched_hunter_profile(self):
        story = self.controller.story
        monster_door = DoorEnum.MONSTER.create_instance(
            controller=self.controller,
            monster=Monster(name="史莱姆", hp=30, atk=6, tier=1),
        )
        story.register_consequence(
            choice_flag="caravan_case",
            consequence_id="caravan_donate_bandit_envy",
            effect_key="revenge_ambush",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"hp_ratio": 1.1, "atk_ratio": 1.1},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed_door.enum.name, "MONSTER")
        self.assertEqual(changed_door.monster.name, "劫道匪徒")
        self.assertTrue(any("援助车队惹怒了劫匪" in msg for msg in self.controller.messages))

    def test_shop_discount_persists_to_next_shop_refresh(self):
        story = self.controller.story
        self.player.gold = 100
        shop = self.controller.current_shop

        random.seed(20260309)
        shop.generate_items()
        baseline_costs = [item.cost for item in shop.shop_items]

        story.register_consequence(
            choice_flag="discount_refresh_case",
            consequence_id="discount_refresh_once",
            effect_key="black_market_discount",
            chance=1.0,
            trigger_door_types=["SHOP"],
            payload={"ratio": 0.5},
        )
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)

        random.seed(20260309)
        shop.generate_items()
        refreshed_discount_costs = [item.cost for item in shop.shop_items]

        self.assertTrue(all(new <= old for new, old in zip(refreshed_discount_costs, baseline_costs)))
        self.assertTrue(any(new < old for new, old in zip(refreshed_discount_costs, baseline_costs)))
        self.assertEqual(shop.pending_price_ratio, 1.0)


    def test_event_door_prefers_force_story_event_when_many_candidates(self):
        story = self.controller.story
        for i in range(4):
            story.register_consequence(
                choice_flag=f"bulk_{i}",
                consequence_id=f"bulk_reward_{i}",
                effect_key="guard_reward",
                chance=1.0,
                trigger_door_types=["EVENT"],
                priority=99,
                payload={"gold": 1},
            )

        story.register_consequence(
            choice_flag="bulk_force",
            consequence_id="bulk_force_event",
            effect_key="force_story_event",
            chance=1.0,
            trigger_door_types=["EVENT"],
            priority=1,
            payload={"event_key": "moon_verdict_event"},
        )

        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        # 5 条候选权重 [1,1,1,1,2]；roll=5.0 落在最后一条（force_story_event）区间 [4,6)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=5.0):
            changed_door = story.apply_pre_enter_checks(event_door)

        self.assertEqual(getattr(changed_door, "story_forced_event_key", ""), "moon_verdict_event")

    def test_elf_side_merchant_rewrite_keeps_shop_door_type(self):
        story = self.controller.story
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        story.register_consequence(
            choice_flag="elf_side_reg",
            consequence_id="elf_side_merchant_disguised_once",
            effect_key="replace_with_elf_side_event",
            chance=1.0,
            trigger_door_types=["SHOP"],
            payload={"event_key": "elf_side_merchant_disguised_event", "chance": 1.0},
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.0
        ):
            changed_door = story.apply_pre_enter_checks(shop_door)

        self.assertEqual(changed_door.enum.name, "SHOP")
        self.assertEqual(getattr(changed_door, "story_forced_event_key", ""), "elf_side_merchant_disguised_event")

    def test_shop_door_can_jump_to_forced_story_event(self):
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        shop_door.story_forced_event_key = "elf_side_merchant_disguised_event"

        entered = shop_door.enter()

        self.assertTrue(entered)
        self.assertEqual(self.controller.scene_manager.current_scene.enum.name, "EVENT")
        self.assertIsInstance(self.controller.current_event, ElfSideMerchantDisguisedEvent)

    def test_trigger_message_is_not_logged_when_effect_not_applied(self):
        story = self.controller.story
        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        story.register_consequence(
            choice_flag="elf_side_reg",
            consequence_id="elf_side_merchant_disguised_once",
            effect_key="replace_with_elf_side_event",
            chance=1.0,
            trigger_door_types=["SHOP"],
            payload={
                "event_key": "elf_side_merchant_disguised_event",
                "chance": 0.0,
                "message": "柜台后的商人懒洋洋的看着你——那眼神你认得，这是莱希娅。",
            },
        )

        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(shop_door)

        self.assertEqual(changed_door.enum.name, "SHOP")
        self.assertEqual(getattr(changed_door, "story_forced_event_key", ""), "")
        self.assertNotIn("柜台后的商人懒洋洋的看着你——那眼神你认得，这是莱希娅。", self.controller.messages)

    def test_elf_positive_reward_can_be_heal_instead_of_atk(self):
        self.player.hp = 40
        base_atk = self.player._atk
        event = ElfRooftopDuelEvent(self.controller)

        with unittest.mock.patch("models.events.random.random", return_value=0.5):
            event.train_hard()

        self.assertGreater(self.player.hp, 40)
        self.assertEqual(self.player._atk, base_atk)

    def test_elf_positive_reward_can_be_item_instead_of_atk(self):
        event = ElfRooftopDuelEvent(self.controller)
        before_items = self.player.get_inventory_size()

        with unittest.mock.patch("models.events.random.random", return_value=0.95), unittest.mock.patch(
            "models.events.create_reward_door_item", return_value=FlyingHammer("飞锤", cost=0, duration=3)
        ):
            event.train_hard()

        self.assertGreater(self.player.get_inventory_size(), before_items)
        self.assertTrue(any("飞锤" in msg for msg in self.controller.messages))

    def test_stage_curtain_preface_is_scheduled_in_pre_final_window_with_reward_gate_only(self):
        self.controller.round_count = 185
        story = self.controller.story
        story.elf_chain_ended = True
        story.elf_relation = 3
        story.elf_key_obtained = True
        story.story_tags.add("ending:puppet_final_defeated")
        story.puppet_evil_value = 30

        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_stage_curtain_preface", story.pending_consequences)
        pending = story.pending_consequences["ending_stage_curtain_preface"]
        self.assertEqual(pending.min_round, 185)
        self.assertEqual(pending.max_round, 200)
        self.assertFalse(pending.force_on_expire)
        self.assertEqual(pending.trigger_door_types, {"REWARD"})

        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        unchanged = story.apply_pre_enter_checks(event_door)
        self.assertEqual(unchanged.enum.name, "EVENT")

        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller)
        changed_door = story.apply_pre_enter_checks(reward_door)
        self.assertEqual(changed_door.enum.name, "REWARD")
        extension_types = [ext.get("extension_type") for ext in getattr(changed_door, "door_extensions", [])]
        self.assertIn("stage_curtain_script_vault", extension_types)

    def test_stage_curtain_preface_is_not_forced_by_max_round(self):
        """结局前事件不做 max_round 强制替换；到 200 回合由「保证对应门型出现」按序触发，选错门不改写。"""
        self.controller.round_count = 185
        story = self.controller.story
        story.elf_chain_ended = True
        story.elf_relation = 3
        story.elf_key_obtained = True
        story.story_tags.add("ending:puppet_final_defeated")
        story.puppet_evil_value = 30
        story.ensure_default_normal_ending_schedule()

        for round_count in (185, 190, 191, 200):
            self.controller.round_count = round_count
            trap_door = DoorEnum.TRAP.create_instance(controller=self.controller)
            unchanged = story.apply_pre_enter_checks(trap_door)
            self.assertEqual(unchanged.enum.name, "TRAP")

    def test_stage_script_vault_marks_script_truth_no_longer_schedules_curtain_gate(self):
        """取回剧本后不再在窗口内挂载谢幕门；与善良木偶对话结局门改在第 200 回合、倒数窗口清空后挂载。"""
        story = self.controller.story
        story.story_tags.add("moon_bounty_diary_obtained")
        story.moon_bounty_diary_source = "thief_testimony"

        run_script_vault_recovery(self.controller)

        self.assertIn("curtain_call_script_recovered", story.story_tags)
        self.assertIn("curtain_call_truth_revealed", story.story_tags)
        self.assertNotIn("ending_stage_curtain_gate", story.pending_consequences)
        self.assertTrue(any("被冤枉" in msg for msg in self.controller.messages))

    def test_stage_curtain_gate_can_trigger_order_ending_clear(self):
        story = self.controller.story
        story.story_tags.update(
            {
                "elf_outcome:alliance",
                "ending:puppet_final_defeated",
                "elf_key_obtained",
                "curtain_call_script_recovered",
            }
        )
        story.choice_flags.update(
            {
                "moon_verdict_clean",
                "clockwork_calibrated",
                "dream_well_sealed",
                "echo_court_redeemed",
            }
        )
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 20
        story.moon_bounty_diary_source = "thief_testimony"

        event = EndingStageCurtainGateEvent(self.controller)
        event.resolve_choice(0)

        clear_info = getattr(self.controller, "game_clear_info", {})
        self.assertEqual(clear_info.get("ending_key"), "stage_curtain_order")
        self.assertIn("ending:stage_curtain_completed", story.story_tags)
        self.assertEqual(clear_info.get("ending_meta", {}).get("stage_outcome"), "order")
        self.assertTrue(clear_info.get("ending_meta", {}).get("puppet_kind_rescued"))
        self.assertTrue(clear_info.get("ending_meta", {}).get("stage_script_ready"))
        self.assertIn("最后一幕", clear_info.get("ending_description", ""))
        self.assertTrue(any("跑上前台" in msg for msg in self.controller.messages))

    def test_stage_curtain_order_route_still_succeeds_when_puppet_kind_persona_not_rescued(self):
        """选补全谢幕时即使善良人格未救回仍为补全结局，仅文案不同。"""
        story = self.controller.story
        story.story_tags.update({"elf_outcome:alliance", "elf_key_obtained", "curtain_call_script_recovered"})
        story.choice_flags.update(
            {
                "moon_verdict_clean",
                "clockwork_calibrated",
                "dream_well_sealed",
                "echo_court_redeemed",
            }
        )
        story.moon_bounty_diary_source = "thief_testimony"

        event = EndingStageCurtainGateEvent(self.controller)
        event.resolve_choice(0)

        clear_info = getattr(self.controller, "game_clear_info", {})
        self.assertEqual(clear_info.get("ending_key"), "stage_curtain_order")
        self.assertEqual(clear_info.get("ending_meta", {}).get("stage_outcome"), "order")
        self.assertIn("善良人格尚未归位", clear_info.get("ending_description", ""))

    def test_default_ending_is_forced_on_round_200_when_no_long_branch_started(self):
        self.controller.round_count = 200
        story = self.controller.story

        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled)
        self.assertIn("ending_default_force_gate_round_200", story.pending_consequences)

        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller)
        changed_door = story.apply_pre_enter_checks(reward_door)
        self.assertEqual(changed_door.enum.name, "EVENT")
        self.assertEqual(getattr(changed_door, "story_forced_event_key", ""), "ending_final_first_gate_event")

    def test_default_ending_is_blocked_until_all_pre_final_events_are_resolved(self):
        self.controller.round_count = 185
        story = self.controller.story
        story.story_tags.update({"ending:puppet_final_escape_recorded"})
        story.puppet_final_outcome = "escaped"
        story.elf_chain_ended = True
        story.elf_relation = -5
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_puppet_pre_final_rematch_gate", story.pending_consequences)
        self.assertIn("ending_elf_rival_final_gate", story.pending_consequences)

        self.controller.round_count = 200
        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertFalse(scheduled)
        self.assertNotIn("ending_default_force_gate_round_200", story.pending_consequences)

        # 不强制替换门：选到对应门型才触发；模拟玩家选到保证出现的 MONSTER 门
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        triggered_first = story.apply_pre_enter_checks(monster_door)
        self.assertEqual(triggered_first.enum.name, "MONSTER")
        self.assertEqual(triggered_first.monster.name, "裂齿·夜魇·游荡残响")
        story.resolve_battle_consequence(triggered_first.monster, defeated=True)

        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        triggered_second = story.apply_pre_enter_checks(monster_door)
        self.assertEqual(triggered_second.enum.name, "MONSTER")
        self.assertEqual(triggered_second.monster.name, "银羽飞贼·莱希娅")
        story.resolve_battle_consequence(triggered_second.monster, defeated=True)

        scheduled_after = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled_after)
        self.assertIn("ending_default_force_gate_round_200", story.pending_consequences)

    def test_default_ending_is_not_scheduled_after_any_long_branch_started(self):
        self.controller.round_count = 200
        self.controller.event_trigger_counts["MoonBountyEvent"] = 1
        story = self.controller.story

        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertFalse(scheduled)
        self.assertNotIn("ending_default_force_gate_round_200", story.pending_consequences)

    def test_default_ending_two_gate_events_can_chain_to_final_boss(self):
        story = self.controller.story
        first_event = EndingFinalFirstGateEvent(self.controller)
        first_event.resolve_choice(1)
        self.assertIn("ending_default_second_gate", story.pending_consequences)

        self.controller.round_count = 201
        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        forced_second = story.apply_pre_enter_checks(event_door)
        self.assertEqual(forced_second.enum.name, "EVENT")
        self.assertEqual(getattr(forced_second, "story_forced_event_key", ""), "ending_final_second_gate_event")

        second_event = EndingFinalSecondGateEvent(self.controller)
        second_event.resolve_choice(2)
        self.assertIn("ending_default_final_boss_gate", story.pending_consequences)

        self.controller.round_count = 202
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        triggered_boss = story.apply_pre_enter_checks(monster_door)
        self.assertEqual(triggered_boss.enum.name, "MONSTER")
        self.assertEqual(triggered_boss.monster.name, "选择困难症候群")
        self.assertTrue(getattr(triggered_boss.monster, "story_default_final_boss", False))

    def test_pre_final_window_schedules_puppet_rematch_and_uses_monster_gate(self):
        story = self.controller.story
        story.story_tags.add("ending:puppet_final_escape_recorded")
        story.puppet_final_outcome = "escaped"
        self.controller.round_count = 185

        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_puppet_pre_final_rematch_gate", story.pending_consequences)
        pending = story.pending_consequences["ending_puppet_pre_final_rematch_gate"]
        self.assertEqual(pending.min_round, 185)
        self.assertEqual(pending.max_round, 200)
        self.assertFalse(pending.force_on_expire)
        self.assertEqual(pending.trigger_door_types, {"MONSTER"})

        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        forced_rematch = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(forced_rematch.enum.name, "MONSTER")
        self.assertEqual(forced_rematch.monster.name, "裂齿·夜魇·游荡残响")
        self.assertFalse(getattr(forced_rematch.monster, "story_puppet_final_boss", False))
        self.assertTrue(getattr(forced_rematch.monster, "story_pre_final_dispatch", False))
        self.assertTrue(any(token in (forced_rematch.hint or "") for token in ("红噪", "失真", "童谣")))

    def test_pre_final_window_forces_rematch_before_final_when_no_monster_gate_hit(self):
        """结局前事件不强制替换门；选错门保持原样，选到 MONSTER 才触发木偶补战。"""
        story = self.controller.story
        story.story_tags.add("ending:puppet_final_escape_recorded")
        story.puppet_final_outcome = "escaped"

        self.controller.round_count = 185
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_puppet_pre_final_rematch_gate", story.pending_consequences)

        for round_count in (185, 191, 200):
            self.controller.round_count = round_count
            trap_door = DoorEnum.TRAP.create_instance(controller=self.controller)
            unchanged = story.apply_pre_enter_checks(trap_door)
            self.assertEqual(unchanged.enum.name, "TRAP")

        self.controller.round_count = 191
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        triggered_rematch = story.apply_pre_enter_checks(monster_door)
        self.assertEqual(triggered_rematch.enum.name, "MONSTER")
        self.assertEqual(triggered_rematch.monster.name, "裂齿·夜魇·游荡残响")

    def test_puppet_rematch_then_elf_rival_can_chain_dispatch_without_early_default_boss(self):
        story = self.controller.story
        story.story_tags.update({"ending:puppet_final_escape_recorded"})
        story.puppet_final_outcome = "escaped"
        story.elf_chain_ended = True
        story.elf_relation = -5
        self.controller.round_count = 185
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_puppet_pre_final_rematch_gate", story.pending_consequences)
        self.assertIn("ending_elf_rival_final_gate", story.pending_consequences)

        self.controller.round_count = 191
        reward_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        forced_rematch = story.apply_pre_enter_checks(reward_door)
        self.assertEqual(forced_rematch.monster.name, "裂齿·夜魇·游荡残响")
        story.resolve_battle_consequence(forced_rematch.monster, defeated=True)
        self.assertIn("ending_elf_rival_final_gate", story.pending_consequences)

        self.controller.round_count = 192
        event_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        forced_rival = story.apply_pre_enter_checks(event_door)
        story.resolve_battle_consequence(forced_rival.monster, defeated=True)
        self.assertNotIn("ending_default_final_boss_gate", story.pending_consequences)

    def test_puppet_escape_record_can_schedule_pre_final_rematch_without_auto_default_boss(self):
        story = self.controller.story
        story.story_tags.update({"ending:puppet_final_escape_recorded"})
        story.puppet_final_outcome = "escaped"
        self.controller.round_count = 185
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_puppet_pre_final_rematch_gate", story.pending_consequences)

        self.controller.round_count = 186
        shop_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        forced_rematch = story.apply_pre_enter_checks(shop_door)
        story.resolve_battle_consequence(forced_rematch.monster, defeated=False)
        self.assertNotIn("ending_default_final_boss_gate", story.pending_consequences)

    def test_hostile_elf_chain_inserts_rival_gate_in_pre_final_window(self):
        story = self.controller.story
        story.elf_chain_ended = True
        story.elf_relation = -5
        self.controller.round_count = 185
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_elf_rival_final_gate", story.pending_consequences)

    def test_pre_final_window_rechecks_every_five_rounds_for_newly_eligible_events(self):
        story = self.controller.story
        story.story_tags.add("ending:puppet_final_escape_recorded")
        story.puppet_final_outcome = "escaped"
        self.controller.round_count = 185
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_puppet_pre_final_rematch_gate", story.pending_consequences)
        self.assertNotIn("ending_elf_rival_final_gate", story.pending_consequences)

        # 在倒数窗口中途才满足飞贼敌对条件；非 5 回合检查点时不应立即挂载
        self.controller.round_count = 187
        story.elf_chain_ended = True
        story.elf_relation = -5
        story.ensure_default_normal_ending_schedule()
        self.assertNotIn("ending_elf_rival_final_gate", story.pending_consequences)

        # 到达 5 回合检查点后重新评估并纳入窗口
        self.controller.round_count = 190
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_elf_rival_final_gate", story.pending_consequences)

    def test_pre_final_countdown_pending_events_have_eighty_percent_priority(self):
        story = self.controller.story
        self.controller.round_count = 190

        story.register_consequence(
            choice_flag="pre_final_priority_case",
            consequence_id="ending_elf_rival_final_gate",
            effect_key="force_story_event",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"event_key": "moon_verdict_event"},
        )
        story.register_consequence(
            choice_flag="pre_final_priority_case",
            consequence_id="non_blocking_event",
            effect_key="force_story_event",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"event_key": "moon_bounty_event"},
        )

        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.random", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.uniform", return_value=0.0
        ):
            changed = story.apply_pre_enter_checks(event_door)

        self.assertEqual(getattr(changed, "story_forced_event_key", ""), "moon_verdict_event")
        self.assertIn("ending_elf_rival_final_gate", story.consumed_consequences)
        self.assertIn("non_blocking_event", story.pending_consequences)

    def test_pre_final_countdown_priority_is_not_guaranteed(self):
        story = self.controller.story
        self.controller.round_count = 190

        story.register_consequence(
            choice_flag="pre_final_priority_case",
            consequence_id="ending_elf_rival_final_gate",
            effect_key="force_story_event",
            chance=0.01,
            trigger_door_types=["EVENT"],
            payload={"event_key": "moon_verdict_event"},
        )
        story.register_consequence(
            choice_flag="pre_final_priority_case",
            consequence_id="non_blocking_event",
            effect_key="force_story_event",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"event_key": "moon_bounty_event"},
        )

        event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.random", return_value=0.95), unittest.mock.patch(
            "models.story_system.random.uniform", return_value=1.0
        ):
            changed = story.apply_pre_enter_checks(event_door)

        self.assertEqual(getattr(changed, "story_forced_event_key", ""), "moon_bounty_event")
        self.assertIn("non_blocking_event", story.consumed_consequences)
        self.assertIn("ending_elf_rival_final_gate", story.pending_consequences)

    def test_after_window_all_remaining_pre_final_events_are_forced_sequentially(self):
        # 木偶逃跑 + 飞贼敌对：不满足银羽秘藏前置（需击败木偶且邪恶值≤45），故只挂载木偶补战与飞贼清算
        story = self.controller.story
        story.story_tags.update({"ending:puppet_final_escape_recorded"})
        story.puppet_final_outcome = "escaped"
        story.elf_chain_ended = True
        story.elf_relation = -5
        story.elf_key_obtained = True

        self.controller.round_count = 185
        story.ensure_default_normal_ending_schedule()
        self.assertIn("ending_puppet_pre_final_rematch_gate", story.pending_consequences)
        self.assertIn("ending_elf_rival_final_gate", story.pending_consequences)

        # 不强制替换门；选错门保持 TRAP，选到 MONSTER 时按序触发（先木偶补战，再飞贼清算）
        for round_count in (185, 191):
            self.controller.round_count = round_count
            trap_door = DoorEnum.TRAP.create_instance(controller=self.controller)
            unchanged = story.apply_pre_enter_checks(trap_door)
            self.assertEqual(unchanged.enum.name, "TRAP")

        self.controller.round_count = 191
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        triggered_1 = story.apply_pre_enter_checks(monster_door)
        self.assertEqual(triggered_1.enum.name, "MONSTER")
        self.assertEqual(triggered_1.monster.name, "裂齿·夜魇·游荡残响")
        story.resolve_battle_consequence(triggered_1.monster, defeated=True)

        self.controller.round_count = 192
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller)
        triggered_2 = story.apply_pre_enter_checks(monster_door)
        self.assertEqual(triggered_2.enum.name, "MONSTER")
        self.assertEqual(triggered_2.monster.name, "银羽飞贼·莱希娅")
        story.resolve_battle_consequence(triggered_2.monster, defeated=True)

    def test_elf_rival_final_battle_victory_grants_hint_and_consumes_gate(self):
        story = self.controller.story
        monster = Monster(name="银羽飞贼·莱希娅", hp=12, atk=4, tier=4)
        setattr(monster, "story_elf_rival_final_boss", True)
        setattr(monster, "story_consequence_id", "ending_elf_rival_final_gate")
        setattr(monster, "story_consume_on_defeat", True)
        setattr(monster, "story_elf_rival_hint", "终局门里的第一条提示往往是诱饵。")
        story.register_consequence(
            choice_flag="ending_default_second_gate_rival",
            consequence_id="ending_elf_rival_final_gate",
            effect_key="elf_rival_final_gate",
            chance=1.0,
            trigger_door_types=["MONSTER"],
            payload={"relation": -5},
        )

        story.resolve_battle_consequence(monster, defeated=True)

        self.assertIn("ending:elf_rival_final_victory", story.story_tags)
        self.assertIn("ending_elf_rival_final_victory", story.choice_flags)
        self.assertIn("ending_elf_rival_final_gate", story.consumed_consequences)
        self.assertNotIn("ending_default_final_boss_gate", story.pending_consequences)
        self.assertTrue(any("终局门里" in msg or "诱饵" in msg for msg in self.controller.messages))

    def test_elf_rival_final_battle_escape_marks_permanent_parting(self):
        story = self.controller.story
        monster = Monster(name="银羽飞贼·莱希娅", hp=12, atk=4, tier=4)
        setattr(monster, "story_elf_rival_final_boss", True)

        story.resolve_battle_consequence(monster, defeated=False)

        self.assertIn("ending:elf_rival_parted", story.story_tags)
        self.assertIn("ending_elf_rival_parted", story.choice_flags)
        self.assertTrue(any("下次不用再见" in msg for msg in self.controller.messages))

    def test_elf_rival_grudge_lines_reference_prior_elf_choices(self):
        """清算战中台词按支线记录的冒犯行为依次播放。"""
        from models.story_system import _collect_elf_rival_grudge_barks

        story = self.controller.story
        story.choice_flags.update({"elf_grudge_heist_betrayed", "elf_grudge_map_sold_out"})
        state = {
            "profile": "trickster",
            "extensions": [],
            "shadowstep_boost": [0.24],
            "debuff_turns": [2],
            "debuff_mode": "weak",
            "lines": {"shadowstep": "（身法）", "debuff": "（扰敌）"},
            "grudge_barks": _collect_elf_rival_grudge_barks(story),
            "runtime": {"trigger_counts": {}},
        }
        ext = {"extension_type": "elf_rival_final_boss", "state": state}
        rival = Monster(name="银羽飞贼·莱希娅", hp=10, atk=2, tier=4)
        setattr(rival, "story_elf_rival_final_boss", True)

        self.controller.messages.clear()
        story.handle_battle_extension_post_player_attack(ext, rival)
        blob = "\n".join(self.controller.messages)
        self.assertIn("钟塔", blob)
        self.assertIn("莱希娅", blob)

        story.apply_battle_extension(ext, "monster_attack", rival, self.controller.player, 5)
        blob2 = "\n".join(self.controller.messages)
        self.assertIn("商人", blob2)

    def test_defeating_default_final_boss_triggers_normal_ending_clear(self):
        story = self.controller.story
        monster = Monster(name="选择困难症候群", hp=10, atk=2, tier=4)
        setattr(monster, "story_default_final_boss", True)

        story.resolve_battle_consequence(monster, defeated=True)

        # 通关后先进入结局摘要场景，点击「继续」后进入结局滚动，再点击继续才是 GameOverScene
        self.assertEqual(self.controller.scene_manager.current_scene.enum.name, "ENDING_SUMMARY")
        self.assertEqual(getattr(self.controller, "game_clear_info", {}).get("ending_key"), "default_normal")
        self.controller.scene_manager.current_scene.handle_choice(0)  # 继续 -> 进入结局滚动
        self.assertEqual(self.controller.scene_manager.current_scene.enum.name, "ENDING_ROLL")
        self.controller.scene_manager.current_scene.handle_choice(0)  # 继续
        self.assertEqual(self.controller.scene_manager.current_scene.enum.name, "GAME_OVER")
        self.assertIn("ending:default_normal_completed", story.story_tags)

    # ---------- 结局触发确定性测试：参数满足时对应结局必须能触发 ----------

    def test_ending_default_normal_scheduled_and_triggered_when_no_long_branch(self):
        """无长线分支、回合200、无阻塞时，必须挂载默认第一门，完成两门+Boss 后触发 default_normal。"""
        self.controller.round_count = 200
        story = self.controller.story
        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled, "应挂载默认终局入口")
        self.assertIn("ending_default_force_gate_round_200", story.pending_consequences)
        cfg = story.pending_consequences["ending_default_force_gate_round_200"]
        self.assertEqual(cfg.payload.get("event_key"), "ending_final_first_gate_event")

        first = EndingFinalFirstGateEvent(self.controller)
        first.resolve_choice(1)
        self.assertIn("ending_default_second_gate", story.pending_consequences)
        self.controller.round_count = 201
        second = EndingFinalSecondGateEvent(self.controller)
        second.resolve_choice(2)
        self.assertIn("ending_default_final_boss_gate", story.pending_consequences)
        self.controller.round_count = 202
        monster = Monster("选择困难症候群", hp=10, atk=2, tier=4)
        setattr(monster, "story_default_final_boss", True)
        story.resolve_battle_consequence(monster, defeated=True)
        self.assertEqual(getattr(self.controller, "game_clear_info", {}).get("ending_key"), "default_normal")

    def test_puppet_echo_gate_scheduled_when_puppet_defeated_no_key_elf_not_friendly(self):
        """已击败木偶、未拿钥匙、与飞贼关系普通或不好时，回合200 应挂载木偶回声怪物门。"""
        self.controller.round_count = 200
        story = self.controller.story
        story.story_tags.add("ending:puppet_final_defeated")
        story.story_tags.discard("elf_key_obtained")
        story.elf_key_obtained = False
        story.elf_chain_ended = True
        story.elf_relation = 0
        self.assertTrue(story._is_puppet_echo_gate_ready())
        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled)
        self.assertIn("ending_puppet_echo_final_gate", story.pending_consequences)
        self.assertNotIn("ending_default_force_gate_round_200", story.pending_consequences)

    def test_puppet_echo_defeat_schedules_aftermath_event_then_choices_trigger_endings(self):
        """击败木偶的回声后挂载事件门；前两选为即兴谢幕（文案不同），第三选为选择困难症→进入普通结局主线。"""
        from models.monster import Monster
        from models.events import EndingPuppetEchoAftermathEvent

        story = self.controller.story
        echo = Monster("木偶的回声", hp=10, atk=2, tier=4)
        setattr(echo, "story_puppet_echo_final_boss", True)
        story.resolve_battle_consequence(echo, defeated=True)
        self.assertIsNone(getattr(self.controller, "game_clear_info", None))
        self.assertEqual(getattr(self.controller, "pending_post_battle_event_key", None), "ending_puppet_echo_aftermath_event")

        event = EndingPuppetEchoAftermathEvent(self.controller)
        self.assertEqual(len(event.choices), 3)
        event.resolve_choice(0)
        clear_info = getattr(self.controller, "game_clear_info", {})
        self.assertEqual(clear_info.get("ending_key"), "stage_curtain_freedom")
        self.assertTrue(clear_info.get("ending_meta", {}).get("puppet_echo_final"))
        self.controller.game_clear_info = None
        story.story_tags.discard("ending:stage_curtain_completed")
        event2 = EndingPuppetEchoAftermathEvent(self.controller)
        event2.resolve_choice(1)
        clear_info2 = getattr(self.controller, "game_clear_info", {})
        self.assertEqual(clear_info2.get("ending_key"), "stage_curtain_freedom")
        self.assertIn("即兴", clear_info2.get("ending_description", ""))
        self.controller.game_clear_info = None
        story.story_tags.discard("ending:stage_curtain_completed")
        event3 = EndingPuppetEchoAftermathEvent(self.controller)
        event3.resolve_choice(2)
        # 选择困难症进入普通结局主线：挂载终局第一门，不直接触发结局
        self.assertIsNone(getattr(self.controller, "game_clear_info", None))
        self.assertIn("ending_default_force_gate_round_200", story.pending_consequences)

    def test_ending_stage_curtain_order_triggered_with_order_route_and_puppet_kind_rescued(self):
        """补全路线 + 善良人格已救回 + 秩序/风险达标时，选补全门必触发 stage_curtain_order。"""
        story = self.controller.story
        story.story_tags.update({
            "elf_outcome:alliance", "ending:puppet_final_defeated", "elf_key_obtained",
            "curtain_call_script_recovered",
        })
        story.choice_flags.update({
            "moon_verdict_clean", "clockwork_calibrated", "dream_well_sealed", "echo_court_redeemed",
        })
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 20
        story.moon_bounty_diary_source = "thief_testimony"
        event = EndingStageCurtainGateEvent(self.controller)
        event.resolve_choice(0)
        self.assertEqual(getattr(self.controller, "game_clear_info", {}).get("ending_key"), "stage_curtain_order")

    def test_ending_stage_curtain_freedom_triggered_with_freedom_route_and_scores(self):
        """即兴路线 + freedom>=4, risk<=3 时，选即兴门必触发 stage_curtain_freedom。"""
        story = self.controller.story
        story.story_tags.update({
            "elf_outcome:alliance", "ending:puppet_final_defeated", "elf_key_obtained",
            "curtain_call_script_recovered",
        })
        story.choice_flags.update({
            "moon_verdict_clean", "clockwork_calibrated", "dream_well_sealed", "echo_court_redeemed",
            "dream_well_drank", "puppet_signal_soft", "puppet_kind_echo_trust",
        })
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 30
        story.moon_bounty_diary_source = "thief_testimony"
        payload = _collect_stage_curtain_scores(story)
        self.assertGreaterEqual(payload.get("freedom", 0), 4)
        self.assertLessEqual(payload.get("risk", 10), 3)
        event = EndingStageCurtainGateEvent(self.controller)
        event.resolve_choice(1)
        self.assertEqual(getattr(self.controller, "game_clear_info", {}).get("ending_key"), "stage_curtain_freedom")

    def test_ending_stage_curtain_power_triggered_with_power_route_and_scores(self):
        """接管路线 + power>=4, risk<=4 时，选接管门必触发 stage_curtain_power。"""
        story = self.controller.story
        story.story_tags.update({
            "ending:puppet_final_defeated", "elf_key_obtained", "curtain_call_script_recovered",
        })
        story.choice_flags.update({
            "moon_verdict_extorted", "clockwork_hacked", "dream_well_sold", "mirror_played_villain",
        })
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 50
        payload = _collect_stage_curtain_scores(story)
        self.assertGreaterEqual(payload.get("power", 0), 4)
        self.assertLessEqual(payload.get("risk", 10), 4)
        event = EndingStageCurtainGateEvent(self.controller)
        event.resolve_choice(2)
        self.assertEqual(getattr(self.controller, "game_clear_info", {}).get("ending_key"), "stage_curtain_power")

    def test_kind_puppet_dialogue_round200_mounted_when_script_and_puppet_low_evil(self):
        """第 200 回合、倒数窗口清空后，若已取回剧本+击败木偶+邪恶值低（且有钥匙，否则走木偶回声门），挂载与善良木偶对话结局门。"""
        self.controller.round_count = 200
        story = self.controller.story
        story.story_tags.add("curtain_call_script_recovered")
        story.story_tags.add("ending:puppet_final_defeated")
        story.story_tags.add("elf_key_obtained")
        story.elf_key_obtained = True
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 30
        self.assertTrue(story._is_kind_puppet_dialogue_ready())
        self.assertFalse(story._is_puppet_echo_gate_ready())
        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled)
        self.assertIn("ending_kind_puppet_dialogue_round200", story.pending_consequences)
        self.assertNotIn("ending_default_force_gate_round_200", story.pending_consequences)

    def test_kind_puppet_dialogue_three_choices_trigger_three_endings(self):
        """与善良木偶对话事件门三选一：0=补全，1=即兴，2=选择困难症（进入普通结局主线第一门）。"""
        story = self.controller.story
        story.story_tags.update({
            "elf_outcome:alliance", "ending:puppet_final_defeated", "elf_key_obtained",
            "curtain_call_script_recovered",
        })
        story.choice_flags.update({
            "moon_verdict_clean", "clockwork_calibrated", "dream_well_sealed", "echo_court_redeemed",
        })
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 20
        story.moon_bounty_diary_source = "thief_testimony"
        event = EndingStageKindPuppetDialogueEvent(self.controller)
        self.assertEqual(len(event.choices), 3)
        event.resolve_choice(0)
        self.assertEqual(getattr(self.controller, "game_clear_info", {}).get("ending_key"), "stage_curtain_order")
        self.controller.game_clear_info = None
        event2 = EndingStageKindPuppetDialogueEvent(self.controller)
        event2.resolve_choice(1)
        self.assertEqual(getattr(self.controller, "game_clear_info", {}).get("ending_key"), "stage_curtain_freedom")
        self.controller.game_clear_info = None
        story.story_tags.discard("ending:stage_curtain_completed")
        event3 = EndingStageKindPuppetDialogueEvent(self.controller)
        event3.resolve_choice(2)
        # 选择困难症进入普通结局主线：挂载终局第一门，不直接触发结局
        self.assertIsNone(getattr(self.controller, "game_clear_info", None))
        self.assertIn("ending_default_force_gate_round_200", story.pending_consequences)

    def test_kind_and_power_curtain_dialogue_are_mutually_exclusive_by_evil(self):
        """与善良木偶对话（邪恶值≤45）与接管谢幕选择门（邪恶值>45）互斥，决策树只挂载其一。"""
        self.controller.round_count = 200
        story = self.controller.story
        story.story_tags.add("curtain_call_script_recovered")
        story.story_tags.add("ending:puppet_final_defeated")
        story.story_tags.add("elf_key_obtained")
        story.elf_key_obtained = True
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 30
        self.assertTrue(story._is_kind_puppet_dialogue_ready())
        self.assertFalse(story._is_puppet_echo_gate_ready())
        self.assertFalse(story._is_power_curtain_dialogue_ready())
        scheduled = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled)
        self.assertIn("ending_kind_puppet_dialogue_round200", story.pending_consequences)
        self.assertNotIn("ending_power_curtain_dialogue_round200", story.pending_consequences)

        story.pending_consequences.clear()
        story.consumed_consequences.discard("ending_kind_puppet_dialogue_round200")
        story.story_tags.discard("ending:default_normal_scheduled")
        story.puppet_evil_value = 50
        story.elf_chain_ended = True
        story.elf_relation = 2
        self.assertFalse(story._is_kind_puppet_dialogue_ready())
        self.assertFalse(story._is_power_curtain_direct_ready())
        self.assertTrue(story._is_power_curtain_dialogue_ready())
        scheduled2 = story.ensure_default_normal_ending_schedule()
        self.assertTrue(scheduled2)
        self.assertIn("ending_power_curtain_dialogue_round200", story.pending_consequences)
        self.assertNotIn("ending_kind_puppet_dialogue_round200", story.pending_consequences)

    def test_power_curtain_choice_event_three_options(self):
        """接管谢幕选择门：0/1 均为 stage_curtain_power（剧情文案不同），2 为选择困难症→进入普通结局主线。"""
        story = self.controller.story
        story.story_tags.add("curtain_call_script_recovered")
        story.story_tags.add("ending:puppet_final_defeated")
        story.puppet_final_outcome = "defeated"
        story.puppet_evil_value = 50
        event = EndingPowerCurtainChoiceEvent(self.controller)
        self.assertEqual(len(event.choices), 3)
        event.resolve_choice(0)
        clear_info = getattr(self.controller, "game_clear_info", {})
        self.assertEqual(clear_info.get("ending_key"), "stage_curtain_power")
        self.assertEqual(clear_info.get("ending_meta", {}).get("power_curtain_choice_variant"), "order")
        self.controller.game_clear_info = None
        story.story_tags.discard("ending:stage_curtain_completed")
        event2 = EndingPowerCurtainChoiceEvent(self.controller)
        event2.resolve_choice(1)
        clear_info2 = getattr(self.controller, "game_clear_info", {})
        self.assertEqual(clear_info2.get("ending_key"), "stage_curtain_power")
        self.assertEqual(clear_info2.get("ending_meta", {}).get("power_curtain_choice_variant"), "will")
        self.controller.game_clear_info = None
        story.story_tags.discard("ending:stage_curtain_completed")
        event3 = EndingPowerCurtainChoiceEvent(self.controller)
        event3.resolve_choice(2)
        # 选择困难症进入普通结局主线：挂载终局第一门，不直接触发结局
        self.assertIsNone(getattr(self.controller, "game_clear_info", None))
        self.assertIn("ending_default_force_gate_round_200", story.pending_consequences)
