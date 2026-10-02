"""对局存储：内存 LRU 缓存 + 磁盘 pickle 持久化。

- 内存中最多保留 max_in_memory 局，超出时淘汰最久未访问的（磁盘上仍有存档）。
- persist_dir 非空时，每次 save() 把对局原子写入 <persist_dir>/<game_id>.pkl，
  服务重启或被淘汰后可从磁盘恢复；超过 ttl_seconds 未更新的存档会被清理。
- 存档无法读取（例如代码升级后类结构变化）时视为不存在，调用方会开新局。
"""
import os
import pickle
import re
import tempfile
import time
from collections import OrderedDict
from typing import Any, Optional

_GAME_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_valid_game_id(game_id: Any) -> bool:
    return isinstance(game_id, str) and bool(_GAME_ID_RE.match(game_id))


class GameStore:
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        max_in_memory: int = 200,
        ttl_seconds: int = 7 * 24 * 3600,
        prune_interval_seconds: int = 3600,
    ):
        self.persist_dir = persist_dir
        self.max_in_memory = max(1, int(max_in_memory))
        self.ttl_seconds = ttl_seconds
        self.prune_interval_seconds = prune_interval_seconds
        self._games: "OrderedDict[str, Any]" = OrderedDict()
        self._last_prune = 0.0

    # ---- 映射接口（便于路由与测试像 dict 一样使用） ----
    def __contains__(self, game_id: str) -> bool:
        return self.get(game_id) is not None

    def __getitem__(self, game_id: str) -> Any:
        game = self.get(game_id)
        if game is None:
            raise KeyError(game_id)
        return game

    def __setitem__(self, game_id: str, game: Any) -> None:
        if not is_valid_game_id(game_id):
            raise ValueError(f"invalid game id: {game_id!r}")
        self._games[game_id] = game
        self._games.move_to_end(game_id)
        self._evict_if_needed()

    def __len__(self) -> int:
        return len(self._games)

    def get(self, game_id: str, default: Any = None) -> Any:
        if not is_valid_game_id(game_id):
            return default
        game = self._games.get(game_id)
        if game is not None:
            self._games.move_to_end(game_id)
            return game
        game = self._load(game_id)
        if game is None:
            return default
        self[game_id] = game
        return game

    def pop(self, game_id: str, default: Any = None) -> Any:
        game = self._games.pop(game_id, None) if is_valid_game_id(game_id) else None
        path = self._path(game_id)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
        return game if game is not None else default

    def clear(self) -> None:
        """清空内存缓存（不删除磁盘存档）。"""
        self._games.clear()

    # ---- 持久化 ----
    def save(self, game_id: str) -> None:
        """把内存中的对局写盘；失败不影响游戏继续（仅内存保留）。"""
        game = self._games.get(game_id)
        path = self._path(game_id)
        if game is None or not path:
            return
        try:
            data = pickle.dumps(game, protocol=pickle.HIGHEST_PROTOCOL)
            os.makedirs(self.persist_dir, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=self.persist_dir, suffix=".tmp")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp_path, path)
        except Exception as exc:  # noqa: BLE001 - 存档失败只记录，不中断请求
            print(f"[GameStore] 保存对局 {game_id} 失败：{exc}")
        self._maybe_prune()

    def _path(self, game_id: str) -> Optional[str]:
        if not self.persist_dir or not is_valid_game_id(game_id):
            return None
        return os.path.join(self.persist_dir, f"{game_id}.pkl")

    def _load(self, game_id: str) -> Any:
        path = self._path(game_id)
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as fh:
                return pickle.load(fh)
        except Exception as exc:  # noqa: BLE001 - 旧版本或损坏的存档直接作废
            print(f"[GameStore] 读取对局 {game_id} 失败，作废该存档：{exc}")
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    def _evict_if_needed(self) -> None:
        while len(self._games) > self.max_in_memory:
            oldest_id = next(iter(self._games))
            self.save(oldest_id)  # 淘汰前确保落盘（未开启持久化时直接丢弃）
            self._games.pop(oldest_id, None)

    def _maybe_prune(self) -> None:
        now = time.time()
        if now - self._last_prune < self.prune_interval_seconds or not self.persist_dir:
            return
        self._last_prune = now
        try:
            names = os.listdir(self.persist_dir)
        except OSError:
            return
        for name in names:
            if not name.endswith(".pkl"):
                continue
            path = os.path.join(self.persist_dir, name)
            try:
                if now - os.path.getmtime(path) > self.ttl_seconds:
                    os.remove(path)
            except OSError:
                pass
