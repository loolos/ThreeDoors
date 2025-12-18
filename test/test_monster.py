"""
怪物系统测试
"""
from test.test_base import BaseTest
from models.items import ItemType
from models import items
from models.monster import Monster

class TestMonsterSystem(BaseTest):
    """怪物系统测试类"""
    
    def test_loot_generation(self):
        """测试掉落生成"""
        import traceback
        try:
            # 尝试多次以确保覆盖掉落情况
            has_loot = False
            for _ in range(20):
                monster = Monster("测试怪物", 10, 5, tier=1)
                if monster.loot:
                    has_loot = True
                    self.assertIsInstance(monster.loot[0], items.GoldBag)
                    break
            self.assertTrue(has_loot, "Should generate loot at least once in 20 tries")
        except Exception:
            traceback.print_exc()
            raise
        # 高级怪可能有更多掉落
        # 并非绝对，因为是概率掉落，但在大量测试中应能覆盖

    def test_loot_application(self):
        """测试掉落应用"""
        monster = self.create_test_monster(name="测试怪物")
        # 强制设置掉落
        hammer = items.FlyingHammer("飞锤", cost=5, duration=3)
        monster.loot = [hammer]
        
        # 击杀处理掉落
        old_size = self.player.get_inventory_size()
        monster.process_loot(self.player)
        
        self.assertEqual(self.player.get_inventory_size(), old_size + 1)
        self.assertIn("获得 飞锤", self.controller.messages[-1])

    def test_monster_attributes(self):
        """测试怪物属性初始化"""
        m = Monster(tier=3)
        self.assertEqual(m.tier, 3)
        self.assertIsNotNone(m.name)
        self.assertIsNotNone(m.hp)
        self.assertIsNotNone(m.atk)