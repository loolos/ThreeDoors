class GameConfig:
    """游戏配置"""
    # 玩家初始属性
    START_PLAYER_HP = 20
    START_PLAYER_ATK = 5
    START_PLAYER_GOLD = 0 
    MAX_INVENTORY_SIZE = 10
    
    # 怪物掉落配置
    LOOT_CHANCE = 0.5  # 怪物掉落物品的概率

    # 事件门后续影响：候选数 <5 时，此概率下不改写门、沿用原门（不应用任何 pending consequence）
    EVENT_DOOR_SKIP_REWRITE_CHANCE = 0.3
    # 后续影响加权抽取时，force_story_event 类后果的权重倍数（>1 表示更容易被抽中）
    FORCE_STORY_EVENT_WEIGHT_BONUS = 2.0