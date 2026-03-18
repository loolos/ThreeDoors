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
    # 解锁规则：玩家历史峰值 min(攻击, 生命/2) 达到门槛时解锁下一 tier（数值越高门槛越高）
    MONSTER_TIER_UNLOCK_REQUIREMENTS = {
        2: 32,   # min(攻击, 生命/2) >= 32
        3: 64,   # min(攻击, 生命/2) >= 64
        4: 112,  # min(攻击, 生命/2) >= 112
        5: 180,  # min(攻击, 生命/2) >= 180
        6: 280,  # min(攻击, 生命/2) >= 280
    }

    # 事件门后续影响：候选数 <5 时，此概率下不改写门、沿用原门（不应用任何 pending consequence）
    EVENT_DOOR_SKIP_REWRITE_CHANCE = 0.3
    # 后续影响加权抽取时，force_story_event 类后果的权重倍数（>1 表示更容易被抽中）
    FORCE_STORY_EVENT_WEIGHT_BONUS = 2.0
    # 结局前倒数窗口内，若仍有未清空的终局前置事件，则 80% 概率优先从这些事件中抽取
    PRE_FINAL_PENDING_PRIORITY_CHANCE = 0.8

    # -------------------------------
    # 装备命名池（统一配置）
    # -------------------------------
    # key 采用装备的 atk_bonus 档位（商店/随机物品均按该档位选名）
    EQUIPMENT_NAME_POOLS = {
        # 低档：破旧但带点故事
        2: ["豁口短刀", "裂纹木槌", "断齿短斧", "生锈的长剑", "钉锤", "旧护手匕首"],
        # 中档：能用、偏实战
        5: ["精钢长剑", "铁剑", "猎手弯刀", "重刃柴刀", "城卫佩剑", "匠造短枪"],
        # 高档：更像“宝物名”
        10: ["秘银短剑", "附魔之刃", "破风长刃", "黑曜石钩镰", "碎星战斧", "暮光细剑"],
        30: ["霜咬巨刃", "赤纹战戟", "雷鸣重锤", "深渊之刃", "苍穹长枪", "群鸦镰刀"],
        50: ["王庭裁决", "龙骨巨剑", "星辉圣刃", "永夜断罪", "天穹审判", "不朽誓约"],
    }
