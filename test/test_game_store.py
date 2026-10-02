import os
import shutil
import tempfile
import unittest

from game import GameController
from game_store import GameStore, is_valid_game_id
from server import app, games_store


class TestGameStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _played_game(self, rounds=5):
        game = GameController()
        for _ in range(rounds):
            scene = game.scene_manager.current_scene
            if scene.enum.name == "GAME_OVER":
                break
            scene.handle_choice(0)
            game.clear_messages()
        return game

    def test_saved_game_survives_new_store_instance(self):
        store = GameStore(persist_dir=self.dir)
        game = self._played_game()
        store["abc123"] = game
        store.save("abc123")

        restarted = GameStore(persist_dir=self.dir)
        restored = restarted.get("abc123")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.round_count, game.round_count)
        self.assertEqual(restored.player.hp, game.player.hp)
        # 反向引用在反序列化后仍指向同一个控制器
        self.assertIs(restored.player.controller, restored)
        self.assertIs(restored.scene_manager.current_scene.controller, restored)

    def test_eviction_keeps_game_on_disk(self):
        store = GameStore(persist_dir=self.dir, max_in_memory=2)
        for gid in ("g1", "g2", "g3"):
            store[gid] = GameController()
        self.assertEqual(len(store), 2)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "g1.pkl")))
        self.assertIsNotNone(store.get("g1"))

    def test_eviction_without_persistence_drops_oldest(self):
        store = GameStore(persist_dir=None, max_in_memory=1)
        store["g1"] = GameController()
        store["g2"] = GameController()
        self.assertIsNone(store.get("g1"))
        self.assertIsNotNone(store.get("g2"))

    def test_corrupted_save_is_discarded(self):
        path = os.path.join(self.dir, "bad.pkl")
        with open(path, "wb") as fh:
            fh.write(b"not a pickle")
        store = GameStore(persist_dir=self.dir)
        self.assertIsNone(store.get("bad"))
        self.assertFalse(os.path.exists(path))

    def test_invalid_ids_never_touch_disk(self):
        store = GameStore(persist_dir=self.dir)
        for bad in ("../etc/passwd", "", None, "a/b", "x" * 100):
            self.assertFalse(is_valid_game_id(bad))
            self.assertIsNone(store.get(bad))
        with self.assertRaises(ValueError):
            store["../x"] = GameController()

    def test_pop_removes_save(self):
        store = GameStore(persist_dir=self.dir)
        store["gone"] = GameController()
        store.save("gone")
        store.pop("gone")
        self.assertIsNone(GameStore(persist_dir=self.dir).get("gone"))


class TestServerResumesAfterRestart(unittest.TestCase):
    def setUp(self):
        self._orig_dir = games_store.persist_dir
        games_store.persist_dir = tempfile.mkdtemp()
        games_store.clear()
        self.client = app.test_client()

    def tearDown(self):
        shutil.rmtree(games_store.persist_dir, ignore_errors=True)
        games_store.persist_dir = self._orig_dir
        games_store.clear()

    def test_progress_restored_from_disk(self):
        headers = {"X-Requested-With": "XMLHttpRequest"}
        self.client.get("/getState", headers=headers)
        for _ in range(3):
            self.client.post("/buttonAction", json={"index": 0}, headers=headers)
        before = self.client.get("/getState", headers=headers).get_json()["round"]
        self.assertGreater(before, 0)

        games_store.clear()  # 模拟服务重启：内存缓存清空，只剩磁盘存档
        after = self.client.get("/getState", headers=headers).get_json()["round"]
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
