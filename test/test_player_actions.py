import unittest
from server import GameController, Player, BattleScene
from models.monster import Monster
from models import items
from models.status import StatusName

class TestPlayerActions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.player = self.controller.player

    def test_player_healing(self):
        """测试玩家治疗"""
        initial_hp = self.player.hp
        self.player.take_damage(10)
        self.assertEqual(self.player.hp, initial_hp - 10)
        self.player.heal(5)
        self.assertEqual(self.player.hp, initial_hp - 5)

    def test_player_gold(self):
        """测试玩家金币"""
        initial_gold = self.player.gold
        self.player.add_gold(10)
        self.assertEqual(self.player.gold, initial_gold + 10)

    def test_player_status_effects(self):
        """测试玩家状态效果"""
        # 测试添加状态效果
        self.player.apply_status(StatusName.POISON.create_instance(duration=3, target=self.player))
        self.assertTrue(self.player.has_status(StatusName.POISON))
        
        # 测试状态效果描述
        status_desc = self.player.get_status_desc()
        self.assertIn("中毒", status_desc)

    def test_poison_damage(self):
        """测试中毒效果造成的伤害"""
        # 设置玩家生命值为100
        self.player.hp = 100
        # 添加中毒状态
        self.player.apply_status(StatusName.POISON.create_instance(duration=3, target=self.player))
        
        # 应用回合效果
        self.player.battle_status_duration_pass()
        
        # 验证生命值减少了10%（10点）
        self.assertEqual(self.player.hp, 90)
        
        # 验证消息是否被添加到控制器
        self.assertIn("中毒效果造成 10 点伤害！", self.controller.messages)

    def test_stun_effect(self):
        """测试玩家在晕眩状态下无法行动"""
        # 创建战斗场景
        battle_scene = BattleScene(self.controller)
        battle_scene.monster = Monster("测试怪物", 20, 1, effect_probability=0)
        self.controller.current_monster = battle_scene.monster
        
        # 添加晕眩状态
        self.player.apply_status(StatusName.STUN.create_instance(duration=3, target=self.player))
        
        # 测试无法攻击
        battle_scene.handle_choice(0)  # 尝试攻击
        self.assertTrue(
            any(msg.startswith("你处于眩晕状态") for msg in self.controller.messages),
            "应该显示眩晕状态消息"
        )
        # 测试晕眩状态持续时间减少
        self.assertEqual(self.player.get_status_duration(StatusName.STUN), 2)
        
        # 测试无法使用道具
        # 添加一个治疗药水到背包
        healing_potion = items.HealingPotion("治疗药水", heal_amount=10, cost=5)
        self.player.add_item(healing_potion)
        
        battle_scene.handle_choice(1)  # 尝试使用道具
        self.assertTrue(
            any(msg.startswith("你处于眩晕状态") for msg in self.controller.messages),
            "应该显示眩晕状态消息"
        )

        # 测试晕眩状态结束后可以正常行动
        self.player.battle_status_duration_pass()
        self.assertFalse(self.player.has_status(StatusName.STUN))
        
        # 清除之前的消息
        self.controller.clear_messages()
        
        # 验证可以正常攻击
        battle_scene.handle_choice(0)  # 尝试攻击
        self.assertFalse(
            any(msg.startswith("你处于眩晕状态") for msg in self.controller.messages),
            "不应该显示眩晕状态消息"
        )
        
        # 清除之前的消息
        self.controller.clear_messages()
        
        # 验证可以正常使用道具
        battle_scene.handle_choice(1)
        self.assertFalse(
            any(msg.startswith("你处于眩晕状态") for msg in self.controller.messages),
            "不应该显示眩晕状态消息"
        )

    def test_immunity_effect(self):
        """测试免疫效果"""
        # 先给玩家添加免疫状态
        immune_status = StatusName.IMMUNE.create_instance(duration=5, target=self.controller.player)
        self.controller.player.apply_status(immune_status)
        self.assertTrue(self.controller.player.has_status(StatusName.IMMUNE), "玩家应该具有免疫状态")
        
        # 测试免疫效果对负面状态的影响
        # 1. 测试免疫效果对虚弱状态的影响
        self.controller.clear_messages()  # 清除之前的消息
        weak_status = StatusName.WEAK.create_instance(duration=3, target=self.controller.player)
        self.controller.player.apply_status(weak_status)
        self.assertFalse(self.controller.player.has_status(StatusName.WEAK), "免疫效果应该阻止虚弱状态")
        self.assertTrue(
            any("免疫效果保护了你免受 虚弱 效果!" in msg for msg in self.controller.messages),
            "应该显示免疫保护消息"
        )
        
        # 2. 测试免疫效果对中毒状态的影响
        self.controller.clear_messages()  # 清除之前的消息
        poison_status = StatusName.POISON.create_instance(duration=3, target=self.controller.player)
        self.controller.player.apply_status(poison_status)
        self.assertFalse(self.controller.player.has_status(StatusName.POISON), "免疫效果应该阻止中毒状态")
        self.assertTrue(
            any("免疫效果保护了你免受 中毒 效果!" in msg for msg in self.controller.messages),
            "应该显示免疫保护消息"
        )
        
        # 3. 测试免疫效果对晕眩状态的影响
        self.controller.clear_messages()  # 清除之前的消息
        stun_status = StatusName.STUN.create_instance(duration=2, target=self.controller.player)
        self.controller.player.apply_status(stun_status)
        self.assertFalse(self.controller.player.has_status(StatusName.STUN), "免疫效果应该阻止晕眩状态")
        self.assertTrue(
            any("免疫效果保护了你免受 晕眩 效果!" in msg for msg in self.controller.messages),
            "应该显示免疫保护消息"
        )
        
        # 4. 测试免疫效果对正面状态的影响
        # 4.1 测试攻击力翻倍状态
        self.controller.clear_messages()  # 清除之前的消息
        atk_multiplier_status = StatusName.ATK_MULTIPLIER.create_instance(duration=1, target=self.controller.player, value=2)
        self.controller.player.apply_status(atk_multiplier_status)
        self.assertTrue(self.controller.player.has_status(StatusName.ATK_MULTIPLIER), "免疫效果不应该阻止攻击力翻倍状态")
        self.assertFalse(
            any("免疫效果保护了你免受" in msg for msg in self.controller.messages),
            "不应该显示免疫保护消息"
        )
        
        # 4.2 测试攻击力提升状态
        self.controller.clear_messages()  # 清除之前的消息
        atk_up_status = StatusName.ATK_UP.create_instance(duration=5, target=self.controller.player, value=2)
        self.controller.player.apply_status(atk_up_status)
        self.assertTrue(self.controller.player.has_status(StatusName.ATK_UP), "免疫效果不应该阻止攻击力提升状态")
        self.assertFalse(
            any("免疫效果保护了你免受" in msg for msg in self.controller.messages),
            "不应该显示免疫保护消息"
        ) 