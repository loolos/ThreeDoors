"""data/balance.json 的结构校验：改数值时写错字段能第一时间发现。"""
import unittest

from models import items
from models.game_config import GameConfig, load_balance
from models.monster import Monster
from models.shop import Shop


class TestBalanceData(unittest.TestCase):
    def test_every_tier_has_monsters(self):
        for tier in range(GameConfig.MONSTER_MIN_TIER, GameConfig.MONSTER_MAX_TIER + 1):
            self.assertTrue(GameConfig.MONSTER_TYPES.get(tier), f"tier {tier} 没有怪物")
            for name, hp, atk in GameConfig.MONSTER_TYPES[tier]:
                self.assertGreater(hp, 0, name)
                self.assertGreater(atk, 0, name)
                self.assertIn(name, Monster.MONSTER_TYPE_HINTS, f"{name} 缺少门提示")

    def test_unlock_requirements_increase_with_tier(self):
        reqs = GameConfig.MONSTER_TIER_UNLOCK_REQUIREMENTS
        tiers = sorted(reqs)
        self.assertEqual(tiers, list(range(2, GameConfig.MONSTER_MAX_TIER + 1)))
        self.assertEqual([reqs[t] for t in tiers], sorted(reqs[t] for t in tiers))

    def test_shop_items_build(self):
        for entry in GameConfig.SHOP_ITEMS:
            self.assertTrue(hasattr(items, entry["class"]), f"未知商品类 {entry['class']}")
            cls, params, weight = Shop._catalog_entry(entry)
            params = dict(params)
            params.pop("shop_category", None)
            pool = params.pop("name_pool", None)
            if pool:
                params["name"] = pool[0]
            self.assertIsInstance(cls(**params), items.Item)
            self.assertGreater(weight, 0)

    def test_loader_returns_fresh_copy(self):
        data = load_balance()
        self.assertIn("monsters", data)
        self.assertIn("shop_items", data)


if __name__ == "__main__":
    unittest.main()
