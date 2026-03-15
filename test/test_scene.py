"""
场景系统测试
"""
from test.test_base import BaseTest
from models.door import DoorEnum
from models.monster import Monster
from models import items
from models.game_config import GameConfig
from scenes import DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene
from unittest import mock

class TestSceneSystem(BaseTest):
    """场景系统测试类"""
    
    def setUp(self):
        super().setUp()
        self.controller.scene_manager.go_to("door_scene")
        
    def test_scene_transitions(self):
        """测试场景切换流程"""
        # 1. 门场景 -> 战斗场景
        door_scene = self.controller.scene_manager.current_scene
        door_scene.generate_doors([DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP])
        # 确保门1是怪物
        door_scene.doors[0].monster = Monster("测试怪物", 100, 10)
        
        door_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        
        # 2. 战斗场景 -> 道具使用场景
        battle_scene = self.controller.scene_manager.current_scene
        # 给玩家发个道具确保能进
        self.player.add_item(items.FlyingHammer("飞锤", cost=0, duration=3))
        battle_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)
        
        # 3. 道具使用 -> 战斗场景
        use_item_scene = self.controller.scene_manager.current_scene
        use_item_scene.handle_choice(0) # 使用飞锤
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        
        # 4. 战斗结束 -> 门场景
        self.controller.current_monster.hp = 1
        self.controller.scene_manager.current_scene.handle_choice(0) # 攻击
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

    def test_shop_transition(self):
        """测试商店场景切换"""
        self.player.gold = 100
        door_scene = self.controller.scene_manager.current_scene
        door_scene.generate_doors([DoorEnum.SHOP, DoorEnum.MONSTER, DoorEnum.TRAP])
        
        door_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
        
        # 离开商店
        self.controller.scene_manager.current_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

    def test_shop_items_refresh_on_each_enter(self):
        """每次进入商店时都应刷新商品列表"""
        self.player.gold = 100
        shop = self.controller.current_shop
        with mock.patch.object(shop, "generate_items", wraps=shop.generate_items) as mocked_generate:
            # 第一次进入商店
            door_scene = self.controller.scene_manager.current_scene
            door_scene.generate_doors([DoorEnum.SHOP, DoorEnum.MONSTER, DoorEnum.TRAP])
            door_scene.handle_choice(0)
            self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
            self.controller.scene_manager.current_scene.handle_choice(0)  # 离开商店
            self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

            # 第二次进入商店
            door_scene = self.controller.scene_manager.current_scene
            door_scene.generate_doors([DoorEnum.SHOP, DoorEnum.MONSTER, DoorEnum.TRAP])
            door_scene.handle_choice(0)
            self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)

            self.assertGreaterEqual(mocked_generate.call_count, 2)

    def test_game_over_transition(self):
        """测试游戏结束场景"""
        self.clear_player_inventory() # 确保没有复活卷轴
        self.player.hp = 1
        door_scene = self.controller.scene_manager.current_scene
        door_scene.generate_doors([DoorEnum.TRAP, DoorEnum.MONSTER, DoorEnum.SHOP])
        
        # 踩陷阱致死
        door_scene.doors[0].damage = 100
        import unittest.mock
        with unittest.mock.patch('random.choice', return_value='spike'):
            door_scene.handle_choice(0)
        
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)

    def test_game_clear_mode_disables_revive_option(self):
        self.controller.trigger_game_clear(
            ending_key="default_normal",
            ending_title="普通结局·迷宫出口",
            ending_description="测试结局描述",
        )
        scene = self.controller.scene_manager.current_scene
        self.assertIsInstance(scene, GameOverScene)
        self.assertEqual(scene.button_texts[1], "结局已达成")

        self.controller.clear_messages()
        scene.handle_choice(1)
        self.assertIn("无需使用复活卷轴", "\n".join(self.controller.messages))

    def test_button_text_door(self):
        """测试门场景按钮文本"""
        scene = self.controller.scene_manager.current_scene
        texts = scene.get_button_texts()
        self.assertEqual(len(texts), 3)
        self.assertTrue(all("门" in t for t in texts))

    def test_button_text_battle(self):
        """测试战斗场景按钮文本"""
        self.controller.scene_manager.go_to("battle_scene")
        texts = self.controller.scene_manager.current_scene.get_button_texts()
        self.assertEqual(texts, ["攻击", "使用道具", "逃跑"])

    def test_event_ambush_retriggers_after_escape_until_monster_is_defeated(self):
        """事件门引出的伏击：逃跑不结算，击倒后才结算。"""
        story = self.controller.story
        consequence_id = "event_hunter_repeat"
        story.register_consequence(
            choice_flag="repeat_case",
            consequence_id=consequence_id,
            effect_key="revenge_ambush",
            chance=1.0,
            trigger_door_types=["EVENT"],
            payload={"force_hunter": True},
        )

        door_scene = self.controller.scene_manager.current_scene
        door_scene.generate_doors([DoorEnum.EVENT, DoorEnum.MONSTER, DoorEnum.TRAP])

        with mock.patch.object(GameConfig, "EVENT_DOOR_SKIP_REWRITE_CHANCE", 0.0), mock.patch(
            "models.story_system.random.uniform", return_value=0.0
        ):
            door_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)

        with mock.patch("models.player.random.random", return_value=0.0):
            self.controller.scene_manager.current_scene.handle_choice(2)
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        self.assertIn(consequence_id, story.pending_consequences)
        self.assertNotIn(consequence_id, story.consumed_consequences)

        door_scene = self.controller.scene_manager.current_scene
        door_scene.generate_doors([DoorEnum.EVENT, DoorEnum.MONSTER, DoorEnum.TRAP])
        with mock.patch.object(GameConfig, "EVENT_DOOR_SKIP_REWRITE_CHANCE", 0.0), mock.patch(
            "models.story_system.random.uniform", return_value=0.0
        ):
            door_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)

        self.player.atk = 999
        self.controller.current_monster.hp = 1
        self.controller.scene_manager.current_scene.handle_choice(0)
        self.assertIn(consequence_id, story.consumed_consequences)
        self.assertNotIn(consequence_id, story.pending_consequences)

    def test_escape_from_puppet_final_boss_only_records_finale_parameters(self):
        self.controller.scene_manager.go_to("battle_scene")
        monster = Monster(name="裂齿·夜魇·堕暗机偶", hp=200, atk=1, tier=4)
        setattr(monster, "story_puppet_final_boss", True)
        self.controller.current_monster = monster
        self.controller.scene_manager.current_scene.on_enter()

        with mock.patch("models.player.random.random", return_value=0.0):
            self.controller.scene_manager.current_scene.handle_choice(2)

        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        self.assertIsNone(getattr(self.controller, "game_clear_info", None))
        self.assertEqual(getattr(self.controller.story, "puppet_final_outcome", ""), "escaped")
        self.assertEqual(getattr(self.controller.story, "puppet_patrol_state", ""), "active")
        self.assertIn("走廊中来回游荡", getattr(self.controller.story, "puppet_patrol_note", ""))

    def test_tier_unlock_check_runs_every_five_rounds(self):
        """tier 解锁检测应仅在每5回合触发，并写入日志。解锁条件：min(攻击, 生命/2) 达到对应门槛。"""
        self.controller.round_count = 4
        self.player.hp = 240
        self.player.atk = 120  # min(120, 120)=120，足以解锁到 tier 4（需求 112）

        # 非5的倍数不触发检测
        self.controller.check_and_unlock_monster_tier()
        self.assertEqual(self.controller.unlocked_monster_tier, 1)

        # 到5回合触发检测，按 min(攻击, 生命/2) 一次性解锁到可达上限
        self.controller.round_count = 5
        self.controller.check_and_unlock_monster_tier()
        self.assertEqual(self.controller.unlocked_monster_tier, 4)
        self.assertTrue(any("威胁升级" in m for m in self.controller.messages))
        self.assertTrue(any("凶暴巨兽已被惊醒" in m for m in self.controller.messages))

    def test_door_generation_respects_unlocked_tier_cap(self):
        """门场景生成怪物时应受已解锁 tier 限制。"""
        self.controller.unlocked_monster_tier = 2
        self.controller.round_count = 99
        door_scene = self.controller.scene_manager.current_scene

        for _ in range(30):
            door_scene.generate_doors()
            monster_door = next(door for door in door_scene.doors if door.enum == DoorEnum.MONSTER)
            self.assertLessEqual(monster_door.monster.tier, 2)
