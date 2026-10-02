"""
怪物系统测试
"""
from test.test_base import BaseTest
from models.items import ItemType
from models import items
from models.monster import Monster, get_random_monster, estimate_player_power
from types import SimpleNamespace
from unittest.mock import patch
import random

class TestMonsterSystem(BaseTest):
    """怪物系统测试类"""
    
    def test_loot_generation(self):
        """测试掉落生成"""
        import traceback
        try:
            # 尝试多次以确保覆盖掉落情况
            has_loot = False
            for _ in range(20):
                monster = Monster("测试怪物", 10, 5, tier=1)
                if monster.loot:
                    has_loot = True
                    self.assertIsInstance(monster.loot[0], items.GoldBag)
                    break
            self.assertTrue(has_loot, "Should generate loot at least once in 20 tries")
        except Exception:
            traceback.print_exc()
            raise
        # 高级怪可能有更多掉落
        # 并非绝对，因为是概率掉落，但在大量测试中应能覆盖

    def test_loot_treasure_uses_create_random_item_with_tier(self):
        """怪物额外宝物掉落应使用 create_random_item，并传入怪物 tier。"""
        fixed_item = items.Barrier("结界", duration=2, cost=0)
        with patch("models.monster.create_random_item", return_value=fixed_item) as mock_create:
            monster = Monster("测试怪物", 10, 5, tier=4)

        mock_create.assert_called_once_with(treasure_tier=4)
        self.assertIsInstance(monster.loot[0], items.GoldBag)
        self.assertGreaterEqual(monster.loot[0].gold_amount, 20)
        self.assertLessEqual(monster.loot[0].gold_amount, 60)
        self.assertIs(monster.loot[1], fixed_item)

    def test_loot_application(self):
        """测试掉落应用"""
        monster = self.create_test_monster(name="测试怪物")
        # 强制设置掉落
        hammer = items.FlyingHammer("飞锤", cost=5, duration=3)
        monster.loot = [hammer]
        
        # 击杀处理掉落
        old_size = self.player.get_inventory_size()
        monster.process_loot(self.player)
        
        self.assertEqual(self.player.get_inventory_size(), old_size + 1)
        self.assertTrue(any("掉落：飞锤" in m for m in self.controller.messages), "日志应包含掉落信息")

    def test_monster_attributes(self):
        """测试怪物属性初始化"""
        m = Monster(tier=3)
        self.assertEqual(m.tier, 3)
        self.assertIsNotNone(m.name)
        self.assertIsNotNone(m.hp)
        self.assertIsNotNone(m.atk)

    def test_monster_custom_name_no_keyerror(self):
        """自定义怪物名不在 MONSTER_TYPE_HINTS 时不应 KeyError"""
        m = Monster(name="自定义未知怪", hp=20, atk=5, tier=1)
        self.assertEqual(m.tier, 1)
        self.assertIsInstance(m.type_hint, str)
        self.assertTrue(len(m.type_hint) > 0)

    def test_random_monster_scales_with_player_power(self):
        """玩家属性导致的怪物增强应从40回合后才生效。"""
        weak_player = SimpleNamespace(_atk=6, atk=6, hp=50, gold=10)
        strong_player = SimpleNamespace(_atk=300, atk=300, hp=1600, gold=400)

        random.seed(20260310)
        weak_pack = [get_random_monster(current_round=28, player=weak_player) for _ in range(40)]
        random.seed(20260310)
        strong_pack = [get_random_monster(current_round=28, player=strong_player) for _ in range(40)]

        weak_avg_hp = sum(m.hp for m in weak_pack) / len(weak_pack)
        strong_avg_hp = sum(m.hp for m in strong_pack) / len(strong_pack)
        weak_avg_atk = sum(m.atk for m in weak_pack) / len(weak_pack)
        strong_avg_atk = sum(m.atk for m in strong_pack) / len(strong_pack)
        # 40回合前不应因玩家属性差异出现额外强化
        self.assertEqual(strong_avg_hp, weak_avg_hp)
        self.assertEqual(strong_avg_atk, weak_avg_atk)

        random.seed(20260310)
        weak_pack_late = [get_random_monster(current_round=70, player=weak_player) for _ in range(40)]
        random.seed(20260310)
        strong_pack_late = [get_random_monster(current_round=70, player=strong_player) for _ in range(40)]

        weak_avg_hp_late = sum(m.hp for m in weak_pack_late) / len(weak_pack_late)
        strong_avg_hp_late = sum(m.hp for m in strong_pack_late) / len(strong_pack_late)
        weak_avg_atk_late = sum(m.atk for m in weak_pack_late) / len(weak_pack_late)
        strong_avg_atk_late = sum(m.atk for m in strong_pack_late) / len(strong_pack_late)
        weak_avg_effect_late = sum(m.effect_probability for m in weak_pack_late) / len(weak_pack_late)
        strong_avg_effect_late = sum(m.effect_probability for m in strong_pack_late) / len(strong_pack_late)

        # 后期高战力应带来更高攻击与更强状态概率，且整体耐久更高
        self.assertGreater(strong_avg_hp_late, weak_avg_hp_late)
        self.assertGreater(strong_avg_atk_late, weak_avg_atk_late)
        self.assertGreater(strong_avg_effect_late, weak_avg_effect_late)

    def test_tier6_monster_stats_are_massively_boosted(self):
        """最高 tier 怪物应达到超高血量与攻击。"""
        tier6 = Monster.MONSTER_TYPES[6]
        self.assertTrue(all(hp >= 1000 for _, hp, _ in tier6))
        self.assertTrue(all(atk >= 100 for _, _, atk in tier6))

    def test_unlocked_tier_limits_generated_monster_tier(self):
        """即使在高回合，未解锁的 tier 也不应生成。"""
        random.seed(20260312)
        pack = [
            get_random_monster(current_round=99, unlocked_tier=3, player=None)
            for _ in range(80)
        ]
        self.assertTrue(all(m.tier <= 3 for m in pack))

    def test_estimate_player_power_examples(self):
        """estimate_player_power()：用固定输入验证示例计算结果。"""
        # 1) current_round=20, hp=200, atk=50, gold=100
        p1 = SimpleNamespace(hp=200, atk=50, gold=100)
        self.assertEqual(estimate_player_power(player=p1, current_round=20), 65.5)

        # 2) current_round=100, hp=1000, atk=200, gold=400
        p2 = SimpleNamespace(hp=1000, atk=200, gold=400)
        self.assertEqual(estimate_player_power(player=p2, current_round=100), 318)

        # 3) current_round=200, hp=0, atk=200, gold=400
        p3 = SimpleNamespace(hp=0, atk=200, gold=400)
        self.assertEqual(estimate_player_power(player=p3, current_round=200), 438)

        # 4) current_round=200, hp=2000, atk=400, gold=1000（gold 会被 cap 到 400）
        p4 = SimpleNamespace(hp=2000, atk=400, gold=1000)
        self.assertEqual(estimate_player_power(player=p4, current_round=200), 628)

    def test_default_final_boss_attack_emits_taunt_without_battle_extension(self):
        """终局 Boss 攻击时应播出嘲讽台词，且不依赖门上的 battle_extensions。"""
        self.controller.clear_messages()
        boss = Monster(name="选择困难症候群", hp=100, atk=3, tier=4)
        setattr(boss, "story_default_final_boss", True)
        setattr(boss, "story_default_final_boss_attack_taunts", ["\u201c测试嘲讽\u201d"])
        self.player.hp = 500
        boss.attack(self.player)
        self.assertTrue(
            any("选择困难症候群" in m and "测试嘲讽" in m for m in self.controller.messages),
            self.controller.messages,
        )
