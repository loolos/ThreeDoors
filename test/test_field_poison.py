import unittest
from server import GameController
from models.status import StatusName, FieldPoisonStatus
from scenes import DoorScene, BattleScene
from test.test_base import BaseTest

class TestFieldPoison(BaseTest):
    """测试野外中毒状态"""
    
    def test_field_poison_damage(self):
        """测试野外中毒在探索中扣血效果"""
        p = self.player
        
        # 应用野外中毒状态
        duration = 3
        p.apply_status(StatusName.FIELD_POISON.create_instance(duration=duration, target=p))
        
        # 验证状态已应用
        self.assertTrue(p.has_status(StatusName.FIELD_POISON))
        self.assertEqual(p.get_status_duration(StatusName.FIELD_POISON), duration)
        
        # 模拟探索回合 (逐步验证以应对动态扣血)
        # 第一跳: 100 -> 100 - floor(100 * 0.05) = 95
        last_hp = p.hp
        expected_damage = max(1, int(last_hp * 0.05))
        p.adventure_status_duration_pass()
        self.assertEqual(p.hp, last_hp - expected_damage)
        self.assertEqual(p.get_status_duration(StatusName.FIELD_POISON), 2)
        
        # 第二跳: 95 -> 95 - floor(95 * 0.05) = 95 - 4 = 91
        last_hp = p.hp
        expected_damage = max(1, int(last_hp * 0.05))
        p.adventure_status_duration_pass()
        self.assertEqual(p.hp, last_hp - expected_damage)
        self.assertEqual(p.get_status_duration(StatusName.FIELD_POISON), 1)

        # 第三跳: 91 -> 91 - 4 = 87
        last_hp = p.hp
        expected_damage = max(1, int(last_hp * 0.05))
        p.adventure_status_duration_pass()
        self.assertEqual(p.hp, last_hp - expected_damage)
        
        # 验证状态已消失
        self.assertFalse(p.has_status(StatusName.FIELD_POISON))

    def test_field_poison_persistence_through_battle(self):
        """测试野外中毒不会被战斗状态清理清除"""
        p = self.player
        
        # 应用野外中毒
        p.apply_status(StatusName.FIELD_POISON.create_instance(duration=5, target=p))
        # 应用战斗中毒
        p.apply_status(StatusName.POISON.create_instance(duration=5, target=p))
        
        self.assertTrue(p.has_status(StatusName.FIELD_POISON))
        self.assertTrue(p.has_status(StatusName.POISON))
        
        # 清除战斗状态
        p.clear_battle_status()
        
        # 野外中毒应该依然存在，战斗中毒应该消失
        self.assertTrue(p.has_status(StatusName.FIELD_POISON))
        self.assertFalse(p.has_status(StatusName.POISON))

if __name__ == '__main__':
    unittest.main()
