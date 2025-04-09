from models.items import ItemType
from models import items
import random

class Shop:
    # 商店配置
    SHOP_ITEM_COUNT = 3  # 商店物品数量
    SHOP_PRICE_MULTIPLIER = (0.8, 1.2)  # 价格浮动范围
    MAX_INVENTORY_SIZE = 10  # 最大物品栏数量

    def __init__(self, player):
        self.player = player
        self.shop_items = []
        self.generate_items()

    def generate_items(self):
        """生成商店物品"""
        self.shop_items = []
        
        # 根据玩家金币决定生成物品的类型
        if self.player.gold < 10:
            # 如果金币很少，只生成便宜的治疗药水
            possible = [
                ("小治疗药水", "heal", 5, 5, ItemType.CONSUMABLE),
                ("中治疗药水", "heal", 10, 10, ItemType.CONSUMABLE),
                ("垃圾装备", "weapon", 2, 5, ItemType.CONSUMABLE),
                ("普通装备", "weapon", 5, 15, ItemType.CONSUMABLE),
                ("飞锤", "battle", 3, 25, ItemType.BATTLE),
                ("结界", "battle", 3, 30, ItemType.BATTLE),
                ("巨大卷轴", "battle", 3, 35, ItemType.BATTLE),
            ]
        else:
            # 正常生成各种物品
            possible = [
                ("小治疗药水", "heal", 5, 5, ItemType.CONSUMABLE),
                ("中治疗药水", "heal", 10, 10, ItemType.CONSUMABLE),
                ("大治疗药水", "heal", 15, 15, ItemType.CONSUMABLE),
                ("垃圾装备", "weapon", 2, 5, ItemType.CONSUMABLE),
                ("普通装备", "weapon", 5, 15, ItemType.CONSUMABLE),
                ("精良装备", "weapon", 10, 30, ItemType.CONSUMABLE),
                ("史诗装备", "weapon", 15, 50, ItemType.CONSUMABLE),
                ("传说装备", "weapon", 20, 75, ItemType.CONSUMABLE),
                ("减伤卷轴", "damage_reduction", 3, 20, ItemType.CONSUMABLE),
                ("攻击力提升卷轴", "atk_up", 5, 25, ItemType.CONSUMABLE),
                ("复活卷轴", "revive", 1, 30, ItemType.PASSIVE),
                ("恢复卷轴", "healing_scroll", 5, 15, ItemType.CONSUMABLE),
                ("免疫卷轴", "immune", 3, 20, ItemType.CONSUMABLE),
                ("飞锤", "battle", 3, 25, ItemType.BATTLE),
                ("结界", "battle", 3, 30, ItemType.BATTLE),
                ("巨大卷轴", "battle", 3, 35, ItemType.BATTLE),
            ]
            
        # 随机选择物品
        while len(self.shop_items) < self.SHOP_ITEM_COUNT and possible:
            item_data = random.choice(possible)
            name, item_type, value, base_cost, item_category = item_data
            
            # 计算实际价格（有浮动）
            cost = int(base_cost * random.uniform(*self.SHOP_PRICE_MULTIPLIER))
            
            # 如果玩家金币不足，跳过这个物品
            if cost > self.player.gold:
                possible.remove(item_data)
                continue
                
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

            self.shop_items.append({
                "name": name,
                "type": item_type,
                "value": value,
                "cost": cost,
                "category": item_category,
                "item": item
            })
                
    def purchase_item(self, idx):
        if idx < 0 or idx >= len(self.shop_items):
            self.player.controller.add_message("无效的购买选项!")
            return False
            
        item_data = self.shop_items[idx]
        if self.player.gold < item_data["cost"]:
            self.player.controller.add_message("你的金币不足, 无法购买!")
            return False
            
        item = item_data["item"]
        # 检查物品栏是否已满，且物品不是消耗品
        if self.player.get_inventory_size() >= self.MAX_INVENTORY_SIZE and item.get_type() != ItemType.CONSUMABLE:
            self.player.controller.add_message("你的道具栏已满, 无法购买!")
            return False
            
        self.player.gold -= item_data["cost"]
        
        # 调用acquire方法处理物品
        item.acquire(player=self.player)
        self.player.controller.add_message(f"你花费 {item_data['cost']} 金币, 购买了 {item.name}!")
        return True 