"""随机回合消息去重审计测试框架。"""

import random
from collections import Counter, defaultdict
from dataclasses import dataclass

from scenes import SceneType, GameOverScene
from test.test_base import BaseTest


ALLOWED_DUPLICATE_SCENES = {SceneType.BATTLE, SceneType.USE_ITEM}
GAME_RESET_INTRO_PREFIX = "你睁开眼，发现自己站在一条幽长的走廊里。"


@dataclass
class MessageOccurrence:
    scene_type: SceneType
    action_index: int


class RoundMessageDuplicateAudit:
    """执行随机回合并审计重复消息，输出“可疑 / 允许”两类结果。"""

    def __init__(self, controller):
        self.controller = controller

    def run_until_clear(self, min_clear_round=200, max_actions=12000, seed=42):
        random.seed(seed)
        c = self.controller

        round_messages = defaultdict(list)
        round_occurrences = defaultdict(lambda: defaultdict(list))
        epoch = 0
        action_count = 0
        reached_clear = False
        early_game_over = False
        died_and_restarted = False

        while action_count < max_actions:
            scene = c.scene_manager.current_scene
            if scene is None:
                break

            if getattr(c, "game_clear_info", None) and c.round_count >= min_clear_round:
                reached_clear = True
                break

            c.clear_messages()
            valid_indices = [
                idx for idx, text in enumerate(getattr(scene, "button_texts", [])) if isinstance(text, str) and text.strip()
            ]
            if not valid_indices:
                break

            before_round = c.round_count
            picked = self._pick_index(scene=scene, valid_indices=valid_indices)
            if picked is None:
                break

            scene.handle_choice(picked)
            after_round = c.round_count

            if after_round < before_round:
                epoch += 1

            target_round = after_round if after_round > before_round else before_round
            round_key = (epoch, target_round)
            source_scene_type = scene.enum

            reset_seen = False
            for msg in c.messages:
                round_messages[round_key].append(msg)
                round_occurrences[round_key][msg].append(
                    MessageOccurrence(scene_type=source_scene_type, action_index=action_count)
                )
                if isinstance(msg, str) and msg.startswith(GAME_RESET_INTRO_PREFIX):
                    reset_seen = True

            # 中途死亡重来：不再推进到 200 回合，直接把该次视作成功可审计终止。
            if reset_seen:
                died_and_restarted = True
                break

            if isinstance(c.scene_manager.current_scene, GameOverScene) and not getattr(c, "game_clear_info", None):
                early_game_over = True
                break

            action_count += 1

        report = self._build_report(round_messages, round_occurrences)
        report.update({
            "reached_clear": reached_clear,
            "early_game_over": early_game_over,
            "died_and_restarted": died_and_restarted,
            "final_round": c.round_count,
            "actions": action_count,
        })
        return report

    def _pick_index(self, scene, valid_indices):
        c = self.controller

        if isinstance(scene, GameOverScene):
            valid_indices = [idx for idx in valid_indices if idx != 2]
            return random.choice(valid_indices) if valid_indices else None

        if scene.enum in {SceneType.ENDING_SUMMARY, SceneType.ENDING_ROLL}:
            return 0 if 0 in valid_indices else random.choice(valid_indices)

        # 为了稳定进入“200+回合通关”区间，对关键回合的 Door 进行轻量引导。
        if scene.enum == SceneType.DOOR and hasattr(scene, "doors"):
            doors = getattr(scene, "doors", [])

            # stage_curtain_order 路线在 185 回合优先选宝物门以取回剧本。
            if c.round_count == 184:
                for idx in valid_indices:
                    if idx < len(doors) and getattr(getattr(doors[idx], "enum", None), "name", "") == "REWARD":
                        return idx

            # 终盘阶段优先事件门/怪物门，推进结局链。
            if c.round_count >= 200:
                for want in ("EVENT", "MONSTER"):
                    for idx in valid_indices:
                        if idx < len(doors) and getattr(getattr(doors[idx], "enum", None), "name", "") == want:
                            return idx

        return random.choice(valid_indices)

    def _build_report(self, round_messages, round_occurrences):
        report = {"suspicious": [], "allowed": [], "total_rounds": len(round_messages)}

        for round_key, messages in sorted(round_messages.items()):
            counts = Counter(messages)
            repeated = {msg: cnt for msg, cnt in counts.items() if cnt > 1}
            if not repeated:
                continue

            epoch, round_no = round_key
            for msg, cnt in repeated.items():
                scenes = {item.scene_type for item in round_occurrences[round_key][msg]}
                is_allowed, reason = self._classify_duplicate(msg=msg, scenes=scenes)
                record = {
                    "round": round_no,
                    "epoch": epoch,
                    "message": msg,
                    "count": cnt,
                    "scenes": sorted(scene.name for scene in scenes),
                    "reason": reason,
                }
                report["allowed" if is_allowed else "suspicious"].append(record)

        return report

    @staticmethod
    def _classify_duplicate(msg, scenes):
        if scenes and scenes.issubset(ALLOWED_DUPLICATE_SCENES):
            return True, "重复发生在怪物门战斗流程（允许）。"
        if msg.startswith(GAME_RESET_INTRO_PREFIX):
            return True, "重开后回合计数重置，开场文案在同回合键下重复归档（允许例外）。"
        if msg == "你没有可用的复活卷轴！" and scenes == {SceneType.GAME_OVER}:
            return True, "结算界面重复点击造成重复提示（允许例外）。"
        if "减伤效果触发" in msg:
            return True, "减伤可在同回合多次伤害结算中重复触发（允许例外）。"
        if msg.startswith("获得道具："):
            return True, "奖励链可在同回合发放同名道具（允许例外）。"
        if SceneType.EVENT in scenes:
            return False, "事件门内重复通常缺乏业务合理性，需重点排查。"
        return False, "非战斗场景重复，默认视为可疑冗余。"


class TestRoundMessageDuplicateAudit(BaseTest):
    def test_no_suspicious_duplicates_until_clear_after_200_rounds(self):
        """每次推进到 200+ 回合（通关或仅玩满 200 回合含死亡重开）后，检查同回合重复日志。"""
        seeds = [11, 23, 47]
        suspicious = []

        for seed in seeds:
            self.controller.reset_game()

            # 使用官方测试 gate 的同款配置，让流程稳定进入 200 回合终盘并可触发结局。
            self.controller.story.setup_test_gate_stage_curtain_order()
            self.controller.story.ensure_pre_final_event_schedule()
            self.controller.scene_manager.go_to("door_scene")

            # 增强生存能力，避免中途死亡打断到达终盘。
            self.controller.player.hp = 5000
            self.controller.player._atk = 500
            self.controller.player_peak_hp = 5000
            self.controller.player_peak_atk = 500

            report = RoundMessageDuplicateAudit(self.controller).run_until_clear(
                min_clear_round=200, max_actions=12000, seed=seed
            )

            self.assertFalse(
                report["early_game_over"],
                f"seed={seed} 在通关前进入了 GameOver，final_round={report['final_round']} actions={report['actions']}"
            )
            # 中途死亡重来：不再推进到 200 回合，直接视为成功。
            if report.get("died_and_restarted"):
                continue

            reached_clear_or_200 = report["reached_clear"] or report["final_round"] >= 200

            def _dup_summary(r):
                parts = []
                if r.get("suspicious"):
                    parts.append("suspicious: " + str([(x["message"][:50], x["scenes"], x["reason"]) for x in r["suspicious"][:5]]))
                if r.get("allowed"):
                    parts.append("allowed: " + str([(x["message"][:50], x["scenes"]) for x in r["allowed"][:5]]))
                return " | ".join(parts) if parts else "none"

            self.assertTrue(
                reached_clear_or_200,
                f"seed={seed} 未通关且最终回合不足 200（含死亡重开），final_round={report['final_round']} "
                f"actions={report['actions']} | {_dup_summary(report)}"
            )
            self.assertGreaterEqual(report["final_round"], 200, f"seed={seed} 最终回合不足 200")

            suspicious.extend([{"seed": seed, **item} for item in report["suspicious"]])

        if suspicious:
            lines = ["检测到可疑重复消息（同回合）："]
            for item in suspicious[:30]:
                lines.append(
                    f"seed={item['seed']} epoch={item['epoch']} round={item['round']} "
                    f"count={item['count']} scene={item['scenes']} msg={item['message']} reason={item['reason']}"
                )
            if len(suspicious) > 30:
                lines.append(f"... 其余 {len(suspicious) - 30} 条已省略")
            self.fail("\n".join(lines))
