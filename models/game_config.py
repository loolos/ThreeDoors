class GameConfig:
    """游戏配置"""
    # 玩家初始属性
    START_PLAYER_HP = 20
    START_PLAYER_ATK = 5
    START_PLAYER_GOLD = 0 
    MAX_INVENTORY_SIZE = 10
    
    # 怪物掉落配置
    LOOT_CHANCE = 0.5  # 怪物掉落物品的概率

    # 怪物 tier 进度配置
    MONSTER_MIN_TIER = 1
    MONSTER_MAX_TIER = 6
    START_UNLOCKED_MONSTER_TIER = 1
    MONSTER_TIER_CHECK_INTERVAL = 5
    # 解锁规则：仅当玩家（历史峰值）攻击和生命都达到门槛时解锁下一 tier
    MONSTER_TIER_UNLOCK_REQUIREMENTS = {
        2: {"atk": 8, "hp": 30},
        3: {"atk": 14, "hp": 60},
        4: {"atk": 24, "hp": 120},
        5: {"atk": 40, "hp": 260},
        6: {"atk": 70, "hp": 420},
    }

    # 事件门后续影响：候选数 <5 时，此概率下不改写门、沿用原门（不应用任何 pending consequence）
    EVENT_DOOR_SKIP_REWRITE_CHANCE = 0.3
    # 后续影响加权抽取时，force_story_event 类后果的权重倍数（>1 表示更容易被抽中）
    FORCE_STORY_EVENT_WEIGHT_BONUS = 2.0