import unittest
from server import GameController, Player, DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene, GameConfig
from models.monster import get_random_monster

class TestGameInitialization(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.config = GameConfig()

    def test_game_initialization(self):
        """测试游戏初始化"""
        self.assertIsNotNone(self.controller.player)
        self.assertEqual(self.controller.player.hp, self.config.START_PLAYER_HP)
        self.assertEqual(self.controller.player.atk, self.config.START_PLAYER_ATK)
        self.assertEqual(self.controller.player.gold, self.config.START_PLAYER_GOLD)
        self.assertEqual(self.controller.round_count, 0)
        self.assertIsNotNone(self.controller.scene_manager)
        self.assertIsNotNone(self.controller.door_scene)
        self.assertIsNotNone(self.controller.battle_scene)
        self.assertIsNotNone(self.controller.shop_scene)
        self.assertIsNotNone(self.controller.use_item_scene)
        self.assertIsNotNone(self.controller.game_over_scene)

    def test_initial_inventory(self):
        """测试初始道具栏"""
        self.assertEqual(len(self.controller.player.inventory), 4)
        inventory_types = [item["type"] for item in self.controller.player.inventory]
        self.assertIn("revive", inventory_types)
        self.assertIn("飞锤", inventory_types)
        self.assertIn("巨大卷轴", inventory_types)
        self.assertIn("结界", inventory_types)

class TestSceneTransitions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()

    def test_scene_transitions(self):
        """测试场景切换"""
        # 测试从门场景切换到战斗场景
        self.controller.go_to_scene("battle_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)

        # 测试从战斗场景切换到商店场景
        self.controller.go_to_scene("shop_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)

        # 测试从商店场景切换到道具使用场景
        self.controller.go_to_scene("use_item_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)

        # 测试从道具使用场景切换到游戏结束场景
        self.controller.go_to_scene("game_over_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)

class TestPlayerActions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.player = self.controller.player

    def test_player_healing(self):
        """测试玩家治疗"""
        initial_hp = self.player.hp
        self.player.take_damage(10)
        self.assertEqual(self.player.hp, initial_hp - 10)
        self.player.heal(5)
        self.assertEqual(self.player.hp, initial_hp - 5)

    def test_player_gold(self):
        """测试玩家金币"""
        initial_gold = self.player.gold
        self.player.add_gold(10)
        self.assertEqual(self.player.gold, initial_gold + 10)

    def test_player_status_effects(self):
        """测试玩家状态效果"""
        # 测试添加状态效果
        self.player.statuses["poison"] = {"duration": 3}
        self.assertEqual(self.player.statuses["poison"]["duration"], 3)
        
        # 测试状态效果描述
        status_desc = self.player.get_status_desc()
        self.assertIn("中毒", status_desc)

class TestDoorGeneration(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.door_scene = self.controller.door_scene

    def test_door_generation(self):
        """测试门生成"""
        self.door_scene._generate_doors()
        self.assertEqual(len(self.door_scene.doors), 3)
        
        # 检查是否至少有一扇怪物门
        monster_doors = [door for door in self.door_scene.doors if door.event == "monster"]
        self.assertGreater(len(monster_doors), 0)

class TestGameReset(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.config = GameConfig()

    def test_game_reset(self):
        """测试游戏重置"""
        # 修改一些游戏状态
        self.controller.player.hp = 10
        self.controller.player.gold = 100
        self.controller.round_count = 5
        
        # 重置游戏
        self.controller.reset_game()
        
        # 验证重置后的状态
        self.assertEqual(self.controller.player.hp, self.config.START_PLAYER_HP)
        self.assertEqual(self.controller.player.gold, self.config.START_PLAYER_GOLD)
        self.assertEqual(self.controller.round_count, 0)
        self.assertEqual(len(self.controller.player.inventory), 4)

class TestButtonTransitions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()

    def test_door_scene_buttons(self):
        """测试门场景按钮跳转"""
        # 确保当前在门场景
        self.controller.go_to_scene("door_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 测试每个门的点击
        for i in range(3):
            # 记录当前门的类型
            door = self.controller.scene_manager.current_scene.doors[i]
            self.controller.scene_manager.current_scene.handle_choice(i)
            
            # 根据门的类型验证场景跳转
            if door.event == "monster":
                self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
                # 回到门场景继续测试
                self.controller.go_to_scene("door_scene")
            elif door.event == "shop":
                self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
                # 回到门场景继续测试
                self.controller.go_to_scene("door_scene")
            elif door.event in ["trap", "reward"]:
                self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

    def test_battle_scene_buttons(self):
        """测试战斗场景按钮跳转"""
        # 设置一个怪物并进入战斗场景
        self.controller.current_monster = get_random_monster()
        self.controller.go_to_scene("battle_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        
        # 测试攻击按钮
        self.controller.scene_manager.current_scene.handle_choice(0)
        # 如果怪物死亡，应该回到门场景
        if self.controller.current_monster and self.controller.current_monster.hp <= 0:
            self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 测试使用道具按钮
        self.controller.go_to_scene("battle_scene")
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)
        
        # 测试逃跑按钮 - 成功情况
        self.controller.go_to_scene("battle_scene")
        initial_hp = self.controller.player.hp
        self.controller.scene_manager.current_scene.handle_choice(2)
        # 如果逃跑成功，应该回到门场景
        if self.controller.scene_manager.current_scene.__class__.__name__ == "DoorScene":
            self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
            # 逃跑成功不应该受到伤害
            self.assertEqual(self.controller.player.hp, initial_hp)
        
        # 测试逃跑按钮 - 失败情况
        self.controller.go_to_scene("battle_scene")
        initial_hp = self.controller.player.hp
        # 设置玩家状态为虚弱，降低逃跑成功率
        self.controller.player.statuses["weak"] = {"duration": 3}
        self.controller.scene_manager.current_scene.handle_choice(2)
        # 如果逃跑失败，应该受到伤害
        if self.controller.scene_manager.current_scene.__class__.__name__ == "BattleScene":
            self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
            self.assertLess(self.controller.player.hp, initial_hp)

    def test_shop_scene_buttons(self):
        """测试商店场景按钮跳转"""
        # 给玩家一些金币并进入商店场景
        self.controller.player.gold = 100
        self.controller.go_to_scene("shop_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
        
        # 测试购买按钮
        for i in range(3):
            self.controller.scene_manager.current_scene.handle_choice(i)
            # 购买后应该回到门场景
            self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
            # 回到商店场景继续测试
            self.controller.go_to_scene("shop_scene")

    def test_use_item_scene_buttons(self):
        """测试道具使用场景按钮跳转"""
        # 确保玩家有可用的道具
        self.controller.player.inventory = [
            {"name": "飞锤", "type": "飞锤", "value": 0, "cost": 0, "active": True},
            {"name": "结界", "type": "结界", "value": 0, "cost": 0, "active": True},
            {"name": "巨大卷轴", "type": "巨大卷轴", "value": 0, "cost": 0, "active": True}
        ]
        
        # 设置一个怪物并进入战斗场景
        self.controller.current_monster = get_random_monster()
        self.controller.go_to_scene("battle_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        
        # 进入道具使用场景
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)
        
        # 测试使用道具按钮
        initial_inventory_size = len(self.controller.player.inventory)
        self.controller.scene_manager.current_scene.handle_choice(0)  # 使用第一个道具
        
        # 验证道具使用后的状态
        self.assertEqual(len(self.controller.player.inventory), initial_inventory_size - 1)  # 道具应该被消耗
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)  # 应该回到战斗场景

    def test_game_over_scene_buttons(self):
        """测试游戏结束场景按钮跳转"""
        # 进入游戏结束场景
        self.controller.go_to_scene("game_over_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)
        
        # 测试重启游戏按钮
        self.controller.scene_manager.current_scene.handle_choice(0)
        self.assertEqual(self.controller.player.hp, self.controller.game_config.START_PLAYER_HP)
        self.assertEqual(self.controller.player.gold, self.controller.game_config.START_PLAYER_GOLD)
        
        # 测试使用复活卷轴按钮
        self.controller.go_to_scene("game_over_scene")
        self.controller.scene_manager.current_scene.handle_choice(1)
        # 如果有复活卷轴，应该回到上一个场景
        if "revive" in [item["type"] for item in self.controller.player.inventory]:
            self.assertIsNotNone(self.controller.last_scene)

if __name__ == '__main__':
    unittest.main() 