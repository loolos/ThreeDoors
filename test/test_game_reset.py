import unittest
from models.game_config import GameConfig
from scenes import DoorScene
from test.test_base import BaseTest

class TestGameReset(BaseTest):
    """测试游戏重置"""
    
    def test_game_reset(self):
        """测试游戏重置"""
        # 修改一些游戏状态
        self.set_player_stats(hp=10, gold=100)
        self.controller.round_count = 5
        self.clear_player_inventory()
        
        # 重置游戏
        self.setUp()
        
        # 检查玩家属性是否重置
        self.assertEqual(self.player.hp, GameConfig.START_PLAYER_HP)
        self.assertEqual(self.player.gold, 0)
        self.assertEqual(self.controller.round_count, 0)
        
        # 检查初始道具数量
        total_items = sum(len(items) for items in self.player.inventory.values())
        self.assertEqual(total_items, 4)
        
        # 检查场景是否重置
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

if __name__ == '__main__':
    unittest.main() 