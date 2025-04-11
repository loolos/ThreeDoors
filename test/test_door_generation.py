import unittest
from server import GameController, DoorScene

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