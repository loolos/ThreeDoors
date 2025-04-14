"""
游戏系统测试
"""
from test.test_base import BaseTest
from models.game_config import GameConfig
from scenes import DoorScene
from models.items import ItemType
import random
class TestGameSystem(BaseTest):
    """游戏系统测试类"""
    
    def test_game_initialization(self):
        """测试游戏初始化"""
        # 检查物品栏中的物品类型数量
        total_items = sum(len(items) for items in self.controller.player.inventory.values())
        self.assertEqual(total_items, 4)
        
        # 检查战斗物品
        battle_items = self.controller.player.get_items_by_type(ItemType.BATTLE)
        self.assertEqual(len(battle_items), 3)  # 飞锤、巨大卷轴、结界
        
        # 检查被动物品
        passive_items = self.controller.player.get_items_by_type(ItemType.PASSIVE)
        self.assertEqual(len(passive_items), 1)  # 复活卷轴
        
    def test_game_reset(self):
        """测试游戏重置"""
        # 修改一些游戏状态
        self.set_player_stats(hp=10, gold=100)
        self.controller.round_count = 5
        for k in range(10):
            self.controller.scene_manager.current_scene.handle_choice(random.randint(0, 2))
        self.clear_player_inventory()
        
        # 重置游戏
        self.controller.reset_game()
        self.player = self.controller.player  # 更新 player 引用
        
        # 检查玩家属性是否重置
        self.assertEqual(self.player.hp, GameConfig.START_PLAYER_HP)
        self.assertEqual(self.player.gold, 0)
        self.assertEqual(self.controller.round_count, 0)
        
        # 检查初始道具数量
        total_items = sum(len(items) for items in self.player.inventory.values())
        self.assertEqual(total_items, 4)
        
        # 检查场景是否重置
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
    def test_game_rounds(self):
        """测试游戏回合"""
        pass
        
    def test_game_messages(self):
        """测试游戏消息系统"""
        pass
        
    def test_game_stability(self):
        """测试游戏稳定性"""
        pass 