
import unittest
import json
from server import app, games_store
from scenes import SceneType

class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Clear games store
        games_store.clear()
        
    def test_event_scene_button_action(self):
        """Test API handling of EventScene button clicks"""
        # Start a game
        with self.app as client:
            client.get('/') # Init session
            
            # Use a fixed game ID
            game_id = 'test_game_123'
            with client.session_transaction() as sess:
                sess['game_id'] = game_id
            
            # Create game in store directly
            from server import GameController
            game = GameController()
            games_store[game_id] = game
            
            # Manually set up EventScene
            from models.events import StrangerEvent
            event = StrangerEvent(game)
            game.current_event = event
            game.scene_manager.current_scene = game.scene_manager.scene_dict["event_scene"]
            game.scene_manager.current_scene.on_enter()
            
            # Verify we are in EventScene
            self.assertEqual(game.scene_manager.current_scene.enum, SceneType.EVENT)
            
            # Send button action (Choice 2: Ignore - simplest)
            response = client.post('/buttonAction', 
                                 json={'index': 2},
                                 headers={'X-Requested-With': 'XMLHttpRequest'})
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['status'], 'success')
            
            # Verify scene transition (should go to DoorScene)
            # Use SceneType enum for comparison if possible, or check class name
            current_scene_enum = game.scene_manager.current_scene.enum
            self.assertEqual(current_scene_enum, SceneType.DOOR, 
                             f"API call failed to transition from EventScene. Current: {current_scene_enum}")

    def test_all_scenes_in_whitelist(self):
        """Ensure all defined scenes are handled by server.py whitelist logic"""
        from scenes import SceneType
        expected = {"DoorScene", "BattleScene", "ShopScene", "UseItemScene", "EndingSummaryScene", "EndingRollScene", "GameOverScene", "EventScene"}
        scene_names = {s.__name__ for s in SceneType.get_name_scene_dict().values()}
        for name in scene_names:
            self.assertIn(name, expected, f"Scene {name} must be in button_action whitelist")

    def test_button_action_validates_index(self):
        """Invalid or out-of-range index should be clamped, not crash"""
        with self.app as client:
            client.get("/")
            with client.session_transaction() as sess:
                sess["game_id"] = "idx_test"
            from server import GameController
            games_store["idx_test"] = GameController()
            for bad_index in [{"index": -1}, {"index": 99}, {"index": "x"}, {}]:
                resp = client.post("/buttonAction", json=bad_index, headers={"X-Requested-With": "XMLHttpRequest"})
                self.assertEqual(resp.status_code, 200, f"bad payload {bad_index} should not crash")
