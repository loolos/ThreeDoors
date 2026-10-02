"""游戏配置：规则常量在此定义；数值平衡表（怪物、商店、解锁门槛等）从 data/balance.json 读取。"""
import json
import os

BALANCE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "balance.json")


def load_balance(path: str = BALANCE_PATH) -> dict:
    """读取数值平衡表（JSON；以 "_" 开头的键是注释）。"""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


_BALANCE = load_balance()


class GameConfig:
    """游戏配置"""
    # 玩家初始属性
    START_PLAYER_HP = int(_BALANCE["player"]["start_hp"])
    START_PLAYER_ATK = int(_BALANCE["player"]["start_atk"])
    START_PLAYER_GOLD = int(_BALANCE["player"]["start_gold"])
    MAX_INVENTORY_SIZE = int(_BALANCE["player"]["max_inventory_size"])
    
    # 怪物掉落配置
    LOOT_CHANCE = 0.5  # 怪物掉落物品的概率

    # 怪物 tier 进度配置
    MONSTER_MIN_TIER = 1
    MONSTER_MAX_TIER = 6
    START_UNLOCKED_MONSTER_TIER = 1
    MONSTER_TIER_CHECK_INTERVAL = 5
    # 解锁规则：玩家历史峰值 min(攻击, 生命/2) 达到门槛时解锁下一 tier（数值越高门槛越高）
    MONSTER_TIER_UNLOCK_REQUIREMENTS = {
        int(tier): int(value) for tier, value in _BALANCE["monster_tier_unlock"]["requirements"].items()
    }
    # 各 tier 怪物：{tier: [(名称, 生命, 攻击), ...]}
    MONSTER_TYPES = {
        int(tier): [(m["name"], int(m["hp"]), int(m["atk"])) for m in monsters]
        for tier, monsters in _BALANCE["monsters"].items()
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
    EQUIPMENT_NAME_POOLS = {int(k): list(v) for k, v in _BALANCE["equipment_name_pools"].items()}
    # 商店商品池：每项 {"class": items 中的类名, "weight": 权重, 其余为构造参数}
    SHOP_ITEMS = list(_BALANCE["shop_items"])
