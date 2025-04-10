"""
基础测试类，包含通用的测试设置和工具方法
"""
import unittest
from server import GameController
from models.player import Player
from models.monster import Monster
from models.status import Status, StatusName
from models.items import ItemType

class BaseTest(unittest.TestCase):
    """基础测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.controller = GameController()
        self.player = self.controller.player
        
    def tearDown(self):
        """测试后的清理工作"""
        pass
        
    def create_test_monster(self, name="测试怪物", hp=10, atk=5, tier=1):
        """创建一个测试用的怪物"""
        return Monster(name, hp, atk, tier)
        
    def apply_status_to_player(self, status_name, duration=1):
        """给玩家添加状态"""
        status = Status(status_name, duration)
        self.player.apply_status(status)
        
    def clear_player_status(self):
        """清除玩家所有状态"""
        self.player.statuses.clear()
        
    def clear_player_inventory(self):
        """清空玩家背包"""
        self.player.clear_inventory()
        
    def set_player_stats(self, hp=None, atk=None, gold=None):
        """设置玩家属性"""
        if hp is not None:
            self.player.hp = hp
        if atk is not None:
            self.player.atk = atk
        if gold is not None:
            self.player.gold = gold 