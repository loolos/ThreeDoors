import unittest.mock
import random

from models.door import DoorEnum
from models.events import MoonBountyEvent
from models.items import FlyingHammer
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(event_door)
        self.assertEqual(self.player.gold, 100)
        self.assertIn("delay_gold_loss", story.pending_consequences)

        self.controller.round_count = 3
        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(event_door)
        self.assertEqual(self.player.gold, 85)
        self.assertIn("delay_gold_loss", story.consumed_consequences)

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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)

        combined = "\n".join(self.controller.messages)
        self.assertIn("旧事", combined)
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            changed_door = story.apply_pre_enter_checks(reward_door)

        self.assertEqual(changed_door.reward, {"gold": 6})

    def test_long_chain_can_progress_from_hunter_to_shop_to_forced_event(self):
        story = self.controller.story
        moon_event = MoonBountyEvent(self.controller)
        moon_event.resolve_choice(0)
        self.assertIn("moon_chain_accept_hunter", story.pending_consequences)

        first_event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            hunter_door = story.apply_pre_enter_checks(first_event_door)
        self.assertEqual(hunter_door.enum.name, "MONSTER")
        self.assertTrue(hasattr(hunter_door.monster, "story_consequence_id"))
        self.assertIn("moon_chain_accept_hunter", story.pending_consequences)

        story.resolve_battle_consequence(hunter_door.monster, defeated=True)
        self.assertIn("moon_chain_accept_shop", story.pending_consequences)

        shop_door = DoorEnum.SHOP.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)
        self.assertIn("moon_chain_accept_force_verdict", story.pending_consequences)

        second_event_door = DoorEnum.EVENT.create_instance(controller=self.controller)
        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            forced_event_door = story.apply_pre_enter_checks(second_event_door)
        self.assertEqual(getattr(forced_event_door, "story_forced_event_key", ""), "moon_verdict_event")

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

        with unittest.mock.patch("models.story_system.random.random", side_effect=[0.0, 0.99, 1.0]):
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

        with unittest.mock.patch("models.story_system.random.random", side_effect=[0.0, 0.0, 1.0, 1.0, 1.0]):
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

        with unittest.mock.patch("models.story_system.random.random", return_value=0.0):
            story.apply_pre_enter_checks(shop_door)

        random.seed(20260309)
        shop.generate_items()
        refreshed_discount_costs = [item.cost for item in shop.shop_items]

        self.assertTrue(all(new <= old for new, old in zip(refreshed_discount_costs, baseline_costs)))
        self.assertTrue(any(new < old for new, old in zip(refreshed_discount_costs, baseline_costs)))
        self.assertEqual(shop.pending_price_ratio, 1.0)
