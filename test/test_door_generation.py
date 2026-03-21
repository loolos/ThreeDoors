import unittest
import unittest.mock
from models.door import Door, DoorEnum, HINT_CONFIGS, get_mixed_door_hint
from test.test_base import BaseTest

class TestDoorGeneration(BaseTest):
    """测试门生成"""
    
    def test_door_generation(self):
        """测试门生成"""
        # 生成门
        self.controller.scene_manager.current_scene.generate_doors()
        
        # 验证门数量
        self.assertEqual(len(self.controller.scene_manager.current_scene.doors), 3)
        
        # 验证门类型
        door_types = [door.enum for door in self.controller.scene_manager.current_scene.doors]
        self.assertEqual(sum(door_type == DoorEnum.MONSTER for door_type in door_types), 1)
        self.assertEqual(len(set(door_types)), 3)
        
    def test_door_hints(self):
        """测试门提示"""
        # 生成指定类型的门
        door_types = [DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP]
        self.controller.scene_manager.current_scene.generate_doors(door_types)
        
        # 验证提示
        for door in self.controller.scene_manager.current_scene.doors:
            self.assertIsNotNone(door.hint)
            self.assertNotEqual(door.hint, "")
            
    def test_enter_door(self):
        """测试进入门"""
        # 生成门
        door_types = [DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP]
        self.controller.scene_manager.current_scene.generate_doors(door_types)
        hp = self.controller.player.hp
        
        # 测试进入每个门
        for door in self.controller.scene_manager.current_scene.doors:
            # 记录进入前的 HP
            hp_before = self.controller.player.hp
            
            if door.enum == DoorEnum.MONSTER:
                door.enter()
                self.assertIsNotNone(self.controller.current_monster)
            elif door.enum == DoorEnum.SHOP:
                door.enter()
                self.assertIsNotNone(self.controller.current_shop)
            elif door.enum == DoorEnum.TRAP:
                import unittest.mock
                with unittest.mock.patch('random.choice', return_value='spike'):
                    door.enter()
                self.assertLess(self.controller.player.hp, hp_before)
            else:
                door.enter()

    def test_singleton_hint_set_does_not_crash(self):
        """单元素集合提示应正常返回字符串"""
        hint = get_mixed_door_hint(frozenset({DoorEnum.MONSTER}))
        self.assertIsInstance(hint, str)
        self.assertNotEqual(hint, "")

    def test_combo_hint_returns_string(self):
        """双元素组合提示应正常返回字符串"""
        hint = get_mixed_door_hint(frozenset({DoorEnum.MONSTER, DoorEnum.SHOP}))
        self.assertIsInstance(hint, str)
        self.assertNotEqual(hint, "")

    def test_combo_hint_avoids_immediate_repeat(self):
        """同一组合提示池应尽量避免连续重复同一句。"""
        key = frozenset({DoorEnum.EVENT, DoorEnum.SHOP})
        with unittest.mock.patch("random.randint", return_value=0), unittest.mock.patch("random.choice", side_effect=lambda seq: seq[0]):
            first = get_mixed_door_hint(key)
            second = get_mixed_door_hint(key)
        self.assertNotEqual(first, second)

    def test_each_combo_hint_pool_has_richer_candidates(self):
        """每个双门组合都应提供更多候选提示，避免体感单一。"""
        for key, hints in HINT_CONFIGS["combo"].items():
            self.assertEqual(len(key), 2)
            self.assertGreaterEqual(len(hints), 8, msg=f"组合 {key} 的提示过少")

if __name__ == '__main__':
    unittest.main()
