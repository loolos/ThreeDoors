"""
状态系统测试
"""
from test_base import BaseTest
from models.monster import Monster
from models.status import StatusName


class TestStatusSystem(BaseTest):
    """状态系统测试类"""
    def setUp(self):
        super().setUp()
        self.player = self.controller.player
        self.monster = Monster("测试怪物", 100, 10)

    def test_status_application(self):
        """测试状态应用"""
        status = StatusName.WEAK.create_instance(duration=3, target=self.player)
        self.player.apply_status(status)
        self.assertTrue(self.player.has_status(StatusName.WEAK))
        self.assertEqual(self.player.get_status_duration(StatusName.WEAK), 3)

    def test_status_duration(self):
        """测试状态持续时间"""
        status = StatusName.WEAK.create_instance(duration=2, target=self.player)
        self.player.apply_status(status)
        self.assertEqual(self.player.get_status_duration(StatusName.WEAK), 2)
        self.player.battle_status_duration_pass()
        self.assertEqual(self.player.get_status_duration(StatusName.WEAK), 1)
        self.player.battle_status_duration_pass()
        self.assertFalse(self.player.has_status(StatusName.WEAK))

    def test_stun_effect(self):
        """测试眩晕效果"""
        status = StatusName.STUN.create_instance(duration=2, target=self.player)
        self.player.apply_status(status)
        self.assertTrue(self.player.has_status(StatusName.STUN))
        result = self.player.attack(self.monster)
        self.assertFalse(result)

    def test_poison_effect(self):
        """测试中毒效果"""
        self.player.hp = 100
        status = StatusName.POISON.create_instance(duration=2, target=self.player)
        self.player.apply_status(status)
        self.assertTrue(self.player.has_status(StatusName.POISON))
        hp_before = self.player.hp
        self.player.battle_status_duration_pass()
        self.assertLess(self.player.hp, hp_before)

    def test_weak_effect(self):
        """测试虚弱效果"""
        base_atk = self.player.atk
        status = StatusName.WEAK.create_instance(duration=3, target=self.player)
        self.player.apply_status(status)
        self.assertLess(self.player.atk, base_atk)

    def test_weak_expires_in_adventure_rounds(self):
        """测试机关/事件施加的虚弱在冒险回合同样会过期并恢复攻击力"""
        self.player._atk = 10
        self.player.apply_status(StatusName.WEAK.create_instance(duration=1, target=self.player))
        self.assertEqual(self.player.atk, 8)

        self.player.adventure_status_duration_pass()

        self.assertFalse(self.player.has_status(StatusName.WEAK))
        self.assertEqual(self.player.atk, 10)

    def test_immunity_effect(self):
        """测试免疫效果"""
        immune = StatusName.IMMUNE.create_instance(duration=5, target=self.player)
        self.player.apply_status(immune)
        self.assertTrue(self.player.has_status(StatusName.IMMUNE))
        poison = StatusName.POISON.create_instance(duration=3, target=self.player)
        self.player.apply_status(poison)
        self.assertFalse(self.player.has_status(StatusName.POISON))
