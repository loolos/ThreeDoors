import random

class Monster:
    def __init__(self, name, hp, atk, tier=1):
        self.name = name
        self.hp = hp
        self.atk = atk
        self.tier = tier
        self.statuses = {}  # 使用状态系统来管理怪物的状态效果
        self.loot = self._generate_loot()  # 生成掉落物品

    def _generate_loot(self):
        """生成怪物的掉落物品"""
        loot = []
        # 基础金币掉落，随怪物等级提升
        base_gold = random.randint(5, 15) * self.tier
        loot.append(("gold", base_gold))
        
        # 根据怪物等级决定额外掉落
        if self.tier >= 2:
            # Tier 2及以上怪物有50%概率获得装备
            if random.random() < 0.5:
                equip_boost = 2 * self.tier  # 装备加成固定为2倍等级
                loot.append(("equip", equip_boost))
            
            # Tier 2及以上怪物有30%概率获得卷轴
            if random.random() < 0.3:
                scroll_type = random.choice([
                    ("healing_scroll", "恢复卷轴", 5 * self.tier),  # 恢复值随等级提升
                    ("damage_reduction", "减伤卷轴", 10 * self.tier),  # 减伤值随等级提升
                    ("atk_up", "攻击力增益卷轴", 5 * self.tier),  # 攻击力加成随等级提升
                ])
                loot.append(("scroll", scroll_type))
        
        return loot

    def get_loot(self):
        """获取怪物的掉落物品"""
        return self.loot

    def process_loot(self, player):
        """处理怪物的掉落物品，应用到玩家身上"""
        for item_type, value in self.loot:
            if item_type == "gold":
                player.add_gold(value)
                if hasattr(player, 'controller') and player.controller:
                    player.controller.add_message(f"获得 {value} 金币")
            elif item_type == "equip":
                player.atk += value
                if hasattr(player, 'controller') and player.controller:
                    player.controller.add_message(f"获得装备，攻击力提升 {value} 点")
            elif item_type == "scroll":
                scroll_name, scroll_desc, scroll_value = value
                effect_msg = player.apply_item_effect(scroll_name, scroll_value)
                if hasattr(player, 'controller') and player.controller:
                    player.controller.add_message(f"获得 {scroll_desc}，{effect_msg}")

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
            if hasattr(target, 'controller') and target.controller:
                target.controller.add_message(f"{self.name} 被晕眩，无法反击!")
            return False

        # 检查目标是否有结界
        if "barrier" in target.statuses and target.statuses["barrier"]["duration"] > 0:
            if hasattr(target, 'controller') and target.controller:
                target.controller.add_message(f"{self.name} 的攻击被结界挡住了!")
            return False

        # 计算伤害
        mdmg = max(1, self.atk - random.randint(0, 1))
            
        # 造成伤害
        actual_dmg = target.take_damage(mdmg)
        if hasattr(target, 'controller') and target.controller:
            target.controller.add_message(f"{self.name} 反击造成 {actual_dmg} 点伤害.")

        # 检查目标是否死亡
        if target.hp <= 0:
            revived = target.try_revive()
            if hasattr(target, 'controller') and target.controller:
                if revived:
                    target.controller.add_message("复活卷轴救了你(HP=1)!")
                else:
                    target.controller.add_message("你被怪物击倒, 英勇牺牲!")

        # 较强怪物可能附带负面效果
        # 根据怪物等级调整负面效果概率
        effect_probability = 0.1  # 基础概率10%
        if self.tier >= 2:
            effect_probability += 0.1  # Tier 2怪物增加10%概率
        if self.tier >= 3:
            effect_probability += 0.1  # Tier 3怪物再增加10%概率
        if self.tier >= 4:
            effect_probability += 0.1  # Tier 4怪物再增加10%概率
            
        if random.random() < effect_probability:
            effect = random.choice(["weak", "poison", "stun"])
            duration = random.randint(1, 2)
            
            # 检查目标是否有免疫效果
            if hasattr(target, 'statuses') and "immune" in target.statuses and target.statuses["immune"]["duration"] > 0:
                if hasattr(target, 'controller') and target.controller:
                    target.controller.add_message(f"免疫效果保护了你免受 {effect} 效果!")
            else:
                target.statuses[effect] = {"duration": duration}
                if hasattr(target, 'controller') and target.controller:
                    target.controller.add_message(f"{self.name} 附带 {effect} 效果 ({duration}回合)!")

        return False

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