import unittest
from server import GameController
from models.items import ItemType

class TestGameInitialization(unittest.TestCase):
    """测试游戏初始化"""
    
    def setUp(self):
        self.controller = GameController()
    
    def test_initial_inventory(self):
        """测试初始物品栏"""
        # 检查物品栏中的物品类型数量
        total_items = sum(len(items) for items in self.controller.player.inventory.values())
        self.assertEqual(total_items, 4)
        
        # 检查战斗物品
        battle_items = self.controller.player.get_items_by_type(ItemType.BATTLE)
        self.assertEqual(len(battle_items), 3)  # 飞锤、巨大卷轴、结界
        
        # 检查被动物品
        passive_items = self.controller.player.get_items_by_type(ItemType.PASSIVE)
        self.assertEqual(len(passive_items), 1)  # 复活卷轴

if __name__ == '__main__':
    unittest.main() 