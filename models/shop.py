import random

class ShopLogic:
    def __init__(self):
        self.shop_items = []

    def generate_items(self, player):
        self.shop_items = []
        if player.gold == 0:
            return
        # 移除未使用的has_neg变量
        # 每个元组：名称, 类型, 效果值, 基准价格, 是否主动使用
        possible = [
            ("普通治疗药水", "heal", 10, 10, False),
            ("高级治疗药水", "heal", 20, 20, False),
            ("超高级治疗药水", "heal", 30, 30, False),
            ("普通装备", "weapon", 2, 15, False),
            ("稀有装备", "weapon", 5, 30, False),
            ("史诗装备", "weapon", 10, 50, False),
            ("传说装备", "weapon", 15, 75, False),
            ("复活卷轴", "revive", 1, 25, False),
            ("减伤卷轴", "damage_reduction", 2, 15, False),
            ("攻击力增益卷轴", "atk_up", random.randint(10, 20), 20, False),
            ("恢复卷轴", "healing_scroll", 0, 30, False),
            ("免疫卷轴", "immune", 0, 25, False),
            ("飞锤", "飞锤", 0, 20, True),
            ("结界", "结界", 0, 20, True),
            ("巨大卷轴", "巨大卷轴", 0, 20, True),
        ]
        # 如果金币不足10，则只显示低价物品或增益类（注意：主动使用的物品仍保留）
        if player.gold < 10:
            possible = [item for item in possible if item[3] <= 10 or item[1] in ("atk_up", "damage_reduction", "immune")]
        # 使用 random.sample 生成不重复的三件商品
        if len(possible) >= 3:
            items = random.sample(possible, 3)
        else:
            items = [random.choice(possible) for _ in range(3)]
        gold = player.gold
        for item in items:
            name, t, val, basep, active = item
            cost = random.randint(int(basep * 0.8), int(basep * 1.2))
            if gold <= 0:
                cost = 0
            else:
                cost = min(cost, gold)
            self.shop_items.append({
                "name": name,
                "type": t,
                "value": val,
                "cost": cost,
                "active": active
            })

    def purchase_item(self, idx, player):
        if idx < 0 or idx >= len(self.shop_items):
            player.controller.add_message("无效的购买选项!")
            return False
        item = self.shop_items[idx]
        if player.gold < item["cost"]:
            player.controller.add_message("你的金币不足, 无法购买!")
            return False
        # 如果物品为主动使用类型，检查库存是否已满（最多10个）
        if item["active"] and len(player.inventory) >= 10:
            player.controller.add_message("你的道具栏已满, 无法购买!")
            return False
            
        player.gold -= item["cost"]
        n, t, v, cost, active = item["name"], item["type"], item["value"], item["cost"], item["active"]
        
        if active:
            # 主动使用物品加入库存
            player.inventory.append(item.copy())
            player.controller.add_message(f"你花费 {cost} 金币, 购买了 {n}, 已存入道具栏!")
        else:
            # 非主动使用物品立即生效
            effect = player.apply_item_effect(t, v)
            player.controller.add_message(f"你花费 {cost} 金币, 购买了 {n}, {effect}!")
        
        return True 