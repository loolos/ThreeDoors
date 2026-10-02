
import shutil
import tempfile
import unittest
import json
from server import app, games_store
from scenes import SceneType

class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Clear games store（存档写到临时目录，避免污染 instance/）
        games_store.clear()
        self._orig_persist_dir = games_store.persist_dir
        games_store.persist_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(games_store.persist_dir, ignore_errors=True)
        games_store.persist_dir = self._orig_persist_dir
        
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
            from game import GameController
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

    def test_all_scenes_handle_choice(self):
        """/buttonAction 直接调用当前场景的 handle_choice：每个场景都必须实现它。"""
        from scenes import Scene
        for scene_cls in SceneType.get_name_scene_dict().values():
            self.assertTrue(issubclass(scene_cls, Scene))
            self.assertIsNot(scene_cls.handle_choice, Scene.handle_choice, f"{scene_cls.__name__} 未实现 handle_choice")

    def test_retried_action_is_not_applied_twice(self):
        """同一 action_id 的重试请求返回同一结果，回合数只推进一次。"""
        headers = {"X-Requested-With": "XMLHttpRequest"}
        with self.app as client:
            client.get("/getState", headers=headers)
            game = next(iter(games_store._games.values()))
            from models.door import DoorEnum
            game.scene_manager.current_scene.generate_doors([DoorEnum.TRAP, DoorEnum.TRAP, DoorEnum.TRAP])
            round_before = game.round_count
            first = client.post("/buttonAction", json={"index": 1, "action_id": "click-1"}, headers=headers).get_json()
            retry = client.post("/buttonAction", json={"index": 1, "action_id": "click-1"}, headers=headers).get_json()
            self.assertEqual(first, retry)
            self.assertEqual(game.round_count, round_before + 1)
            client.post("/buttonAction", json={"index": 0, "action_id": "click-2"}, headers=headers)
            self.assertGreaterEqual(game.round_count, round_before + 1)
            self.assertEqual(game.last_action_id, "click-2")

    def test_button_action_validates_index(self):
        """Invalid or out-of-range index should be clamped, not crash"""
        with self.app as client:
            client.get("/")
            with client.session_transaction() as sess:
                sess["game_id"] = "idx_test"
            from game import GameController
            games_store["idx_test"] = GameController()
            for bad_index in [{"index": -1}, {"index": 99}, {"index": "x"}, {}]:
                resp = client.post("/buttonAction", json=bad_index, headers={"X-Requested-With": "XMLHttpRequest"})
                self.assertEqual(resp.status_code, 200, f"bad payload {bad_index} should not crash")


class TestExitGameEndpoint(unittest.TestCase):
    """/exitGame 只在本地开发模式下、来自本机的请求才会关闭服务器进程。"""

    def setUp(self):
        self.client = app.test_client()
        games_store.clear()
        self._orig_dev_mode = app.config.get("DEV_MODE")
        self._orig_persist_dir = games_store.persist_dir
        games_store.persist_dir = tempfile.mkdtemp()

    def tearDown(self):
        app.config["DEV_MODE"] = self._orig_dev_mode
        shutil.rmtree(games_store.persist_dir, ignore_errors=True)
        games_store.persist_dir = self._orig_persist_dir

    def _post_exit(self, remote_addr):
        from unittest import mock
        self.client.get("/")
        with mock.patch("server.threading.Thread") as thread_cls:
            resp = self.client.post("/exitGame", environ_base={"REMOTE_ADDR": remote_addr})
        return resp, thread_cls

    def test_production_does_not_stop_server(self):
        app.config["DEV_MODE"] = False
        resp, thread_cls = self._post_exit("127.0.0.1")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["server_stopped"])
        thread_cls.assert_not_called()
        self.assertEqual(len(games_store), 0, "退出后应清除本局")

    def test_dev_mode_remote_request_does_not_stop_server(self):
        app.config["DEV_MODE"] = True
        resp, thread_cls = self._post_exit("192.168.1.23")
        self.assertFalse(resp.get_json()["server_stopped"])
        thread_cls.assert_not_called()

    def test_dev_mode_local_request_stops_server(self):
        app.config["DEV_MODE"] = True
        resp, thread_cls = self._post_exit("127.0.0.1")
        self.assertTrue(resp.get_json()["server_stopped"])
        thread_cls.assert_called_once()

    def test_index_hides_shutdown_wording_in_production(self):
        app.config["DEV_MODE"] = False
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("退出本局", html)
        self.assertNotIn("关闭游戏</button>", html)
