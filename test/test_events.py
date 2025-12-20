
import unittest
import unittest.mock
from test.test_base import BaseTest
from models.door import DoorEnum, EventDoor
from scenes import SceneType
from models.events import (
    StrangerEvent, SmugglerEvent, AncientShrineEvent, 
    GamblerEvent, LostChildEvent, CursedChestEvent, WiseSageEvent,
    get_random_event
)

class TestEvents(BaseTest):
    
    def test_event_door_creation(self):
        """测试事件门创建"""
        door = DoorEnum.EVENT.create_instance(controller=self.controller)
        self.assertIsInstance(door, EventDoor)
        self.assertEqual(door.enum, DoorEnum.EVENT)
        
    def test_event_door_enter(self):
        """测试进入事件门"""
        door = DoorEnum.EVENT.create_instance(controller=self.controller)
        door.enter()
        
        self.assertIsNotNone(self.controller.current_event)
        self.assertEqual(self.controller.scene_manager.current_scene.enum, SceneType.EVENT)
        
    @unittest.mock.patch('models.events.create_random_item')
    def test_stranger_event(self, mock_create):
        """测试陌生人事件"""
        # Mock item to be a Battle Item so it goes to inventory
        from models.items import FlyingHammer
        mock_create.return_value = FlyingHammer("TestHammer")
        
        event = StrangerEvent(self.controller)
        self.controller.current_event = event
        
        # 1. Test Help (Choice 0) - Need Gold
        self.player.gold = 20
        msg = event.resolve_choice(0)
        self.assertEqual(self.player.gold, 10) # Cost 10
        # Now inventory should increase
        self.assertTrue(self.player.get_inventory_size() > 0) 
        
        # 2. Test Rob (Choice 1)
        initial_gold = self.player.gold
        event.resolve_choice(1)
        self.assertTrue(self.player.gold > initial_gold)
        
    def test_smuggler_event(self):
        """测试走私犯事件"""
        event = SmugglerEvent(self.controller)
        # Manually set a battle item to ensure inventory interaction
        from models.items import FlyingHammer
        event.item = FlyingHammer("TestHammer", cost=10)
        event.cost = 5
        
        self.controller.current_event = event
        
        # Ensure player has gold
        self.player.gold = 20
        
        # Buy Item
        initial_inv = self.player.get_inventory_size()
        event.resolve_choice(0)
        self.assertEqual(self.player.get_inventory_size(), initial_inv + 1)
        self.assertEqual(self.player.gold, 15) # 20 - 5

        
    def test_gambler_event(self):
        """测试赌徒事件"""
        event = GamblerEvent(self.controller)
        self.controller.current_event = event
        
        # Low Stakes
        self.player.gold = 20
        # Mock random to ensure win or loss? 
        # Since logic uses random inside, we can just check gold changed is +/- 10 or +20
        # But hard to assert exact value without patching random.
        # Just ensure it runs without error for now.
        event.resolve_choice(1) 
        self.assertNotEqual(self.player.gold, 20) # Only unchanged if logic failed, but actually win=lose=10 diff?
        # If win: +10 profit (20-10+20=30). If lose: -10 (20-10=10). So definitely not 20.
        
    def test_sage_event(self):
        """测试贤者事件"""
        event = WiseSageEvent(self.controller)
        self.controller.current_event = event
        
        # Power
        initial_atk = self.player.atk
        event.resolve_choice(0)
        self.assertEqual(self.player.atk, initial_atk + 3)
        
        # Wealth
        initial_gold = self.player.gold
        event.resolve_choice(1)
        self.assertEqual(self.player.gold, initial_gold + 200)

    def test_event_scene_ui(self):
        """测试事件场景UI"""
        event = StrangerEvent(self.controller)
        self.controller.current_event = event
        
        scene = self.controller.scene_manager.scene_dict["event_scene"]
        self.controller.scene_manager.current_scene = scene
        scene.on_enter()
        
        # Verify buttons match event choices
        choices = event.get_choices()
        self.assertEqual(scene.button_texts[0], choices[0])
        self.assertEqual(scene.button_texts[1], choices[1])
        self.assertEqual(scene.button_texts[2], choices[2])
        
