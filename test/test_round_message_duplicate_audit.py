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

    def run(self, max_rounds=100, max_actions=8000, seed=42):
        random.seed(seed)
        c = self.controller

        round_messages = defaultdict(list)
        round_occurrences = defaultdict(lambda: defaultdict(list))
        epoch = 0
        action_count = 0

        while c.round_count < max_rounds and action_count < max_actions:
            scene = c.scene_manager.current_scene
            if scene is None:
                break

            c.clear_messages()
            valid_indices = [
                idx for idx, text in enumerate(getattr(scene, "button_texts", [])) if isinstance(text, str) and text.strip()
            ]
            if not valid_indices:
                break
            if isinstance(scene, GameOverScene):
                valid_indices = [idx for idx in valid_indices if idx != 2]
                if not valid_indices:
                    break

            before_round = c.round_count
            picked = random.choice(valid_indices)
            scene.handle_choice(picked)
            after_round = c.round_count

            if after_round < before_round:
                epoch += 1

            target_round = after_round if after_round > before_round else before_round
            round_key = (epoch, target_round)
            source_scene_type = scene.enum

            for msg in c.messages:
                round_messages[round_key].append(msg)
                round_occurrences[round_key][msg].append(MessageOccurrence(scene_type=source_scene_type, action_index=action_count))

            action_count += 1

        return self._build_report(round_messages, round_occurrences)

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
        # 1) 战斗场景重复：允许（连续攻击/多段效果本就可能重复提示）
        if scenes and scenes.issubset(ALLOWED_DUPLICATE_SCENES):
            return True, "重复发生在怪物门战斗流程（允许）。"

        # 2) 已知合理例外：死亡后重开在同一回合内可能多次触发开场文案
        if msg.startswith(GAME_RESET_INTRO_PREFIX):
            return True, "重开后回合计数重置，开场文案在同回合键下重复归档（允许例外）。"

        # 3) 已知合理例外：GameOver 连续点击“复活卷轴”会重复提示
        if msg == "你没有可用的复活卷轴！" and scenes == {SceneType.GAME_OVER}:
            return True, "结算界面重复点击造成重复提示（允许例外）。"

        # 4) 已知合理例外：减伤是多处伤害链路共用提示，单回合可能触发多次
        if "减伤效果触发" in msg:
            return True, "减伤可在同回合多次伤害结算中重复触发（允许例外）。"

        # 5) 已知合理例外：同回合可能获得多个同名道具
        if msg.startswith("获得道具："):
            return True, "奖励链可在同回合发放同名道具（允许例外）。"

        # 6) 默认策略：事件门重复应优先拦截
        if SceneType.EVENT in scenes:
            return False, "事件门内重复通常缺乏业务合理性，需重点排查。"

        return False, "非战斗场景重复，默认视为可疑冗余。"


class TestRoundMessageDuplicateAudit(BaseTest):
    def test_no_suspicious_duplicates_in_100_rounds(self):
        """100 回合随机流程中，除例外外不应存在同回合重复消息。"""
        seeds = [7, 13, 29, 42, 87]
        suspicious = []
        allowed = []

        for seed in seeds:
            self.controller.reset_game()
            report = RoundMessageDuplicateAudit(self.controller).run(max_rounds=100, seed=seed)
            suspicious.extend([{"seed": seed, **item} for item in report["suspicious"]])
            allowed.extend([{"seed": seed, **item} for item in report["allowed"]])

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

        for item in allowed:
            self.assertTrue(item["reason"])
