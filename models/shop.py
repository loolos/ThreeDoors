"""商店逻辑：商品生成、价格浮动与购买。"""

from models.items import ItemType
from models import items
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
        
        # 正常生成各种物品 (name, type, value, base_cost, category)
        possible = [
            ("小治疗药水", "heal", 5, 5, "potion"),
            ("中治疗药水", "heal", 10, 10, "potion"),
            ("大治疗药水", "heal", 15, 15, "potion"),
            ("垃圾装备", "weapon", 2, 5, "equipment"),
            ("普通装备", "weapon", 5, 15, "equipment"),
            ("精良装备", "weapon", 10, 30, "equipment"),
            ("史诗装备", "weapon", 15, 50, "equipment"),
            ("传说装备", "weapon", 20, 75, "equipment"),
            ("减伤卷轴", "damage_reduction", 3, 20, "scroll"),
            ("攻击力提升卷轴", "atk_up", 5, 25, "scroll"),
            ("复活卷轴", "revive", 1, 30, "scroll"),
            ("恢复卷轴", "healing_scroll", 5, 15, "scroll"),
            ("免疫卷轴", "immune", 3, 20, "scroll"),
            ("飞锤", "battle", 3, 25, "battle"),
            ("结界", "battle", 3, 30, "battle"),
            ("巨大卷轴", "battle", 3, 35, "battle"),
        ]
        # 根据玩家资金水平计算目标价位：有钱时偏向高价，没钱时偏向低价
        target_cost = max(5, min(75, int(self.player.gold * 0.5)))
        def cost_weight(item_data):
            return 1.0 / (1.0 + abs(item_data[3] - target_cost))

        # 先尽量保证“多类别”：每个选中类别先拿一件，再按权重补齐
        categories = {}
        for item_data in possible:
            categories.setdefault(item_data[4], []).append(item_data)

        target_category_count = min(self.SHOP_ITEM_COUNT, len(categories))
        selected_data = []

        if target_category_count > 0:
            category_names = list(categories.keys())
            category_weights = [
                max(cost_weight(candidate) for candidate in categories[name])
                for name in category_names
            ]
            selected_categories = self._weighted_unique_choices(
                category_names,
                category_weights,
                target_category_count
            )
            for category_name in selected_categories:
                category_candidates = categories[category_name]
                candidate_weights = [cost_weight(candidate) for candidate in category_candidates]
                selected_data.append(
                    random.choices(category_candidates, weights=candidate_weights, k=1)[0]
                )

        remaining = [item for item in possible if item not in selected_data]
        remaining_count = self.SHOP_ITEM_COUNT - len(selected_data)
        if remaining_count > 0 and remaining:
            remaining_weights = [cost_weight(item_data) for item_data in remaining]
            selected_data.extend(
                self._weighted_unique_choices(remaining, remaining_weights, remaining_count)
            )

        random.shuffle(selected_data)
        for item_data in selected_data:
            name, item_type, value, base_cost, item_category = item_data

            # 计算实际价格（有浮动）
            cost = int(base_cost * random.uniform(*self.SHOP_PRICE_MULTIPLIER))
            
            # 如果玩家金币不足，跳过这个物品 -> removed

                
            # 创建物品
            if item_type == "heal":
                item = items.HealingPotion(name, heal_amount=value, cost=cost)
            elif item_type == "weapon":
                item = items.Equipment(name, atk_bonus=value, cost=cost)
            elif item_type == "damage_reduction":
                item = items.DamageReductionScroll(name, cost=cost, duration=value)
            elif item_type == "atk_up":
                item = items.AttackUpScroll(name, atk_bonus=value, cost=cost, duration=value)
            elif item_type == "revive":
                item = items.ReviveScroll(name, cost=cost, duration=value)
            elif item_type == "healing_scroll":
                item = items.HealingScroll(name, cost=cost, duration=value)
            elif item_type == "immune":
                item = items.ImmuneScroll(name, cost=cost, duration=value)
            elif item_type == "battle":
                if name == "飞锤":
                    item = items.FlyingHammer(name, cost=cost, duration=3)
                elif name == "结界":
                    item = items.Barrier(name, cost=cost, duration=3)
                elif name == "巨大卷轴":
                    item = items.GiantScroll(name, cost=cost, duration=3)
            else:
                raise ValueError(f"未知的物品类型: {item_type}")

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