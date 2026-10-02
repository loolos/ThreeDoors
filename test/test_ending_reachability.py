"""结局可达性穷举测试：任意剧情状态组合从第 184 回合起继续游玩，都必须在有限回合内达成某个结局。

枚举的状态维度（与 docs/storyline.md 终局决策树的条件一一对应）：
- 飞贼线：未开启 / 进行中 / 已收束（关系 -5、0、4）
- 是否拿到飞贼钥匙
- 是否已取回剧本
- 木偶线：未开启 / 进行中 / 已击败 / 曾逃跑
- 木偶邪恶值：低（20）/ 高（60）
- 梦境井与镜面剧场是否都已完结

每种组合再按三种事件选项策略 × 两种战斗策略（一直攻击 / 每种怪第一次遇到先逃跑）各跑一局。
玩家数值拉满以排除战斗失败，只检验剧情调度是否存在走不到结局的死路。
"""
import io
import itertools
import random
import contextlib
import unittest
from unittest import mock

from server import GameController
from models.player import Player

START_ROUND = 184
MAX_DOOR_PICKS = 80

ELF_STATES = ("none", "started", "ended:-5", "ended:0", "ended:4")
PUPPET_STATES = ("none", "active", "defeated", "escaped")
CHOICE_POLICIES = (0, 1, 2)
BATTLE_POLICIES = ("fight", "escape_first")


def _setup_state(game, elf, key, script, puppet, evil, dream_mirror_done):
    story = game.story
    game.round_count = START_ROUND
    player = game.player
    player.hp = 10**7
    player._atk = 10**5
    game.player_peak_hp = player.hp
    game.player_peak_atk = player._atk

    if elf != "none":
        story.elf_chain_started = True
    if elf.startswith("ended"):
        story.elf_chain_ended = True
        story.elf_relation = int(elf.split(":")[1])
        story.story_tags.add("elf_chain_ended")
    story.elf_key_obtained = key
    if key:
        story.story_tags.add("elf_key_obtained")
    if script:
        story.story_tags.add("curtain_call_script_recovered")
    if puppet != "none":
        story.story_tags.add("puppet_arc_active")
    if puppet == "defeated":
        story.story_tags.add("ending:puppet_final_defeated")
        story.puppet_final_outcome = "defeated"
    elif puppet == "escaped":
        story.story_tags.add("ending:puppet_final_escape_recorded")
        story.puppet_final_outcome = "escaped"
    story.puppet_evil_value = evil
    if dream_mirror_done:
        story.choice_flags.update({"dream_well_sealed", "mirror_played_hero"})
    game.scene_manager.go_to("door_scene")


def _play_until_ending(game, choice_policy, battle_policy):
    """按策略自动游玩，返回 (是否达成结局, 已选门次数)。"""
    escaped_names = set()
    picks = 0
    for _ in range(5000):
        if game.game_clear_info:
            return True, picks
        scene = game.scene_manager.current_scene
        name = scene.enum.name
        if name == "GAME_OVER":
            return False, picks
        if name == "DOOR":
            picks += 1
            if picks > MAX_DOOR_PICKS:
                return False, picks
            wanted = game.story.get_required_door_type_for_next_ending(game.round_count)
            index = next(
                (i for i, door in enumerate(scene.doors) if wanted and door.enum.name == wanted),
                0,
            )
            scene.handle_choice(index)
        elif name == "BATTLE":
            monster = scene.monster
            if battle_policy == "escape_first" and monster is not None and monster.name not in escaped_names:
                escaped_names.add(monster.name)
                with mock.patch.object(Player, "try_escape", return_value=True):
                    scene.handle_choice(2)
            else:
                scene.handle_choice(0)
        elif name == "USE_ITEM":
            scene.handle_choice(2)
        elif name == "SHOP":
            game.scene_manager.go_to("door_scene")
        elif name == "EVENT":
            choices = game.current_event.get_choices() if game.current_event else []
            scene.handle_choice(choice_policy % max(1, len(choices)))
        else:
            scene.handle_choice(0)
        game.clear_messages()
    return False, picks


class TestEndingReachability(unittest.TestCase):
    def test_every_story_state_reaches_an_ending(self):
        combos = list(
            itertools.product(
                ELF_STATES,
                (False, True),
                (False, True),
                PUPPET_STATES,
                (20, 60),
                (False, True),
            )
        )
        failures = []
        seed = 0
        for combo in combos:
            for choice_policy in CHOICE_POLICIES:
                for battle_policy in BATTLE_POLICIES:
                    seed += 1
                    random.seed(seed)
                    with contextlib.redirect_stdout(io.StringIO()):
                        game = GameController()
                        _setup_state(game, *combo)
                        reached, _ = _play_until_ending(game, choice_policy, battle_policy)
                    if not reached:
                        failures.append(
                            (combo, choice_policy, battle_policy, game.round_count,
                             sorted(game.story.pending_consequences)[:5])
                        )
        if failures:
            self.fail(
                f"{len(failures)} 种状态组合无法达成结局，前几例（(飞贼, 钥匙, 剧本, 木偶, 邪恶值, 梦境镜面),"
                f" 选项策略, 战斗策略, 回合, pending）：{failures[:5]}"
            )

if __name__ == "__main__":
    unittest.main()
