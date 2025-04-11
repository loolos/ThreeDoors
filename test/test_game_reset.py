import unittest
from server import GameController
from models.game_config import GameConfig

class TestGameReset(unittest.TestCase):
    """测试游戏重置功能"""
    
    def setUp(self):
        self.controller = GameController()
    
    def test_reset_game(self):
        """测试游戏重置"""
        # 修改一些游戏状态
        self.controller.player.hp = 50
        self.controller.player.gold = 100
        self.controller.round_count = 5
        self.controller.scene_manager.go_to("battle_scene")
        
        # 重置游戏
        self.controller.reset_game()
        
        # 验证重置后的状态
        self.assertEqual(self.controller.player.hp, GameConfig.START_PLAYER_HP)  # 应该是20
        self.assertEqual(self.controller.player.gold, 0)
        self.assertEqual(self.controller.round_count, 0)
        self.assertEqual(self.controller.scene_manager.current_scene.__class__.__name__, "DoorScene")
        self.assertEqual(len(self.controller.player.inventory), 3)

if __name__ == '__main__':
    unittest.main() 