import unittest.mock

from models.door import DoorEnum
from models.monster import Monster
from test.test_base import BaseTest


class TestStorySystem(BaseTest):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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
        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", side_effect=[0.0, 0.0]):
            changed_door = story.apply_pre_enter_checks(monster_door)

        self.assertEqual(changed_door.enum.name, "REWARD")

    def test_high_moral_does_not_affect_irrelevant_monster(self):
        story = self.controller.story
        story.moral_score = 60
        slime = Monster(name="史莱姆", hp=18, atk=2, tier=1)
        monster_door = DoorEnum.MONSTER.create_instance(controller=self.controller, monster=slime)
        hp_before = monster_door.monster.hp

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(event_door)

        self.assertIn("chain_second", story.pending_consequences)
        self.assertIn("consumed:chain_start", story.story_tags)

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)
        self.assertIn("chain_second", story.consumed_consequences)

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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(event_door)

        self.assertTrue(marker["called"])
        self.assertIn("custom_id", story.consumed_consequences)

    def test_revenge_ambush_converts_selected_door_to_hunter_monster(self):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(event_door)

        self.assertEqual(changed_door.enum.name, "MONSTER")
        self.assertIn(changed_door.monster.name, {"土匪", "狼人", "暗影刺客"})
        self.assertIn("revenge_hunter_case", story.consumed_consequences)

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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(shop_door)

        self.assertEqual(changed_door.enum.name, "SHOP")
        self.assertLess(changed_door.shop.shop_items[0].cost, original_cost)
        self.assertIn("shop_discount_case", story.consumed_consequences)
