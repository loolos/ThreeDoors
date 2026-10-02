"""门扩展与战斗扩展：剧情把额外规则挂到某扇门 / 某场战斗上（标记宝物、寄存背包、
木偶双阶段 Boss、飞贼清算战的反击与仇怨台词等）。

以 mixin 形式并入 StorySystem，方法名与调用方式保持不变：
- 门：Door.run_door_extensions → StorySystem.apply_door_extension
- 战斗：GameController.apply_battle_extensions → StorySystem.apply_battle_extension，
  玩家出手后 → handle_battle_extension_post_player_attack
"""
import random
from typing import Any, Dict, Set, Tuple

from models.door import DoorEnum
from models.items import DepositedBackpack, create_random_item
from models.narrative import story_system_lines as narrative_lines
from models.status import StatusName


class StoryExtensionsMixin:
    def _attach_door_extension(
        self,
        door: Any,
        extension_config: Dict[str, Any],
        *,
        apply_on_attach: bool = True,
    ) -> bool:
        """将事件改写封装到门扩展，并可在挂载时做一次兼容应用。"""
        if door is None or not isinstance(extension_config, dict):
            return False
        add_method = getattr(door, "add_door_extension", None)
        if not callable(add_method):
            add_method = getattr(door, "add_extension", None)
        if callable(add_method):
            add_method(extension_config)
        else:
            ext_list = getattr(door, "door_extensions", None)
            if not isinstance(ext_list, list):
                ext_list = []
                door.door_extensions = ext_list
            ext_list.append(extension_config)
        if apply_on_attach:
            self.apply_door_extension(door=door, extension=extension_config, hook="on_attach")
        return True

    @staticmethod
    def _get_extension_runtime(extension: Dict[str, Any]) -> Dict[str, Any]:
        runtime = extension.get("_runtime")
        if not isinstance(runtime, dict):
            runtime = {}
            extension["_runtime"] = runtime
        return runtime

    def _build_marked_reward(
        self,
        current_reward: Dict[Any, int],
        payload: Dict[str, Any],
    ) -> Tuple[Dict[Any, int], Any]:
        keep_gold = bool(payload.get("keep_gold", True))
        reward_gold = current_reward.get("gold", 0) if keep_gold else 0
        if bool(payload.get("replace_existing_items", True)):
            new_reward: Dict[Any, int] = {}
        else:
            new_reward = {k: v for k, v in current_reward.items() if k != "gold"}
        if reward_gold > 0:
            new_reward["gold"] = reward_gold
        bonus_gold = int(payload.get("gold_bonus", 0))
        if bonus_gold > 0:
            new_reward["gold"] = new_reward.get("gold", 0) + bonus_gold
        amount = max(1, int(payload.get("amount", 1)))
        item_key = payload.get("item_key")
        marked_item = self._create_story_item(item_key)
        if not marked_item:
            marked_item = create_random_item()
        new_reward[marked_item] = amount
        return new_reward, marked_item

    def _build_deposit_backpack_reward(self, payload: Dict[str, Any]) -> Dict[Any, int]:
        gold_min = max(8, int(payload.get("gold_min", 16)))
        gold_max = max(gold_min, int(payload.get("gold_max", 40)))
        extra_count = max(2, int(payload.get("extra_item_count", 2)))
        stored_items = [create_random_item() for _ in range(extra_count)]
        reward: Dict[Any, int] = {
            "gold": random.randint(gold_min, gold_max),
            DepositedBackpack(name="寄存的背包", cost=0, stored_items=stored_items): 1,
        }
        return reward

    def _build_puppet_battle_state(
        self,
        payload: Dict[str, Any],
        story_flags: Set[str],
        kind_name: str,
        dark_name: str,
        phase2_name: str,
    ) -> Dict[str, Any]:
        """构建黑暗木偶双阶段战斗状态。"""
        try:
            threshold = float(payload.get("phase2_threshold_ratio", 0.45))
        except (TypeError, ValueError):
            threshold = 0.45
        threshold = max(0.12, min(0.75, threshold))
        try:
            burst_heal_ratio = float(payload.get("phase2_burst_heal_ratio", 0.22))
        except (TypeError, ValueError):
            burst_heal_ratio = 0.22
        burst_heal_ratio = max(0.08, min(0.5, burst_heal_ratio))
        try:
            burst_atk_ratio = float(payload.get("phase2_burst_atk_ratio", 1.12))
        except (TypeError, ValueError):
            burst_atk_ratio = 1.12
        burst_atk_ratio = max(1.03, min(1.5, burst_atk_ratio))
        try:
            phase2_min_hp_ratio = float(payload.get("phase2_min_hp_ratio", 0.0))
        except (TypeError, ValueError):
            phase2_min_hp_ratio = 0.0
        phase2_min_hp_ratio = max(0.0, min(1.0, phase2_min_hp_ratio))
        phase2_enabled = not bool(payload.get("disable_phase_two", False))

        state: Dict[str, Any] = {
            "phase": 1,
            "phase2_started": False,
            "phase2_enabled": phase2_enabled,
            "phase2_name": phase2_name.strip() if isinstance(phase2_name, str) and phase2_name.strip() else f"{dark_name}·黑暗完全体",
            "phase2_threshold_ratio": threshold,
            "phase2_burst_heal_ratio": burst_heal_ratio,
            "phase2_burst_atk_ratio": burst_atk_ratio,
            "phase2_min_hp_ratio": phase2_min_hp_ratio,
            "phase1_entry_modifiers": [],
            "phase2_entry_modifiers": [],
            "runtime_modifiers": [],
            "runtime_trigger_counts": {},
            "kind_name": kind_name,
            "dark_name": dark_name,
        }

        def _add_entry(
            flag: str,
            *,
            phase: int,
            target: str,
            direction: str,
            message: str,
            min_pct: float = 0.05,
            max_pct: float = 0.15,
        ) -> None:
            if flag not in story_flags:
                return
            key = "phase1_entry_modifiers" if phase == 1 else "phase2_entry_modifiers"
            state[key].append(
                {
                    "id": flag,
                    "target": target,
                    "direction": direction,
                    "message": message,
                    "min_pct": max(0.05, float(min_pct)),
                    "max_pct": min(0.15, float(max_pct)),
                }
            )

        def _add_runtime(
            flag: str,
            *,
            trigger: str,
            direction: str,
            message: str,
            chance: float = 0.35,
            active_phase: int = 0,
            min_pct: float = 0.05,
            max_pct: float = 0.15,
        ) -> None:
            if flag not in story_flags:
                return
            state["runtime_modifiers"].append(
                {
                    "id": flag,
                    "trigger": trigger,
                    "direction": direction,
                    "message": message,
                    "chance": max(0.01, min(1.0, float(chance))),
                    "active_phase": max(0, int(active_phase)),
                    "min_pct": max(0.05, float(min_pct)),
                    "max_pct": min(0.15, float(max_pct)),
                }
            )

        # 阶段一开场：只做百分比增减（5%~15%）。
        _add_entry(
            "consumed:puppet_side_minion_once",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你拆过锈蚀的小木偶，开场节奏被你读穿，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_signal_soft",
            phase=1,
            target="boss_hp",
            direction="down",
            message="你此前重放的温和语音样本仍在生效，核心输出收敛，黑暗木偶生命降低 {percent}%。",
        )
        _add_entry(
            "puppet_signal_soft",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你此前重放的温和语音样本干扰了抬手节奏，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_signal_log",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你此前分析过战术日志并补齐反制参数，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_kind_echo_trust",
            phase=1,
            target="boss_atk",
            direction="down",
            message="你曾按善良人格给的路线前进，它仍在底层牵制，黑暗木偶攻击降低 {percent}%。",
        )
        _add_entry(
            "puppet_rift_kind",
            phase=1,
            target="boss_hp",
            direction="down",
            message="裂隙中你护住了善良侧信号通道，黑暗木偶生命降低 {percent}%。",
        )
        _add_entry(
            "puppet_descent_patch",
            phase=1,
            target="boss_hp",
            direction="down",
            message="你此前写入的修复补丁残留生效，黑暗木偶生命降低 {percent}%。",
        )

        # 阶段二开场：部分前情延迟到“完全体爆发”时结算。
        _add_entry(
            "consumed:puppet_side_shop_once",
            phase=2,
            target="boss_hp",
            direction="up",
            message="黑市替它补了装甲片，完全体生命上升 {percent}%。",
        )
        _add_entry(
            "consumed:puppet_side_shop_once",
            phase=2,
            target="boss_atk",
            direction="up",
            message="装甲驱动联动完成，完全体攻击上升 {percent}%。",
        )
        _add_entry(
            "puppet_signal_resell",
            phase=2,
            target="boss_hp",
            direction="up",
            message="你曾把污染片段打包转卖，完全体病毒回灌，生命上升 {percent}%。",
        )
        _add_entry(
            "puppet_rift_dark",
            phase=2,
            target="boss_atk",
            direction="up",
            message="裂隙里你向黑暗侧喂过自毁协议，完全体攻击上升 {percent}%。",
        )
        _add_entry(
            "puppet_descent_dark_feed",
            phase=2,
            target="boss_hp",
            direction="up",
            message="你曾随机录入指令试图控制木偶，指令集中兑现，完全体生命上升 {percent}%。",
        )
        _add_entry(
            "puppet_descent_dark_feed",
            phase=2,
            target="boss_atk",
            direction="up",
            message="你此前录入的随机指令彻底放开限制，完全体攻击上升 {percent}%。",
        )
        _add_entry(
            "puppet_kind_echo_comfort",
            phase=2,
            target="player_hp",
            direction="up",
            message="你曾追问它被抛弃的过去并稳定情绪，蓝光回路在爆发瞬间回补你 {percent}% 当前生命。",
        )

        # 运行时连锁：玩家攻击 / 木偶出招时可重复触发。
        _add_runtime(
            "consumed:puppet_side_trap_once",
            trigger="monster_attack",
            direction="up",
            message="陷阱回廊里木偶病毒曾劫持过你的节拍，在出招时重放，本次木偶伤害提高 {percent}%。",
            chance=0.33,
            active_phase=0,
        )
        _add_runtime(
            "consumed:puppet_side_reward_once",
            trigger="player_attack",
            direction="up",
            message="你曾拿到的宝物应急结界发生器在挥击时校准受力，本次玩家伤害提高 {percent}%。",
            chance=0.36,
            active_phase=0,
        )
        _add_runtime(
            "consumed:puppet_side_reward_once",
            trigger="monster_attack",
            direction="down",
            message="应急结界在受击瞬间展开，本次木偶伤害降低 {percent}%。",
            chance=0.34,
            active_phase=0,
        )
        _add_runtime(
            "puppet_signal_soft",
            trigger="monster_attack",
            direction="down",
            message="你此前重放的温和语音样本拖慢了黑暗抬手，本次木偶伤害降低 {percent}%。",
            chance=0.35,
            active_phase=0,
        )
        _add_runtime(
            "puppet_signal_log",
            trigger="player_attack",
            direction="up",
            message="你此前分析战术日志补齐的反制参数提示了破绽，本次玩家伤害提高 {percent}%。",
            chance=0.4,
            active_phase=0,
        )
        _add_runtime(
            "puppet_kind_echo_trust",
            trigger="monster_attack",
            direction="down",
            message="你曾相信善良人格给的路线，它再次短暂争夺控制，本次木偶伤害降低 {percent}%。",
            chance=0.32,
            active_phase=0,
        )
        _add_runtime(
            "puppet_kind_echo_exploit",
            trigger="monster_attack",
            direction="up",
            message="你曾记录的情感弱点被反向放大，本次木偶伤害提高 {percent}%。",
            chance=0.34,
            active_phase=0,
        )
        _add_runtime(
            "puppet_rift_balance",
            trigger="player_attack",
            direction="up",
            message="你在裂隙维持的双侧平衡参数生效，本次玩家伤害提高 {percent}%。",
            chance=0.28,
            active_phase=0,
        )
        _add_runtime(
            "consumed:puppet_side_shop_once",
            trigger="player_attack",
            direction="down",
            message="黑市装甲片抵消了部分冲击，本次玩家伤害降低 {percent}%。",
            chance=0.35,
            active_phase=2,
        )
        _add_runtime(
            "puppet_signal_resell",
            trigger="monster_attack",
            direction="up",
            message="你此前转卖的污染片段在完全体中继续发酵，本次木偶伤害提高 {percent}%。",
            chance=0.37,
            active_phase=0,
        )
        _add_runtime(
            "puppet_descent_cut_emotion",
            trigger="monster_attack",
            direction="up",
            message="你此前切断了情感模块，完全体再无牵制，本次木偶伤害提高 {percent}%。",
            chance=0.4,
            active_phase=2,
        )
        _add_runtime(
            "puppet_descent_patch",
            trigger="monster_attack",
            direction="down",
            message="你此前写入的修复补丁在关键节点阻断杀意，本次木偶伤害降低 {percent}%。",
            chance=0.3,
            active_phase=0,
        )

        state["monster_attack_filler_lines"] = [
            "童谣断在半拍，机偶仍顺着惯性挥向你。",
            "钢丝拉紧，木偶的关节朝你压来。",
            "失真笑声里混着咔哒声，又一击落下。",
            "黑暗协议没有迟疑——这一下只是执行。",
            f"{state['dark_name']}借机偶的手臂，把节拍砸向你胸口。",
        ]

        return state

    def _apply_puppet_entry_modifiers(self, monster: Any, state: Dict[str, Any], phase: int) -> None:
        if not isinstance(state, dict):
            return
        key = "phase1_entry_modifiers" if phase == 1 else "phase2_entry_modifiers"
        modifiers = state.get(key, [])
        if not isinstance(modifiers, list):
            return
        player = getattr(self.controller, "player", None)
        for mod in modifiers:
            if not isinstance(mod, dict):
                continue
            min_pct = max(0.05, float(mod.get("min_pct", 0.05)))
            max_pct = min(0.15, float(mod.get("max_pct", 0.15)))
            if max_pct < min_pct:
                min_pct, max_pct = max_pct, min_pct
            pct = random.uniform(min_pct, max_pct)
            pct_text = int(round(pct * 100))
            direction = mod.get("direction", "down")
            target = mod.get("target")
            amount = 0

            if target == "boss_hp":
                before = max(1, int(monster.hp))
                scale = (1.0 + pct) if direction == "up" else max(0.1, 1.0 - pct)
                monster.hp = max(1, int(round(before * scale)))
                amount = abs(monster.hp - before)
            elif target == "boss_atk":
                before = max(1, int(monster.atk))
                scale = (1.0 + pct) if direction == "up" else max(0.1, 1.0 - pct)
                monster.atk = max(1, int(round(before * scale)))
                amount = abs(monster.atk - before)
            elif target == "player_hp" and player is not None:
                base = max(1, int(getattr(player, "hp", 1)))
                delta = max(1, int(round(base * pct)))
                if direction == "up":
                    amount = player.heal(delta)
                else:
                    safe_delta = min(delta, max(0, player.hp - 1))
                    if safe_delta > 0:
                        player.take_damage(safe_delta)
                        amount = safe_delta
            message = mod.get("message", "")
            if isinstance(message, str) and message.strip():
                self.controller.add_message(message.format(percent=pct_text, value=amount))

    def _get_puppet_extension_runtime(self, extension: Dict[str, Any], attacker: Any, defender: Any):
        if not isinstance(extension, dict):
            return None, None
        if extension.get("extension_type") != "puppet_dark_boss":
            return None, None
        monster = extension.get("monster_ref")
        state = extension.get("state")
        if monster is None or not isinstance(state, dict):
            return None, None
        if attacker is not monster and defender is not monster:
            return None, None
        return monster, state

    @staticmethod
    def _puppet_phase2_hp_atk(
        phase1_max_hp: int,
        hp_before_phase2: int,
        atk_before_phase2: int,
        state: Dict[str, Any],
    ) -> Tuple[int, int, int]:
        """二阶段：当前血 + 爆发治疗，且不低于 phase1_max_hp * phase2_min_hp_ratio；攻击乘 phase2_burst_atk_ratio。
        返回 (新血量, 新攻击, 爆发治疗量)。"""
        p1 = max(1, int(phase1_max_hp))
        burst = max(1, int(round(p1 * float(state.get("phase2_burst_heal_ratio", 0.22)))))
        floor_hp = max(1, int(round(p1 * max(0.0, float(state.get("phase2_min_hp_ratio", 0.0))))))
        new_hp = max(max(1, int(hp_before_phase2)) + burst, floor_hp)
        new_atk = max(
            1,
            int(round(max(1, int(atk_before_phase2)) * float(state.get("phase2_burst_atk_ratio", 1.12)))),
        )
        return new_hp, new_atk, burst

    def _try_trigger_puppet_phase_two(self, extension: Dict[str, Any], target: Any) -> bool:
        """在阶段一生命跌破阈值时，切入黑暗完全体。"""
        if not isinstance(extension, dict) or extension.get("extension_type") != "puppet_dark_boss":
            return False
        monster = extension.get("monster_ref")
        state = extension.get("state")
        if monster is None or target is not monster or not isinstance(state, dict):
            return False
        if not bool(state.get("phase2_enabled", True)):
            return False
        if int(state.get("phase", 1)) >= 2:
            return False
        phase1_max_hp = int(state.get("phase1_max_hp", max(1, int(getattr(monster, "hp", 1)))))
        threshold_ratio = float(state.get("phase2_threshold_ratio", 0.45))
        threshold_hp = max(1, int(round(phase1_max_hp * threshold_ratio)))
        if int(monster.hp) > threshold_hp and int(monster.hp) > 0:
            return False

        state["phase"] = 2
        state["phase2_started"] = True
        old_name = monster.name
        monster.name = state.get("phase2_name", monster.name)

        monster.hp, monster.atk, burst_heal = self._puppet_phase2_hp_atk(
            phase1_max_hp, int(monster.hp), int(monster.atk), state
        )

        self.controller.add_message(
            narrative_lines.format_puppet_phase2_entrance(
                old_name, monster.name, burst_heal, int(monster.atk)
            )
        )
        self.controller.add_message(narrative_lines.MSG_PUPPET_PHASE2_THEME)
        self._apply_puppet_entry_modifiers(monster=monster, state=state, phase=2)
        return True

    def _apply_puppet_runtime_modifiers(
        self,
        extension: Dict[str, Any],
        trigger: str,
        attacker: Any,
        defender: Any,
        damage: int,
    ) -> int:
        """对木偶最终战扩展应用战斗中可重复触发的百分比修正。"""
        try:
            raw_damage = max(1, int(damage))
        except (TypeError, ValueError):
            return damage
        if raw_damage <= 0:
            return raw_damage

        puppet_monster, state = self._get_puppet_extension_runtime(extension, attacker=attacker, defender=defender)
        if puppet_monster is None or not isinstance(state, dict):
            return raw_damage

        current_phase = max(1, int(state.get("phase", 1)))
        runtime_modifiers = state.get("runtime_modifiers", [])
        if not isinstance(runtime_modifiers, list) or not runtime_modifiers:
            return raw_damage

        factor = 1.0
        triggered = []
        counters = state.get("runtime_trigger_counts")
        if not isinstance(counters, dict):
            counters = {}
            state["runtime_trigger_counts"] = counters

        for mod in runtime_modifiers:
            if not isinstance(mod, dict):
                continue
            if mod.get("trigger") != trigger:
                continue
            active_phase = max(0, int(mod.get("active_phase", 0)))
            if active_phase and current_phase < active_phase:
                continue
            chance = max(0.01, min(1.0, float(mod.get("chance", 0.35))))
            if random.random() > chance:
                continue
            min_pct = max(0.05, float(mod.get("min_pct", 0.05)))
            max_pct = min(0.15, float(mod.get("max_pct", 0.15)))
            if max_pct < min_pct:
                min_pct, max_pct = max_pct, min_pct
            pct = random.uniform(min_pct, max_pct)
            if str(mod.get("direction", "up")).lower() == "down":
                factor *= max(0.15, 1.0 - pct)
            else:
                factor *= 1.0 + pct
            pct_text = int(round(pct * 100))
            msg = mod.get("message", "")
            if isinstance(msg, str) and msg.strip():
                triggered.append(msg.format(percent=pct_text))
            key = f"{mod.get('id', 'unknown')}:{trigger}"
            counters[key] = int(counters.get(key, 0)) + 1

        adjusted = max(1, int(round(raw_damage * factor)))
        for msg in triggered:
            self.controller.add_message(msg)
        if adjusted != raw_damage:
            actor = "木偶" if trigger == "monster_attack" else "玩家"
            self.controller.add_message(f"{actor}本次伤害 {raw_damage}→{adjusted}。")
        elif trigger == "monster_attack" and not triggered:
            fillers = state.get("monster_attack_filler_lines")
            if isinstance(fillers, list):
                pool = [x for x in fillers if isinstance(x, str) and x.strip()]
                if pool:
                    self.controller.add_message(random.choice(pool))
        return adjusted

    def apply_door_extension(
        self,
        door: Any,
        extension: Dict[str, Any],
        hook: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """统一门扩展入口：事件对门的改写逻辑集中在此。"""
        if door is None or not isinstance(extension, dict):
            return {}
        ext_type = extension.get("extension_type")
        door_type = getattr(getattr(door, "enum", None), "name", "")
        runtime = self._get_extension_runtime(extension)

        if ext_type == "force_story_event":
            event_key = extension.get("event_key")
            if door_type not in {"EVENT", "SHOP"}:
                return {}
            if not isinstance(event_key, str) or not event_key.strip():
                return {}
            door.story_forced_event_key = event_key.strip()
            hint = extension.get("hint") or extension.get("message")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            runtime["applied"] = True
            return {"applied": True}

        if ext_type == "elf_side_reward_mark":
            if door_type != "REWARD":
                return {}
            setattr(door, "elf_side_reward", True)
            hint = extension.get("hint") or extension.get("message")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            runtime["applied"] = True
            return {"applied": True}

        if ext_type == "elf_side_monster_mark":
            if door_type != "MONSTER":
                return {}
            monster = getattr(door, "monster", None)
            if monster is None:
                return {}
            setattr(monster, "elf_side_story", True)
            hint = extension.get("hint") or extension.get("message")
            if isinstance(hint, str) and hint.strip():
                door.hint = hint.strip()
            runtime["applied"] = True
            return {"applied": True}

        if ext_type == "treasure_marked_item":
            if door_type != "REWARD":
                return {}
            if runtime.get("reward_written"):
                return {"applied": True}
            resolved_reward = extension.get("resolved_reward", {})
            if not isinstance(resolved_reward, dict):
                resolved_reward = {}
            door.reward = dict(resolved_reward)
            runtime["reward_written"] = True
            return {"applied": True}

        if ext_type == "treasure_vanish":
            if door_type != "REWARD":
                return {}
            if runtime.get("reward_written"):
                return {"applied": True}
            resolved_reward = extension.get("resolved_reward", {})
            if not isinstance(resolved_reward, dict):
                resolved_reward = {}
            door.reward = dict(resolved_reward)
            runtime["reward_written"] = True
            return {"applied": True}

        if ext_type == "treasure_deposit_backpack":
            if door_type != "REWARD":
                return {}
            if runtime.get("reward_written"):
                return {"applied": True}
            resolved_reward = extension.get("resolved_reward", {})
            if not isinstance(resolved_reward, dict):
                resolved_reward = {}
            door.reward = dict(resolved_reward)
            runtime["reward_written"] = True
            return {"applied": True}

        if ext_type == "stage_curtain_script_vault":
            if door_type != "REWARD":
                return {}
            if runtime.get("reward_written"):
                return {"applied": True}
            try:
                from models.events import run_script_vault_recovery
                run_script_vault_recovery(self.controller)
            except Exception:
                pass
            door.reward = {}
            runtime["reward_written"] = True
            return {"applied": True}

        if ext_type == "trap_rewrite_to_reward":
            if door_type != "TRAP" or hook != "before_enter":
                return {}
            if runtime.get("converted"):
                return {"skip_default_enter": True}
            reward = extension.get("reward", {})
            if not isinstance(reward, dict):
                reward = {}
            reward_door = DoorEnum.REWARD.create_instance(
                controller=self.controller,
                reward=dict(reward),
                hint=extension.get("hint", "神佑余辉"),
            )
            runtime["converted"] = True
            return {"replacement_door": reward_door}

        return {}

    def apply_battle_extension(
        self,
        extension: Dict[str, Any],
        trigger: str,
        attacker: Any,
        defender: Any,
        damage: int,
    ) -> int:
        """统一扩展入口：仅处理当前怪物门声明的扩展。"""
        if not isinstance(extension, dict):
            return damage
        ext_type = extension.get("extension_type")
        if ext_type == "puppet_dark_boss":
            return self._apply_puppet_runtime_modifiers(
                extension=extension,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=damage,
            )
        if ext_type == "elf_rival_final_boss":
            return self._apply_elf_rival_runtime_modifiers(
                extension=extension,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=damage,
            )
        if ext_type == "puppet_echo_final":
            state = extension.get("state")
            if isinstance(state, dict):
                if trigger == "player_attack":
                    echo_lines = state.get("echo_lines") or []
                    idx = int(state.get("echo_index", 0))
                    if echo_lines:
                        line = echo_lines[idx % len(echo_lines)]
                        if isinstance(line, str) and line.strip():
                            self.controller.add_message(f"木偶的回声低语：「{line}」")
                        state["echo_index"] = idx + 1
                elif trigger == "monster_attack":
                    echo_lines = state.get("echo_lines") or []
                    valid = [ln for ln in echo_lines if isinstance(ln, str) and ln.strip()]
                    if valid:
                        mi = int(state.get("echo_monster_attack_idx", 0))
                        line = valid[mi % len(valid)]
                        state["echo_monster_attack_idx"] = mi + 1
                        self.controller.add_message(f"木偶的回声压过来：「{line}」")
            return damage
        return damage

    def handle_battle_extension_post_player_attack(self, extension: Dict[str, Any], target: Any) -> None:
        """统一扩展后处理入口。"""
        if not isinstance(extension, dict):
            return
        ext_type = extension.get("extension_type")
        if ext_type == "puppet_dark_boss":
            self._try_trigger_puppet_phase_two(extension=extension, target=target)
        if ext_type == "elf_rival_final_boss":
            self._try_trigger_elf_rival_counter(extension=extension, target=target)

    # 兼容旧接口：若调用方仍直接走 StorySystem，则透传到当前战斗扩展。
    def apply_puppet_combat_modifiers(self, trigger: str, attacker: Any, defender: Any, damage: int) -> int:
        extensions = getattr(self.controller, "current_battle_extensions", []) or []
        adjusted = damage
        for ext in extensions:
            adjusted = self.apply_battle_extension(
                extension=ext,
                trigger=trigger,
                attacker=attacker,
                defender=defender,
                damage=adjusted,
            )
        return adjusted

    def try_trigger_puppet_phase_two(self, monster: Any) -> bool:
        extensions = getattr(self.controller, "current_battle_extensions", []) or []
        switched = False
        for ext in extensions:
            switched = self._try_trigger_puppet_phase_two(extension=ext, target=monster) or switched
        return switched

    def _elf_rival_speak_next_grudge(self, state: Dict[str, Any], runtime: Dict[str, Any]) -> None:
        """依次播放支线记录的恩怨句；记满后改用 grudge_bark_fillers 循环，避免只剩身法句。"""
        specific = [
            x
            for x in (state.get("grudge_barks") if isinstance(state.get("grudge_barks"), list) else [])
            if isinstance(x, str) and x.strip()
        ]
        fillers = [
            x
            for x in (state.get("grudge_bark_fillers") if isinstance(state.get("grudge_bark_fillers"), list) else [])
            if isinstance(x, str) and x.strip()
        ]
        if not specific and not fillers:
            return
        i = int(runtime.setdefault("grudge_voice_idx", 0))
        if i < len(specific):
            line = specific[i]
        elif fillers:
            line = fillers[(i - len(specific)) % len(fillers)]
        else:
            return
        runtime["grudge_voice_idx"] = i + 1
        if isinstance(line, str) and line.strip():
            self.controller.add_message(f"莱希娅：「{line.strip()}」")

    def _apply_elf_rival_runtime_modifiers(
        self,
        extension: Dict[str, Any],
        trigger: str,
        attacker: Any,
        defender: Any,
        damage: int,
    ) -> int:
        """银羽终局战斗扩展：根据关系分支提供台词与招式。"""
        state = extension.get("state")
        if not isinstance(state, dict):
            return damage
        runtime = state.setdefault("runtime", {})
        counts = runtime.setdefault("trigger_counts", {})

        adjusted = max(1, int(damage))
        if trigger == "monster_attack":
            idx = int(counts.get("monster_attack", 0))
            boosts = state.get("shadowstep_boost", [])
            lines = state.get("lines", {}) if isinstance(state.get("lines", {}), dict) else {}
            if idx < len(boosts):
                self._elf_rival_speak_next_grudge(state, runtime)
                boost = max(0.0, float(boosts[idx]))
                adjusted = max(1, int(round(adjusted * (1.0 + boost))))
                line = lines.get("shadowstep", "")
                if isinstance(line, str) and line.strip():
                    self.controller.add_message(line.strip())
                self.controller.add_message(f"她抓住你的一瞬迟疑，伤害 {damage}→{adjusted}。")
            else:
                banter = state.get("attack_banter", [])
                pool = [b for b in banter if isinstance(b, str) and b.strip()]
                if pool:
                    self.controller.add_message(random.choice(pool))
                else:
                    fallback = lines.get("shadowstep", "")
                    if isinstance(fallback, str) and fallback.strip():
                        self.controller.add_message(fallback.strip())
            counts["monster_attack"] = idx + 1
        return adjusted

    def _try_trigger_elf_rival_counter(self, extension: Dict[str, Any], target: Any) -> None:
        """玩家攻击后判定银羽的扰敌技。"""
        if not target or not bool(getattr(target, "story_elf_rival_final_boss", False)):
            return
        state = extension.get("state")
        if not isinstance(state, dict):
            return
        runtime = state.setdefault("runtime", {})
        counts = runtime.setdefault("trigger_counts", {})
        idx = int(counts.get("post_player_attack", 0))
        turn_cfg = state.get("debuff_turns", [])
        if idx >= len(turn_cfg):
            return
        duration = max(1, int(turn_cfg[idx]))
        mode = str(state.get("debuff_mode", "weak")).strip().lower()
        player = getattr(self.controller, "player", None)
        if player is None:
            return
        effect = StatusName.POISON if mode == "poison" else StatusName.WEAK
        player.apply_status(effect.create_instance(duration=duration, target=player))
        self._elf_rival_speak_next_grudge(state, runtime)
        lines = state.get("lines", {}) if isinstance(state.get("lines", {}), dict) else {}
        line = lines.get("debuff", "")
        if isinstance(line, str) and line.strip():
            self.controller.add_message(line.strip())
        label = "中毒" if effect == StatusName.POISON else "虚弱"
        self.controller.add_message(f"你的节奏被打断，获得{label}（{duration}回合）。")
        counts["post_player_attack"] = idx + 1
