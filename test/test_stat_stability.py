import unittest
from server import GameController
from models.status import StatusName
from test.test_base import BaseTest

class TestStatStability(BaseTest):
    """测试玩家属性稳定性"""
    
    def test_atk_drift_bug_fix(self):
        """测试攻击力漂移 Bug 是否已修复"""
        p = self.player
        p._atk = 1  # 基础攻击力设置为 1
        
        # 应用虚弱状态 (-2)
        p.apply_status(StatusName.WEAK.create_instance(duration=3, target=p))
        # 验证当前攻击力被截断为 1
        self.assertEqual(p.atk, 1)
        
        # 结束虚弱状态
        p.statuses[StatusName.WEAK].duration = 1
        p.battle_status_duration_pass() # 这个调用会减少到0并调用 end_effect
        
        # 验证基础攻击力依然为 1，没有因为虚弱结束而变成 3
        self.assertEqual(p._atk, 1)
        self.assertEqual(p.atk, 1)

    def test_complex_status_stacking(self):
        """测试复杂状态叠加下的攻击力计算"""
        p = self.player
        p._atk = 10  # 基础攻击力 10
        
        # 1. 虚弱 (-2) -> 8
        p.apply_status(StatusName.WEAK.create_instance(duration=5, target=p))
        self.assertEqual(p.atk, 8)
        
        # 2. 攻击力提升 (+5) -> 8 + 5 = 13
        p.apply_status(StatusName.ATK_UP.create_instance(duration=5, target=p, value=5))
        self.assertEqual(p.atk, 13)
        
        # 3. 攻击力翻倍 (x2) -> 13 * 2 = 26
        p.apply_status(StatusName.ATK_MULTIPLIER.create_instance(duration=5, target=p, value=2))
        self.assertEqual(p.atk, 26)
        
        # 4. 清除所有状态
        p.statuses = {}
        self.assertEqual(p.atk, 10)

    def test_permanent_equipment_bonus(self):
        """测试永久装备加成是否正确修改基础攻击力"""
        from models.items import Equipment
        p = self.player
        initial_base_atk = p._atk
        
        sword = Equipment("测试长剑", atk_bonus=5)
        sword.effect(player=p)
        
        self.assertEqual(p._atk, initial_base_atk + 5)
        self.assertEqual(p.atk, initial_base_atk + 5)

if __name__ == '__main__':
    unittest.main()
