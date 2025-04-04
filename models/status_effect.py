class StatusEffect:
    """状态效果定义类"""
    # 统一的状态效果配置
    STATUS_CONFIGS = {
        # 战斗状态：只在战斗回合中生效
        "weak": {
            "name": "虚弱",
            "description": "攻击力降低2点",
            "duration": 3,
            "is_battle_only": True,
            "is_monster_effect": True
        },
        "poison": {
            "name": "中毒",
            "description": "每回合损失10%生命值",
            "duration": 3,
            "is_battle_only": True,
            "is_monster_effect": True
        },
        "stun": {
            "name": "晕眩",
            "description": "无法行动",
            "duration": 2,
            "is_battle_only": True,
            "is_monster_effect": True
        },
        "atk_multiplier": {
            "name": "攻击翻倍",
            "description": "攻击力翻倍",
            "duration": 1,
            "is_battle_only": True,
            "value": 2
        },
        "barrier": {
            "name": "结界",
            "description": "免疫怪物伤害",
            "duration": 3,
            "is_battle_only": True
        },
        # 冒险状态：在冒险回合中生效
        "atk_up": {
            "name": "攻击力提升",
            "description": "攻击力增加",
            "duration": 5,
            "is_battle_only": False,
            "value": 2
        },
        "damage_reduction": {
            "name": "伤害减免",
            "description": "受到伤害减少30%",
            "duration": 5,
            "is_battle_only": False,
            "value": 0.7
        },
        "healing_scroll": {
            "name": "恢复卷轴",
            "description": "每回合恢复生命",
            "duration": 10,
            "is_battle_only": False,
            "value": 5  # 默认恢复值，实际值在购买时随机生成
        },
        "immune": {
            "name": "免疫",
            "description": "免疫所有负面效果",
            "duration": 5,
            "is_battle_only": False
        }
    }
    
    @classmethod
    def get_status_info(cls, status_name):
        """获取状态效果的详细信息"""
        return cls.STATUS_CONFIGS.get(status_name)
    
    @classmethod
    def is_battle_status(cls, status_name):
        """判断是否为战斗状态"""
        status_info = cls.get_status_info(status_name)
        return status_info and status_info.get("is_battle_only", False)
    
    @classmethod
    def is_adventure_status(cls, status_name):
        """判断是否为冒险状态"""
        status_info = cls.get_status_info(status_name)
        return status_info and not status_info.get("is_battle_only", False)
    
    @classmethod
    def is_monster_effect(cls, status_name):
        """判断是否为怪物造成的效果"""
        status_info = cls.get_status_info(status_name)
        return status_info and status_info.get("is_monster_effect", False)
    
    @classmethod
    def clear_battle_statuses(cls, player):
        """清除所有战斗状态"""
        expired = []
        for st in player.statuses:
            if cls.is_battle_status(st):
                expired.append(st)
        for r in expired:
            del player.statuses[r] 