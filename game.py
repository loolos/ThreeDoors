"""游戏主控制器：一局游戏的全部状态（玩家、剧情、场景、回合）与回合级规则。"""
from typing import Iterable, Optional

from models.player import Player
from models.shop import Shop
from models.story_system import StorySystem
from models.game_config import GameConfig
from scenes import SceneManager

# 命令行别名 → 测试 gate 名
_TEST_GATE_FLAG_ALIASES = {
    "--test-puppet-final-boss": "puppet_final_boss",
    "--test-puppet-echo": "puppet_echo",
    "--test-stage-curtain-power": "stage_curtain_power",
}


def parse_test_gate(argv: Iterable[str]) -> Optional[str]:
    """从启动参数解析测试 gate：--test-gate=<name> 或上面的别名；未指定返回 None。"""
    for arg in argv:
        if arg.startswith("--test-gate="):
            return arg.split("=", 1)[1].strip().lower() or None
        if arg in _TEST_GATE_FLAG_ALIASES:
            return _TEST_GATE_FLAG_ALIASES[arg]
    return None


class GameController:
    """游戏主控制器：管理玩家、剧情、场景与回合状态。"""

    def __init__(self, test_gate: Optional[str] = None):
        self.game_config = GameConfig()
        # 测试 gate：非空时每次新局/重置都会直接跳到对应剧情节点（见 parse_test_gate）
        self.test_gate = test_gate
        # /buttonAction 去重：最近一次动作的 id 与返回结果（重试请求直接复用）
        self.last_action_id: Optional[str] = None
        self.last_action_response: Optional[dict] = None
        self.reset_game()

    def reset_game(self):
        """重置游戏状态"""
        self.current_monster = None
        self.current_battle_extensions = []
        self.current_event = None
        self.game_clear_info = None
        self.round_count = 0
        self.messages = []
        self.recent_event_classes = []  # 最近触发的事件类名，用于非后续事件门去重
        self.event_trigger_counts = {}  # 事件触发计数，用于权重衰减与单次事件控制
        self.door_visit_counts = {"trap": 0, "reward": 0, "monster": 0, "shop": 0, "event": 0}
        self.monsters_defeated = 0
        self.player = Player(self)
        self.player.reset()  # 重置玩家状态
        self.story = StorySystem(self)
        self.current_shop = Shop(self.player)
        self.scene_manager = SceneManager()
        self.scene_manager.game_controller = self  # 直接设置 game_controller
        self.scene_manager.initialize_scenes()  # 这会设置当前场景为 DoorScene
        self.unlocked_monster_tier = GameConfig.START_UNLOCKED_MONSTER_TIER
        self.player_peak_hp = self.player.hp
        self.player_peak_atk = self.player.atk

        # 测试 gate：若启动时带了 --test-gate=...，直接进入对应事件门
        if self.test_gate == "puppet_final_boss":
            self.round_count = 100
            self.player.hp = 500
            self.player._atk = 200
            self.player_peak_hp = 500
            self.player_peak_atk = 200
            door = self.story.setup_test_gate_puppet_final_boss()
            if door:
                door.enter()
                self.scene_manager.go_to("battle_scene")
                self.add_message("【测试模式】已直接进入木偶最终 Boss 战（回合 100，玩家 500 HP / 200 攻击）。")
        elif self.test_gate == "stage_curtain_order":
            self.story.setup_test_gate_stage_curtain_order()
            self.story.ensure_pre_final_event_schedule()
            self.scene_manager.go_to("door_scene")
            self.add_message("【测试模式】补全谢幕路线：回合 190，HP 800 / ATK 200，飞贼线收束+钥匙+木偶已击败+低邪恶值；下一扇宝物门将触发银羽秘藏。")
        elif self.test_gate == "stage_curtain_power":
            self.story.setup_test_gate_stage_curtain_power()
            self.story.ensure_pre_final_event_schedule()
            self.scene_manager.go_to("door_scene")
            self.add_message("【测试模式】接管谢幕路线：回合 190，HP 800 / ATK 200，飞贼线敌对收束、关系极差（可触发清算战）、无钥匙+木偶已击败+高邪恶值；第 200 回合将挂载木偶回声门并进入接管谢幕分支。")
        elif self.test_gate == "puppet_echo":
            self.story.setup_test_gate_puppet_echo()
            self.story.ensure_pre_final_event_schedule()
            self.scene_manager.go_to("door_scene")
            self.add_message("【测试模式】木偶回声门路线：回合 190，HP 800 / ATK 200，飞贼敌对无钥匙且关系 -5（可触发清算战），木偶已击败+高邪恶值；第 200 回合将挂载木偶回声门。")

    def add_message(self, msg):
        """添加消息到消息列表（同一条连续日志仅保留一份）。"""
        if isinstance(msg, str):
            if not self.messages or self.messages[-1] != msg:
                self.messages.append(msg)
        elif isinstance(msg, list):
            for item in msg:
                if isinstance(item, str) and (not self.messages or self.messages[-1] != item):
                    self.messages.append(item)

    def clear_messages(self):
        """清空消息列表"""
        self.messages.clear()

    def clear_battle_extensions(self):
        """清空当前战斗扩展。"""
        self.current_battle_extensions = []

    def apply_battle_extensions(self, trigger, attacker, defender, damage):
        """仅对当前怪物门声明的扩展执行战斗修正。"""
        adjusted = damage
        for ext in self.current_battle_extensions:
            adjusted = self.story.apply_battle_extension(
                extension=ext,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=adjusted,
            )
        return adjusted

    def on_player_attack_resolved(self, target):
        """玩家攻击后执行扩展后处理（例如阶段切换）。"""
        for ext in self.current_battle_extensions:
            self.story.handle_battle_extension_post_player_attack(extension=ext, target=target)

    def record_door_visit(self, door_enum_value: str) -> None:
        """记录一次门类型访问，用于结局统计。"""
        if door_enum_value in self.door_visit_counts:
            self.door_visit_counts[door_enum_value] += 1

    def record_monster_defeated(self) -> None:
        """记录击败一只怪物，用于结局统计。"""
        self.monsters_defeated += 1

    def trigger_game_clear(self, ending_key: str, ending_title: str, ending_description: str, ending_meta=None) -> None:
        """触发通关结局并跳转到结局滚动画面，再进入结算场景。"""
        extra_meta = ending_meta if isinstance(ending_meta, dict) else {}
        self.game_clear_info = {
            "ending_key": str(ending_key or "unknown"),
            "ending_title": str(ending_title or "结局"),
            "ending_description": str(ending_description or ""),
            "ending_meta": extra_meta,
        }
        self.scene_manager.go_to("ending_summary_scene")

    def update_player_power_peaks(self):
        """记录玩家历史最高生命与攻击，用于 tier 解锁判定。"""
        self.player_peak_hp = max(self.player_peak_hp, self.player.hp)
        self.player_peak_atk = max(self.player_peak_atk, self.player.atk)

    def check_and_unlock_monster_tier(self):
        """每隔固定回合检查怪物 tier 解锁进度，并输出日志。"""
        if self.round_count <= 0:
            return
        if self.round_count % GameConfig.MONSTER_TIER_CHECK_INTERVAL != 0:
            return

        self.update_player_power_peaks()
        # 有效战力 = min(攻击, 生命/2)，用于 tier 解锁判定
        effective_power = min(self.player_peak_atk, self.player_peak_hp // 2)
        old_tier = self.unlocked_monster_tier
        max_tier = GameConfig.MONSTER_MAX_TIER
        new_tier = old_tier

        for tier in range(old_tier + 1, max_tier + 1):
            requirement = GameConfig.MONSTER_TIER_UNLOCK_REQUIREMENTS.get(tier)
            if requirement is None:
                continue
            if effective_power >= requirement:
                new_tier = tier
            else:
                break

        tier_unlock_messages = {
            2: "【威胁升级】阴影里多了细碎脚步声——潜伏者开始在门后徘徊。",
            3: "【威胁升级】你听见铁甲彼此摩擦的回响，重装猎手也加入了追逐。",
            4: "【威胁升级】空气里浮起血与硫磺的味道，凶暴巨兽已被惊醒。",
            5: "【威胁升级】远处传来低沉吟唱，古老而狡诈的强敌正在靠近。",
            6: "【威胁升级】整座迷宫都在震颤，传说中的掠食者已锁定你的气息。",
        }

        tier_warning_messages = {
            2: "【威胁侦测】墙上的抓痕越来越新，像是有猎手在试探你的脚步。",
            3: "【威胁侦测】风里夹着金属味，前方似乎有披甲敌人在巡猎。",
            4: "【威胁侦测】地面偶尔传来闷响，更沉重的脚步正在向你逼近。",
            5: "【威胁侦测】你听见断续低语，某些危险存在已经开始注意你。",
            6: "【威胁侦测】连火把都在发颤，最顶层的威胁正从黑暗深处苏醒。",
        }

        if new_tier > old_tier:
            self.unlocked_monster_tier = new_tier
            for tier in range(old_tier + 1, new_tier + 1):
                self.add_message(
                    tier_unlock_messages.get(
                        tier,
                        f"【威胁升级】更凶险的敌人现身了（已解锁 Tier {tier}）。",
                    )
                )
            return

        if old_tier >= max_tier:
            self.add_message("【威胁侦测】你已触及最高威胁层级，前方皆是传说级敌手。")
            return

        next_tier = old_tier + 1
        self.add_message(
            tier_warning_messages.get(
                next_tier,
                "【威胁侦测】黑暗中的敌意仍在增长，你能感觉到下一波威胁快到了。",
            )
        )
