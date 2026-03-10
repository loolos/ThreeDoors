"""
怪物系统测试
"""
from test.test_base import BaseTest
from models.items import ItemType
from models import items
from models.monster import Monster, get_random_monster
from types import SimpleNamespace
import random

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
        self.assertTrue(any("掉落：飞锤" in m for m in self.controller.messages), "日志应包含掉落信息")

    def test_monster_attributes(self):
        """测试怪物属性初始化"""
        m = Monster(tier=3)
        self.assertEqual(m.tier, 3)
        self.assertIsNotNone(m.name)
        self.assertIsNotNone(m.hp)
        self.assertIsNotNone(m.atk)

    def test_monster_custom_name_no_keyerror(self):
        """自定义怪物名不在 MONSTER_TYPE_HINTS 时不应 KeyError"""
        m = Monster(name="自定义未知怪", hp=20, atk=5, tier=1)
        self.assertEqual(m.tier, 1)
        self.assertIsInstance(m.type_hint, str)
        self.assertTrue(len(m.type_hint) > 0)

    def test_random_monster_scales_with_player_power(self):
        """同回合下，高战力玩家应遭遇更强怪物。"""
        weak_player = SimpleNamespace(_atk=8, atk=8, hp=60, gold=20)
        strong_player = SimpleNamespace(_atk=24, atk=24, hp=160, gold=300)

        random.seed(20260310)
        weak_pack = [get_random_monster(current_round=28, player=weak_player) for _ in range(40)]
        random.seed(20260310)
        strong_pack = [get_random_monster(current_round=28, player=strong_player) for _ in range(40)]

        weak_avg_hp = sum(m.hp for m in weak_pack) / len(weak_pack)
        strong_avg_hp = sum(m.hp for m in strong_pack) / len(strong_pack)
        weak_avg_atk = sum(m.atk for m in weak_pack) / len(weak_pack)
        strong_avg_atk = sum(m.atk for m in strong_pack) / len(strong_pack)
        self.assertGreater(strong_avg_hp, weak_avg_hp)
        self.assertGreater(strong_avg_atk, weak_avg_atk)