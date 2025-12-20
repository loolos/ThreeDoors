import unittest
from models.door import Door, DoorEnum
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
        self.assertTrue(any(door_type == DoorEnum.MONSTER for door_type in door_types))
        
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

if __name__ == '__main__':
    unittest.main()