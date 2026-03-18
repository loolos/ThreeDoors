"""商店逻辑：商品生成、价格浮动与购买。"""

from models.items import ItemType
from models import items
from models.game_config import GameConfig
import random


class Shop:
    """商店：根据玩家资金生成若干商品，支持购买与价格修正。"""
    SHOP_ITEM_COUNT = 3  # 商店物品数量
    SHOP_PRICE_MULTIPLIER = (0.8, 1.2)  # 价格浮动范围
    MAX_INVENTORY_SIZE = 10  # 最大物品栏数量

    def __init__(self, player):
        self.player = player
        self.shop_items = []
        # 一次性价格修正：由剧情后续效果挂入，在下一次刷新商品时生效。
        self.pending_price_ratio = 1.0
        self.generate_items()

    @staticmethod
    def _weighted_unique_choices(candidates, weights, count):
        """按权重无放回抽样，返回不重复结果。"""
        remaining_candidates = list(candidates)
        remaining_weights = list(weights)
        selected = []
        for _ in range(min(count, len(remaining_candidates))):
            picked = random.choices(remaining_candidates, weights=remaining_weights, k=1)[0]
            idx = remaining_candidates.index(picked)
            selected.append(remaining_candidates.pop(idx))
            remaining_weights.pop(idx)
        return selected

    def generate_items(self):
        """生成商店物品"""
        self.shop_items = []
        
        # 商店商品池：与 create_random_item() 的格式保持一致
        # (Class, Params, Weight)
        # 说明：
        # - Params 里的 cost 作为“基础价”，随后会应用 SHOP_PRICE_MULTIPLIER 浮动
        # - 用 shop_category 用于“尽量多类别”上架策略
        item_types = [
            (items.HealingPotion, {"name": "小治疗药水", "heal_amount": 10, "cost": 10, "shop_category": "potion"}, 20),
            (items.HealingPotion, {"name": "中治疗药水", "heal_amount": 20, "cost": 30, "shop_category": "potion"}, 15),
            (items.HealingPotion, {"name": "大治疗药水", "heal_amount": 30, "cost": 50, "shop_category": "potion"}, 10),
            (items.HealingPotion, {"name": "超级治疗药水", "heal_amount": 50, "cost": 80, "shop_category": "potion"}, 10),
            (items.Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[2], "atk_bonus": 2, "cost": 5, "shop_category": "equipment"}, 18),
            (items.Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[5], "atk_bonus": 5, "cost": 15, "shop_category": "equipment"}, 14),
            (items.Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[10], "atk_bonus": 10, "cost": 30, "shop_category": "equipment"}, 10),
            (items.Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[30], "atk_bonus": 30, "cost": 100, "shop_category": "equipment"}, 6),
            (items.Equipment, {"name_pool": GameConfig.EQUIPMENT_NAME_POOLS[50], "atk_bonus": 50, "cost": 200, "shop_category": "equipment"}, 3),
            (items.DamageReductionScroll, {"name": "减伤卷轴", "duration": 3, "cost": 40, "shop_category": "scroll"}, 12),
            (items.AttackUpScroll, {"name": "攻击力提升卷轴", "atk_bonus": 5, "duration": 5, "cost": 25, "shop_category": "scroll"}, 10),
            (items.ReviveScroll, {"name": "复活卷轴", "duration": 1, "cost": 40, "shop_category": "scroll"}, 6),
            (items.HealingScroll, {"name": "恢复卷轴", "duration": 5, "cost": 25, "shop_category": "scroll"}, 10),
            (items.ImmuneScroll, {"name": "免疫卷轴", "duration": 3, "cost": 30, "shop_category": "scroll"}, 8),
            (items.FlyingHammer, {"name": "飞锤", "duration": 3, "cost": 25, "shop_category": "battle"}, 7),
            (items.Barrier, {"name": "结界", "duration": 3, "cost": 30, "shop_category": "battle"}, 6),
            (items.GiantScroll, {"name": "巨大卷轴", "duration": 3, "cost": 35, "shop_category": "battle"}, 5),
        ]
        # 根据玩家资金水平计算目标价位：有钱时偏向高价，没钱时偏向低价
        target_cost = max(5, min(75, int(self.player.gold * 0.5)))
        def _get_base_cost(entry) -> int:
            _, params, _ = entry
            try:
                return int(params.get("cost", 0))
            except (TypeError, ValueError):
                return 0

        def score_weight(entry) -> float:
            """综合“目标价位靠近程度”与“池内权重”。"""
            _, params, base_weight = entry
            base_cost = _get_base_cost(entry)
            closeness = 1.0 / (1.0 + abs(base_cost - target_cost))
            try:
                w = float(base_weight)
            except (TypeError, ValueError):
                w = 1.0
            # 兼顾旧逻辑（偏向目标价位）与显式权重（稀有度）
            return max(0.0, w) * closeness

        # 先尽量保证“多类别”：每个选中类别先拿一件，再按权重补齐
        categories = {}
        for entry in item_types:
            _, params, _ = entry
            category = params.get("shop_category", "misc")
            categories.setdefault(category, []).append(entry)

        target_category_count = min(self.SHOP_ITEM_COUNT, len(categories))
        selected_data = []

        if target_category_count > 0:
            category_names = list(categories.keys())
            category_weights = [
                max(score_weight(candidate) for candidate in categories[name])
                for name in category_names
            ]
            selected_categories = self._weighted_unique_choices(
                category_names,
                category_weights,
                target_category_count
            )
            for category_name in selected_categories:
                category_candidates = categories[category_name]
                candidate_weights = [score_weight(candidate) for candidate in category_candidates]
                selected_data.append(
                    random.choices(category_candidates, weights=candidate_weights, k=1)[0]
                )

        remaining = [entry for entry in item_types if entry not in selected_data]
        remaining_count = self.SHOP_ITEM_COUNT - len(selected_data)
        if remaining_count > 0 and remaining:
            remaining_weights = [score_weight(entry) for entry in remaining]
            selected_data.extend(
                self._weighted_unique_choices(remaining, remaining_weights, remaining_count)
            )

        random.shuffle(selected_data)
        for entry in selected_data:
            item_class, base_params, _ = entry
            params = dict(base_params or {})

            base_cost = _get_base_cost(entry)
            # 计算实际价格（有浮动）
            cost = int(base_cost * random.uniform(*self.SHOP_PRICE_MULTIPLIER))
            params["cost"] = cost

            item_category = params.pop("shop_category", "misc")

            name_pool = params.pop("name_pool", None)
            if item_class is items.Equipment and name_pool and "name" not in params:
                params["name"] = random.choice(list(name_pool))

            item = item_class(**params)
            item.shop_category = item_category
            self.shop_items.append(item)
        if len(self.shop_items) < self.SHOP_ITEM_COUNT:
            self.shop_items = [
                items.HealingPotion("小治疗药水", heal_amount=5, cost=5),
                items.HealingPotion("中治疗药水", heal_amount=10, cost=10),
                items.HealingPotion("大治疗药水", heal_amount=15, cost=15)
            ]

        # -----------------------------
        # 保底机制：确保至少有一件商品买得起
        # -----------------------------
        if self.player.gold > 0 and self.shop_items:
            # 找到当前最便宜的物品
            cheapest_item = min(self.shop_items, key=lambda x: x.cost)
            
            # 如果连最便宜的都买不起
            if cheapest_item.cost > self.player.gold:
                # 强行降价
                cheapest_item.cost = self.player.gold
                # 可选：标记一下是打折商品
                cheapest_item.name = f"{cheapest_item.name} (促销)"

        # 将剧情挂入的下一次价格倍率应用到真正上架的商品。
        if self.pending_price_ratio != 1.0:
            self._apply_price_ratio_to_items(self.pending_price_ratio)
            self.pending_price_ratio = 1.0

    def queue_next_price_ratio(self, ratio):
        """将价格倍率挂到下一次刷新（可叠乘）。"""
        try:
            safe_ratio = float(ratio)
        except (TypeError, ValueError):
            return
        if safe_ratio <= 0:
            return
        self.pending_price_ratio *= safe_ratio

    def _apply_price_ratio_to_items(self, ratio):
        for item in self.shop_items:
            original = item.cost
            if ratio > 1:
                new_cost = max(1, int(original * ratio + 0.9999))
                if new_cost == original:
                    new_cost = original + 1
            elif ratio < 1:
                new_cost = max(1, int(original * ratio))
                if new_cost == original and original > 1:
                    new_cost = original - 1
            else:
                new_cost = original
            item.cost = max(1, new_cost)
            
    def purchase_item(self, idx):
        if idx < 0 or idx >= len(self.shop_items):
            self.player.controller.add_message("无效的购买选项!")
            return False
            
        item = self.shop_items[idx]
        if self.player.gold < item.cost:
            self.player.controller.add_message("你的金币不足, 无法购买!")
            return False
        # 检查物品栏是否已满，且物品不是消耗品
        if self.player.get_inventory_size() >= self.MAX_INVENTORY_SIZE and item.get_type() != ItemType.CONSUMABLE:
            self.player.controller.add_message("你的道具栏已满, 无法购买!")
            return False
            
        self.player.gold -= item.cost
        
        # 调用acquire方法处理物品
        item.acquire(player=self.player)
        self.player.controller.add_message(f"你花费 {item.cost} 金币, 购买了 {item.name}!")
        return True 