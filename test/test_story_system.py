import unittest.mock
import random

from models.door import DoorEnum
from models.events import (
    MoonBountyEvent,
    ElfThiefIntroEvent,
    ElfSideMerchantDisguisedEvent,
    ElfRooftopDuelEvent,
    RefugeeCaravanEvent,
    PuppetAbandonmentEvent,
    PuppetSignalEvent,
)
from models.items import FlyingHammer
from models.monster import Monster
from models.game_config import GameConfig
from test.test_base import BaseTest


class TestStorySystem(BaseTest):
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
        self.assertIn("她被追兵缠住，正在把你强拉进并肩作战。", self.controller.messages)

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
        self.assertEqual(self.controller.current_event.title, "Moon Verdict")

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

    def test_long_chain_can_progress_from_hunter_to_shop_to_forced_event(self):
        story = self.controller.story
        moon_event = MoonBountyEvent(self.controller)
        moon_event.resolve_choice(0)
        self.assertIn("moon_chain_accept_hunter", story.pending_consequences)

        first_event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            hunter_door = story.apply_pre_enter_checks(first_event_door)
        self.assertEqual(hunter_door.enum.name, "MONSTER")
        self.assertTrue(hasattr(hunter_door.monster, "story_consequence_id"))
        self.assertIn("moon_chain_accept_hunter", story.pending_consequences)

        story.resolve_battle_consequence(hunter_door.monster, defeated=True)
        self.assertIn("moon_chain_accept_shop", story.pending_consequences)

        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)
        self.assertIn("moon_chain_accept_force_verdict", story.pending_consequences)

        second_event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0):
            forced_event_door = story.apply_pre_enter_checks(second_event_door)
        self.assertEqual(getattr(forced_event_door, "story_forced_event_key", ""), "moon_verdict_event")

    def test_puppet_intro_registers_forced_minion_and_signal_gate(self):
        story = self.controller.story
        self.controller.round_count = 9
        event = PuppetAbandonmentEvent(self.controller)
        event.resolve_choice(0)

        minion = story.pending_consequences.get("puppet_chain_hide_minion_gate")
        signal = story.pending_consequences.get("puppet_chain_hide_signal_event_gate")
        self.assertIsNotNone(minion)
        self.assertIsNotNone(signal)
        self.assertEqual(minion.min_round, 10)
        self.assertEqual(minion.max_round, 13)
        self.assertTrue(minion.force_on_expire)
        self.assertEqual(minion.force_door_type, "MONSTER")
        self.assertTrue(signal.force_on_expire)
        self.assertEqual(signal.force_door_type, "EVENT")
        self.assertIn("consumed:puppet_chain_hide_minion_gate", signal.required_flags)

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
        self.assertIn("puppet_chain_hide_minion_gate", story.pending_consequences)

        story.resolve_battle_consequence(minion_door.monster, defeated=True)
        self.assertIn("puppet_chain_hide_minion_gate", story.consumed_consequences)

        self.controller.round_count = 17
        reward_door = DoorEnum.REWARD.create_instance(controller=self.controller)
        forced_event_door = story.apply_pre_enter_checks(reward_door)
        self.assertEqual(forced_event_door.enum.name, "EVENT")
        self.assertEqual(getattr(forced_event_door, "story_forced_event_key", ""), "puppet_signal_event")

    def test_puppet_signal_registers_forced_shop_trap_reward_and_core_event(self):
        story = self.controller.story
        self.controller.round_count = 20
        PuppetSignalEvent(self.controller).resolve_choice(0)

        shop = story.pending_consequences.get("puppet_mid_empathy_shop_gate")
        trap = story.pending_consequences.get("puppet_mid_empathy_trap_gate")
        reward = story.pending_consequences.get("puppet_mid_empathy_reward_gate")
        core = story.pending_consequences.get("puppet_mid_empathy_core_event_gate")
        self.assertIsNotNone(shop)
        self.assertIsNotNone(trap)
        self.assertIsNotNone(reward)
        self.assertIsNotNone(core)

        self.assertTrue(shop.force_on_expire)
        self.assertEqual(shop.force_door_type, "SHOP")
        self.assertTrue(trap.force_on_expire)
        self.assertEqual(trap.force_door_type, "TRAP")
        self.assertTrue(reward.force_on_expire)
        self.assertEqual(reward.force_door_type, "REWARD")
        self.assertTrue(core.force_on_expire)
        self.assertEqual(core.force_door_type, "EVENT")
        self.assertIn("consumed:puppet_mid_empathy_shop_gate", trap.required_flags)
        self.assertIn("consumed:puppet_mid_empathy_trap_gate", reward.required_flags)
        self.assertIn("consumed:puppet_mid_empathy_reward_gate", core.required_flags)

    def test_puppet_dark_boss_can_be_weakened_by_kind_persona(self):
        story = self.controller.story
        story.choice_flags.update({"puppet_intro_hide", "puppet_signal_empathy", "puppet_descent_patch"})
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
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.9
        ):
            changed = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed.enum.name, "MONSTER")
        self.assertEqual(changed.monster.name, "堕暗机偶·弃线者")
        self.assertLess(changed.monster.hp, 200)
        self.assertLess(changed.monster.atk, 30)
        self.assertTrue(any("善良人格" in msg for msg in self.controller.messages))

    def test_puppet_dark_boss_can_be_forced_and_strengthened(self):
        story = self.controller.story
        story.choice_flags.update(
            {
                "puppet_intro_blackout",
                "puppet_intro_decoy",
                "puppet_signal_sellout",
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
            payload={"hp_ratio": 1.5, "atk_ratio": 1.4},
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

        # 加权抽中该后果后，effect 内 replace_chance 用 random.random()；<0.35 则替换怪物
        with unittest.mock.patch("models.story_system.random.uniform", return_value=0.0), unittest.mock.patch(
            "models.story_system.random.random", return_value=0.0
        ):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed_door.enum.name, "MONSTER")
        self.assertNotEqual(changed_door.monster.name, "史莱姆")
        self.assertIn("monster_revenge_replace", story.consumed_consequences)

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
