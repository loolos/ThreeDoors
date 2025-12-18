"""
场景系统测试
"""
from test.test_base import BaseTest
from models.door import DoorEnum
from models.monster import Monster
from models import items
from scenes import DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene

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

    def test_game_over_transition(self):
        """测试游戏结束场景"""
        self.clear_player_inventory() # 确保没有复活卷轴
        self.player.hp = 1
        door_scene = self.controller.scene_manager.current_scene
        door_scene.generate_doors([DoorEnum.TRAP, DoorEnum.MONSTER, DoorEnum.SHOP])
        
        # 踩陷阱致死
        door_scene.doors[0].damage = 100
        door_scene.handle_choice(0)
        
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)

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