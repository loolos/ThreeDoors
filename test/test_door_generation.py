import unittest
from server import GameController, DoorScene
from models.door import DoorEnum, MonsterDoor, ShopDoor, TrapDoor, RewardDoor

class TestDoorGeneration(unittest.TestCase):
    """测试门生成系统"""
    
    def setUp(self):
        self.controller = GameController()
        self.controller.scene_manager.go_to("door_scene")
        self.door_scene = self.controller.scene_manager.current_scene

    def test_door_generation(self):
        """测试门生成"""
        self.door_scene.generate_doors()
        self.assertEqual(len(self.door_scene.doors), 3)
        
        # 检查是否至少有一扇怪物门
        monster_doors = [door for door in self.door_scene.doors if door.event == "monster"]
        self.assertGreater(len(monster_doors), 0)

    def test_generate_doors(self):
        """测试生成门"""
        # 测试生成特定类型的门
        door_types = [DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP]
        self.door_scene.generate_doors(door_types)
        
        # 验证门的类型
        self.assertIsInstance(self.door_scene.doors[0], MonsterDoor)
        self.assertIsInstance(self.door_scene.doors[1], ShopDoor)
        self.assertIsInstance(self.door_scene.doors[2], TrapDoor)
        
        # 测试生成随机门
        self.door_scene.generate_doors()
        for door in self.door_scene.doors:
            self.assertTrue(
                DoorEnum.is_valid_door_type(door.enum),
                f"Invalid door type: {type(door)}"
            )
    
    def test_door_hints(self):
        """测试门提示"""
        door_types = [DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP]
        self.door_scene.generate_doors(door_types)
        
        # 验证每个门都有提示
        for door in self.door_scene.doors:
            hint = door.generate_hint()
            self.assertIsInstance(hint, str)
            self.assertTrue(len(hint) > 0)