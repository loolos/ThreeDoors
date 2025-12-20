
import unittest
import unittest.mock
from test.test_base import BaseTest
from models.events import (
    StrangerEvent, SmugglerEvent, AncientShrineEvent, 
    GamblerEvent, LostChildEvent, CursedChestEvent, WiseSageEvent
)
from models.items import FlyingHammer

class TestAllEvents(BaseTest):
    
    def _run_choice(self, event_cls, choice_index, setup_func=None):
        """Helper to run a specific choice of an event"""
        event = event_cls(self.controller)
        self.controller.current_event = event
        
        if setup_func:
            setup_func(event, self.player)
            
        print(f"Testing {event.title} Choice {choice_index}...")
        try:
            event.resolve_choice(choice_index)
        except Exception as e:
            self.fail(f"{event.title} Choice {choice_index} raised exception: {e}")

    @unittest.mock.patch('models.events.create_random_item')
    def test_stranger_choices(self, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")
        
        # 0: Help (needs gold)
        self._run_choice(StrangerEvent, 0, lambda e, p: setattr(p, 'gold', 20))
        # 0: Help (no gold)
        self._run_choice(StrangerEvent, 0, lambda e, p: setattr(p, 'gold', 0))
        # 1: Rob
        self._run_choice(StrangerEvent, 1)
        # 2: Ignore
        self._run_choice(StrangerEvent, 2)

    @unittest.mock.patch('models.events.create_random_item')
    def test_smuggler_choices(self, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")

        # 0: Buy (needs gold)
        self._run_choice(SmugglerEvent, 0, lambda e, p: setattr(p, 'gold', 100))
        # 0: Buy (no gold)
        self._run_choice(SmugglerEvent, 0, lambda e, p: setattr(p, 'gold', 0))
        # 1: Report
        self._run_choice(SmugglerEvent, 1)
        # 2: Leave
        self._run_choice(SmugglerEvent, 2)

    @unittest.mock.patch('models.events.create_random_item')
    def test_shrine_choices(self, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")
        # 0: Pray
        self._run_choice(AncientShrineEvent, 0)
        # 1: Desecrate
        self._run_choice(AncientShrineEvent, 1)
        # 2: Inspect
        self._run_choice(AncientShrineEvent, 2)

    def test_gambler_choices(self):
        # 0: High Stakes
        self._run_choice(GamblerEvent, 0, lambda e, p: setattr(p, 'gold', 100))
        # 1: Low Stakes
        self._run_choice(GamblerEvent, 1, lambda e, p: setattr(p, 'gold', 100))
        # 2: Decline
        self._run_choice(GamblerEvent, 2)

    def test_lost_child_choices(self):
        # 0: Guide Home (might trigger damage)
        self._run_choice(LostChildEvent, 0)
        # 1: Give Gold
        self._run_choice(LostChildEvent, 1, lambda e, p: setattr(p, 'gold', 100))
        # 2: Ignore
        self._run_choice(LostChildEvent, 2)

    @unittest.mock.patch('models.events.create_random_item')
    def test_cursed_chest_choices(self, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")
        # 0: Open
        self._run_choice(CursedChestEvent, 0)
        # 1: Purify
        self._run_choice(CursedChestEvent, 1)
        # 2: Leave
        self._run_choice(CursedChestEvent, 2)

    def test_death_in_event(self):
        """Test if player dies during event, scene stays GameOver"""
        # Force low HP
        self.player.hp = 1
        # Remove Revive Scroll to ensure death
        self.player.clear_inventory()
        
        # Lost Child Event choice 0 has 30% chance to deal 15 dmg.
        # We need to force that path. But it uses random.random().
        # We can patch random.random in models.events
        
        with unittest.mock.patch('models.events.random.random') as mock_rand:
            mock_rand.return_value = 0.1 # < 0.3 triggers damage path
            
            # Setup scene manager to simulate real flow
            event = LostChildEvent(self.controller)
            self.controller.current_event = event
            
            # Manually simulate Scene flow
            scene = self.controller.scene_manager.scene_dict["event_scene"]
            self.controller.scene_manager.current_scene = scene
            
            # Trigger choice 0
            print("Triggering Choice 0 (Guide Home)...")
            scene.handle_choice(0)
            
            # Verify we are in GAME_OVER, NOT DOOR_SCENE
            from scenes import SceneType
            print(f"Scene after death: {self.controller.scene_manager.current_scene.enum}")
            print(f"Player HP: {self.player.hp}")
            self.assertEqual(self.controller.scene_manager.current_scene.enum, SceneType.GAME_OVER)

    def test_sage_choices(self):
        # 0: Power
        self._run_choice(WiseSageEvent, 0)
        # 1: Wealth
        self._run_choice(WiseSageEvent, 1)
        # 2: Health
        self._run_choice(WiseSageEvent, 2)
