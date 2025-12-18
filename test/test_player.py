"""
玩家系统测试
"""
from test.test_base import BaseTest
from models.status import StatusName, Status
from models import items

class TestPlayerSystem(BaseTest):
    """玩家系统测试类"""
    
    def test_healing(self):
        """测试治疗"""
        self.player.hp = 10
        initial_hp = self.player.hp
        self.player.heal(5)
        self.assertEqual(self.player.hp, initial_hp + 5)

    def test_gold(self):
        """测试金币"""
        initial_gold = self.player.gold
        self.player.add_gold(100)
        self.assertEqual(self.player.gold, initial_gold + 100)

    def test_status_application(self):
        """测试状态应用"""
        # 测试中毒
        self.apply_status_to_player(StatusName.POISON, duration=3)
        self.assertTrue(self.player.has_status(StatusName.POISON))
        
        # 测试中毒伤害
        self.player.hp = 100
        self.player.battle_status_duration_pass()
        self.assertEqual(self.player.hp, 90) # 10% dmg

    def test_stun_effect(self):
        """测试晕眩效果"""
        # 添加晕眩
        self.apply_status_to_player(StatusName.STUN, duration=2)
        
        # 尝试攻击
        monster = self.create_test_monster()
        result = self.player.attack(monster)
        self.assertFalse(result)
        self.assertIn("眩晕", self.controller.messages[-1])

    def test_immunity(self):
        """测试免疫效果"""
        # 添加免疫
        self.apply_status_to_player(StatusName.IMMUNE, duration=5)
        
        # 尝试添加负面状态
        self.apply_status_to_player(StatusName.POISON)
        self.assertFalse(self.player.has_status(StatusName.POISON))
        
        # 尝试添加正面状态（应允许）
        self.apply_status_to_player(StatusName.ATK_UP)
        self.assertTrue(self.player.has_status(StatusName.ATK_UP))

    def test_inventory(self):
        """测试背包"""
        # 初始有4个物品
        size = self.player.get_inventory_size()
        self.assertEqual(size, 4)
        
        # 添加物品
        item = items.HealingPotion("测试药水", heal_amount=10, cost=10)
        self.player.add_item(item)
        self.assertEqual(self.player.get_inventory_size(), size + 1)
        
        # 移除物品
        self.player.remove_item(item)
        self.assertEqual(self.player.get_inventory_size(), size)