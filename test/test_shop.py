import random

from models import items
from test.test_base import BaseTest


class TestShopGeneration(BaseTest):
    """商店生成测试"""

    @staticmethod
    def _category_of(item):
        if isinstance(item, items.HealingPotion):
            return "potion"
        if isinstance(item, items.Equipment):
            return "equipment"
        if isinstance(item, (items.FlyingHammer, items.Barrier, items.GiantScroll)):
            return "battle"
        return "scroll"

    def test_shop_items_contain_multiple_categories(self):
        """商店每次刷新应尽量包含多个类别，而非单一类别"""
        shop = self.controller.current_shop
        for gold in [1, 10, 50, 120]:
            self.player.gold = gold
            for seed in range(30):
                random.seed(seed + gold)
                shop.generate_items()
                categories = {self._category_of(item) for item in shop.shop_items}
                self.assertGreaterEqual(
                    len(categories),
                    2,
                    f"金币={gold}, seed={seed} 时类别过少: {categories}"
                )
