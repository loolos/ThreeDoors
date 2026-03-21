"""
道具系统测试
"""
from test.test_base import BaseTest
from models import items
from models.game_config import GameConfig
from models.status import StatusName
from models.items import ItemType
from unittest.mock import patch

class TestItemSystem(BaseTest):
    """道具系统测试类"""
    
    def test_scroll_effect_stacking(self):
        """测试卷轴效果叠加"""
        # 给玩家添加减伤卷轴效果
        self.apply_status_to_player(StatusName.DAMAGE_REDUCTION, duration=5)
        self.player.statuses[StatusName.DAMAGE_REDUCTION].value = 0.7 # 确保value存在
        
        # 创建并使用卷轴
        scroll = items.DamageReductionScroll("减伤卷轴", cost=10, duration=10)
        scroll.acquire(player=self.player)
        scroll.effect(target=self.player)
        
        # 检查状态
        actual_duration = self.player.get_status_duration(StatusName.DAMAGE_REDUCTION)
        self.assertEqual(actual_duration, 15)

    def test_flying_hammer(self):
        """测试飞锤效果"""
        # 创建怪物
        monster = self.create_test_monster()
        self.controller.current_monster = monster
        
        # 添加并使用飞锤
        flying_hammer = items.FlyingHammer("飞锤", cost=0, duration=3)
        self.player.add_item(flying_hammer)
        
        # 使用飞锤
        flying_hammer.effect(player=self.player, monster=monster)
        
        # 验证效果
        self.assertTrue(monster.has_status(StatusName.STUN))
        self.assertEqual(monster.get_status_duration(StatusName.STUN), 3)

    def test_giant_scroll(self):
        """测试巨大卷轴效果"""
        giant_scroll = items.GiantScroll("巨大卷轴", cost=0, duration=3)
        self.player.add_item(giant_scroll)
        
        # 记录初始攻击力
        initial_atk = self.player.atk
        
        # 使用卷轴
        giant_scroll.effect(player=self.player)
        
        # 验证效果
        self.assertTrue(self.player.has_status(StatusName.ATK_MULTIPLIER))
        self.assertEqual(self.player.atk, initial_atk * 2)

    def test_barrier(self):
        """测试结界效果"""
        barrier = items.Barrier("结界", cost=0, duration=3)
        self.player.add_item(barrier)
        
        # 使用结界
        barrier.effect(player=self.player)
        
        # 验证效果
        self.assertTrue(self.player.has_status(StatusName.BARRIER))
        
        # 测试递减减伤效果：90% -> 80% -> 70%
        monster = self.create_test_monster(atk=10)
        initial_hp = self.player.hp
        with patch("models.monster.random.randint", return_value=0):
            monster.attack(self.player)
            self.assertEqual(self.player.hp, initial_hp - 1)

            monster.attack(self.player)
            self.assertEqual(self.player.hp, initial_hp - 3)

            monster.attack(self.player)
            self.assertEqual(self.player.hp, initial_hp - 6)

    def test_revive_scroll(self):
        """测试复活卷轴效果"""
        self.clear_player_inventory()
        revive_scroll = items.ReviveScroll("复活卷轴", cost=0)
        self.player.add_item(revive_scroll)
        
        # 致死伤害
        self.player.take_damage(self.player.hp + 100)
        
        # 验证是否存活且消耗了卷轴
        self.assertGreater(self.player.hp, 0)
        passive_items = self.player.get_items_by_type(ItemType.PASSIVE)
        self.assertFalse(any(item.name == "复活卷轴" for item in passive_items))

    def test_create_random_item_supports_treasure_tier(self):
        """create_random_item 的宝物 tier 参数应影响装备强度。"""
        with patch("models.items.random.choices", return_value=["equip"]):
            item = items.create_random_item(treasure_tier=4)

        self.assertIsInstance(item, items.Equipment)
        self.assertEqual(item.atk_bonus, 8)
        all_names = [
            name
            for name_pool in GameConfig.EQUIPMENT_NAME_POOLS.values()
            for name in name_pool
        ]
        self.assertIn(item.name, all_names)
