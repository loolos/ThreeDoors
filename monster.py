import random

class Monster:
    def __init__(self, name, hp, atk, tier=1):
        self.name = name
        self.hp = hp
        self.atk = atk
        self.tier = tier
        self.statuses = {}  # 使用状态系统来管理怪物的状态效果
        self.loot = self.generate_loot()  # 生成掉落物品

    def generate_loot(self):
        """生成怪物的掉落物品"""
        loot = []
        # 基础金币掉落，随怪物等级提升
        base_gold = random.randint(5, 15) * self.tier
        loot.append(("gold", base_gold))
        
        # 根据怪物等级决定额外掉落
        if self.tier >= 2:
            # Tier 2怪物有40%概率获得装备，装备加成随等级提升
            if random.random() < 0.4:
                equip_boost = random.randint(2, 5) * self.tier
                loot.append(("equip", equip_boost))
            
            # Tier 2怪物有20%概率获得卷轴
            if random.random() < 0.2:
                scroll_type = random.choice([
                    ("healing_scroll", "恢复卷轴", 10),
                    ("damage_reduction", "减伤卷轴", random.randint(10, 20)),
                    ("atk_up", "攻击力增益卷轴", 10),
                ])
                loot.append(("scroll", scroll_type))
        
        if self.tier >= 3:
            # Tier 3怪物有60%概率获得装备，装备加成更高
            if random.random() < 0.6:
                equip_boost = random.randint(3, 7) * self.tier
                loot.append(("equip", equip_boost))
            
            # Tier 3怪物有40%概率获得卷轴，卷轴效果更好
            if random.random() < 0.4:
                scroll_type = random.choice([
                    ("healing_scroll", "恢复卷轴", 15),
                    ("damage_reduction", "减伤卷轴", random.randint(15, 25)),
                    ("atk_up", "攻击力增益卷轴", 15),
                ])
                loot.append(("scroll", scroll_type))
        
        if self.tier >= 4:
            # Tier 4怪物有80%概率获得装备，装备加成最高
            if random.random() < 0.8:
                equip_boost = random.randint(5, 10) * self.tier
                loot.append(("equip", equip_boost))
            
            # Tier 4怪物有60%概率获得卷轴，卷轴效果最好
            if random.random() < 0.6:
                scroll_type = random.choice([
                    ("healing_scroll", "恢复卷轴", 20),
                    ("damage_reduction", "减伤卷轴", random.randint(20, 30)),
                    ("atk_up", "攻击力增益卷轴", 20),
                ])
                loot.append(("scroll", scroll_type))
            
            # Tier 4怪物有30%概率获得额外金币
            if random.random() < 0.3:
                extra_gold = random.randint(20, 40) * self.tier
                loot.append(("gold", extra_gold))
            
        return loot

    def get_loot(self):
        """获取怪物的掉落物品"""
        return self.loot

    def take_damage(self, dmg):
        self.hp -= dmg

    def apply_status(self, status_name, duration):
        """应用状态效果"""
        self.statuses[status_name] = {"duration": duration}

    def has_status(self, status_name):
        """检查是否有特定状态"""
        return status_name in self.statuses and self.statuses[status_name]["duration"] > 0

    def update_statuses(self):
        """更新状态持续时间"""
        expired = []
        for status in self.statuses:
            self.statuses[status]["duration"] -= 1
            if self.statuses[status]["duration"] <= 0:
                expired.append(status)
        for status in expired:
            del self.statuses[status]

    def attack(self, target):
        """怪物攻击目标"""
        # 检查是否晕眩
        if self.has_status("stun"):
            self.update_statuses()
            return [f"{self.name} 被晕眩，无法反击!"], False

        # 检查目标是否有结界
        if "barrier" in target.statuses and target.statuses["barrier"]["duration"] > 0:
            return [f"{self.name} 的攻击被结界挡住了!"], False

        # 计算伤害
        mdmg = max(1, self.atk - random.randint(0, 1))
        if "damage_reduction" in target.statuses:
            original_dmg = mdmg
            mdmg = int(mdmg * 0.25)  # 减少75%伤害
            msg = [f"一部分伤害被减伤卷轴挡掉了！"]
        else:
            msg = []
            
        # 造成伤害
        target.take_damage(mdmg)
        msg.append(f"{self.name} 反击造成 {mdmg} 点伤害.")

        # 检查目标是否死亡
        if target.hp <= 0:
            revived = target.try_revive()
            if revived:
                msg.append("复活卷轴救了你(HP=1)!")
            else:
                msg.append("你被怪物击倒, 英勇牺牲!")

        # 较强怪物可能附带负面效果
        if self.tier >= 3 and random.random() < 0.3:
            effect = random.choice(["weak", "poison", "stun"])
            duration = random.randint(1, 2)
            target.statuses[effect] = {"duration": duration}
            msg.append(f"{self.name} 附带 {effect} 效果 ({duration}回合)!")

        return msg, False

def get_random_monster(max_tier=None, current_round=None):
    monster_pool = [
        # Tier 1 - 新手怪物
        Monster("史莱姆", 15, 4, 1),
        Monster("哥布林", 20, 5, 1),
        Monster("狼", 18, 6, 1),
        Monster("蜘蛛", 16, 5, 1),
        Monster("蝙蝠", 14, 4, 1),
        Monster("小骷髅", 17, 5, 1),
        
        # Tier 2 - 中级怪物
        Monster("小恶魔", 25, 7, 2),
        Monster("牛头人", 35, 9, 2),
        Monster("食人花", 30, 8, 2),
        Monster("蜥蜴人", 28, 7, 2),
        Monster("石像鬼", 32, 8, 2),
        Monster("半人马", 38, 10, 2),
        
        # Tier 3 - 高级怪物
        Monster("巨龙", 40, 10, 3),
        Monster("暗黑骑士", 50, 12, 3),
        Monster("九头蛇", 45, 11, 3),
        Monster("独眼巨人", 48, 13, 3),
        Monster("地狱犬", 42, 12, 3),
        Monster("巫妖", 55, 14, 3),
        
        # Tier 4 - 精英怪物
        Monster("末日领主", 70, 15, 4),
        Monster("深渊魔王", 75, 18, 4),
        Monster("混沌使者", 65, 16, 4),
        Monster("虚空领主", 80, 20, 4),
        Monster("死亡骑士", 72, 17, 4),
        Monster("远古巨龙", 85, 22, 4),
    ]
    
    # 根据回合数限制怪物等级
    if max_tier is None and current_round is not None:
        if current_round <= 5:
            max_tier = 1  # 前5回合只出现Tier 1怪物
        elif current_round <= 10:
            max_tier = 2  # 6-10回合可能出现Tier 2怪物
        elif current_round <= 15:
            max_tier = 3  # 11-15回合可能出现Tier 3怪物
        else:
            max_tier = 4  # 15回合后可能出现所有怪物
    elif max_tier is None:
        max_tier = 1  # 默认使用Tier 1
    
    # 过滤出符合条件的怪物
    filtered = [m for m in monster_pool if m.tier <= max_tier]
    if filtered:
        monster_pool = filtered
    
    return random.choice(monster_pool) 