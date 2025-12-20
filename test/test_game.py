import unittest
import unittest.mock
from server import GameController, Player, DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene, GameConfig
from models.monster import get_random_monster, Monster
import random
from models.items import ItemType, Equipment, HealingScroll, DamageReductionScroll, AttackUpScroll
from models import items
from models.status import Status, StatusName
from models.door import DoorEnum
from scenes import SceneType

class TestGameInitialization(unittest.TestCase):
    """测试游戏初始化"""
    
    def setUp(self):
        self.controller = GameController()
        
    def test_initial_inventory(self):
        """测试初始物品栏"""
        # 检查初始物品数量
        total_items = sum(len(items) for items in self.controller.player.inventory.values())
        self.assertEqual(total_items, 4)
        
    def test_scene_transitions(self):
        """测试场景切换"""
        # 检查初始场景
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 测试场景切换
        self.controller.scene_manager.go_to("battle_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        
        self.controller.scene_manager.go_to("shop_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
        
        self.controller.scene_manager.go_to("door_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

    def test_game_reset(self):
        """测试游戏重置功能"""
        self.player = self.controller.player
        # 修改状态
        self.player.hp = 1
        self.player.gold = 9999
        self.controller.round_count = 10
        self.controller.scene_manager.go_to("game_over_scene")
        
        # 重置
        self.controller.reset_game()
        self.player = self.controller.player # 更新引用
        
        # 验证
        self.assertEqual(self.player.hp, GameConfig.START_PLAYER_HP)
        self.assertEqual(self.player.gold, 0)
        self.assertEqual(self.controller.round_count, 0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

class TestPlayerActions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.controller.player = self.controller.player

    def test_player_healing(self):
        """测试玩家治疗"""
        initial_hp = self.controller.player.hp
        self.controller.player.take_damage(10)
        self.assertEqual(self.controller.player.hp, initial_hp - 10)
        self.controller.player.heal(5)
        self.assertEqual(self.controller.player.hp, initial_hp - 5)

    def test_player_gold(self):
        """测试玩家金币"""
        initial_gold = self.controller.player.gold
        self.controller.player.add_gold(10)
        self.assertEqual(self.controller.player.gold, initial_gold + 10)

    def test_player_status_effects(self):
        """测试玩家状态效果"""
        # 测试添加状态效果
        self.controller.player.apply_status(StatusName.POISON.create_instance(duration=3, target=self.controller.player))
        self.assertTrue(self.controller.player.has_status(StatusName.POISON))
        
        # 测试状态效果描述
        status_desc = self.controller.player.get_status_desc()
        self.assertIn("中毒", status_desc)

    def test_poison_damage(self):
        """测试中毒效果造成的伤害"""
        # 设置玩家生命值为100
        self.controller.player.hp = 100
        # 添加中毒状态
        self.controller.player.apply_status(StatusName.POISON.create_instance(duration=3, target=self.controller.player))
        
        # 应用回合效果
        self.controller.player.battle_status_duration_pass()
        
        # 验证生命值减少了10%（10点）
        self.assertEqual(self.controller.player.hp, 90)
        
        # 验证消息是否被添加到控制器
        self.assertIn("中毒效果造成 10 点伤害！", self.controller.messages)

    def test_stun_effect(self):
        """测试玩家在晕眩状态下无法行动"""
        # 创建战斗场景
        battle_scene = BattleScene(self.controller)
        battle_scene.monster = Monster("测试怪物", 20, 1, effect_probability=0)
        self.controller.current_monster = battle_scene.monster
        
        # 添加晕眩状态
        self.controller.player.apply_status(StatusName.STUN.create_instance(duration=3, target=self.controller.player))
        
        # 测试无法攻击
        battle_scene.handle_choice(0)  # 尝试攻击
        self.assertTrue(
            any(msg.startswith("你处于眩晕状态") for msg in self.controller.messages),
            "应该显示眩晕状态消息"
        )
        # 测试晕眩状态持续时间减少
        self.assertEqual(self.controller.player.get_status_duration(StatusName.STUN), 2)
        
        # 测试无法使用道具
        # 添加一个治疗药水到背包
        healing_potion = items.HealingPotion("治疗药水", heal_amount=10, cost=5)
        self.controller.player.add_item(healing_potion)
        
        battle_scene.handle_choice(1)  # 尝试使用道具
        self.assertTrue(
            any(msg.startswith("你处于眩晕状态") for msg in self.controller.messages),
            "应该显示眩晕状态消息"
        )

        # 测试晕眩状态结束后可以正常行动
        self.controller.player.battle_status_duration_pass()
        self.assertFalse(self.controller.player.has_status(StatusName.STUN))
        
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
        
        # 4.3 测试减伤状态
        self.controller.clear_messages()  # 清除之前的消息
        damage_reduction_status = StatusName.DAMAGE_REDUCTION.create_instance(duration=5, target=self.controller.player)
        self.controller.player.apply_status(damage_reduction_status)
        self.assertTrue(self.controller.player.has_status(StatusName.DAMAGE_REDUCTION), "免疫效果不应该阻止减伤状态")
        self.assertFalse(
            any("免疫效果保护了你免受" in msg for msg in self.controller.messages),
            "不应该显示免疫保护消息"
        )
        
        # 4.4 测试结界状态
        self.controller.clear_messages()  # 清除之前的消息
        barrier_status = StatusName.BARRIER.create_instance(duration=3, target=self.controller.player)
        self.controller.player.apply_status(barrier_status)
        self.assertTrue(self.controller.player.has_status(StatusName.BARRIER), "免疫效果不应该阻止结界状态")
        self.assertFalse(
            any("免疫效果保护了你免受" in msg for msg in self.controller.messages),
            "不应该显示免疫保护消息"
        )
        
        # 4.5 测试恢复卷轴状态
        self.controller.clear_messages()  # 清除之前的消息
        healing_scroll_status = StatusName.HEALING_SCROLL.create_instance(duration=10, target=self.controller.player, value=5)
        self.controller.player.apply_status(healing_scroll_status)
        self.assertTrue(self.controller.player.has_status(StatusName.HEALING_SCROLL), "免疫效果不应该阻止恢复卷轴状态")
        self.assertFalse(
            any("免疫效果保护了你免受" in msg for msg in self.controller.messages),
            "不应该显示免疫保护消息"
        )
        
        # 5. 测试免疫效果叠加
        self.controller.clear_messages()  # 清除之前的消息
        immune_status2 = StatusName.IMMUNE.create_instance(duration=5, target=self.controller.player)
        self.controller.player.apply_status(immune_status2)
        self.assertTrue(self.controller.player.has_status(StatusName.IMMUNE), "免疫效果应该可以叠加")
        self.assertEqual(self.controller.player.statuses[StatusName.IMMUNE].duration, 10, "免疫效果叠加后持续时间应该增加")
        self.assertTrue(
            any("免疫效果从 5 回合提升至 10 回合!" in msg for msg in self.controller.messages),
            "应该显示免疫效果叠加的消息"
        )

class TestDoorGeneration(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.controller.scene_manager.go_to("door_scene")
        self.door_scene = self.controller.scene_manager.current_scene

    def test_door_generation(self):
        """测试门生成"""
        self.door_scene.generate_doors()
        self.assertEqual(len(self.door_scene.doors), 3)
        monster_count = 0
        for door in self.door_scene.doors:
            self.assertTrue(DoorEnum.is_valid_door_enum(door.enum))
            if door.enum == DoorEnum.MONSTER:
                monster_count += 1
        self.assertGreater(monster_count, 0)

class TestButtonTransitions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()    
        self.controller.scene_manager.scene_dict["door_scene"].generate_doors(door_enums=[DoorEnum.SHOP, DoorEnum.MONSTER, DoorEnum.TRAP])
        self.controller.scene_manager.go_to("door_scene", generate_new_doors=False)

    def test_door_scene_buttons(self):
        """测试门场景按钮跳转"""
        # 给玩家一些金币以确保可以进入商店
        self.controller.player.gold = 100
        
        # 进入门场景
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        self.controller.scene_manager.current_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
        self.controller.scene_manager.current_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

        self.setUp()
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        # 测试使用道具按钮
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)

    def test_shop_no_gold(self):
        """测试玩家没有金币时进入商店的情况"""
        # 确保玩家没有金币
        self.controller.player.gold = 0
        self.controller.scene_manager.current_scene.handle_choice(0)
        
        # 验证是否回到了门场景
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 检查消息是否包含"被踢出来"的提示
        self.assertTrue(any("被商人踢了出来" in msg for msg in self.controller.messages))

class TestButtonText(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.controller.player = self.controller.player
        self.controller.scene_manager.scene_dict["door_scene"].generate_doors(door_enums=[DoorEnum.SHOP, DoorEnum.MONSTER, DoorEnum.TRAP])
        self.controller.scene_manager.go_to("door_scene",generate_new_doors=False)
        print("test_button_text门场景初始化完成")
    def test_door_scene_button_text(self):
        """测试门场景按钮文本"""
        # 进入门场景
        door_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = door_scene.get_button_texts()
        self.assertEqual(len(buttons), 3, "门场景应该有3个按钮")
        
        # 验证每个按钮的文本格式
        for button in buttons:
            self.assertIn("门", button, "按钮文本应该包含'门'")
            # 由于门的描述是动态生成的，我们只验证基本格式
            self.assertRegex(button, r"门\d+ - .*", "按钮文本应该符合'门X - 描述'的格式")

    def test_battle_scene_button_text(self):
        """测试战斗场景按钮文本"""
        # 设置一个怪物并进入战斗场景
        self.controller.scene_manager.scene_dict["door_scene"].doors[1].monster = Monster("测试怪物", 100, 10)
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        battle_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = battle_scene.get_button_texts()
        self.assertEqual(len(buttons), 3, "战斗场景应该有3个按钮")
        
        # 验证按钮文本
        self.assertEqual(buttons[0], "攻击")
        self.assertEqual(buttons[1], "使用道具")
        self.assertEqual(buttons[2], "逃跑")

    def test_shop_scene_button_text(self):
        """测试商店场景按钮文本"""
        # 给玩家足够的金币
        self.controller.player.gold = 100
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        self.controller.scene_manager.current_scene.handle_choice(0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
        shop_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = shop_scene.get_button_texts()
        self.assertGreaterEqual(len(buttons), 3, "商店场景应该至少有3个按钮")
        
        # 验证每个商品按钮的文本格式
        for button in buttons:
            self.assertRegex(button, r".+\s+\(\d+G\)", "商品按钮文本应该包含价格信息")

    def test_use_item_scene_button_text(self):
        """测试道具使用场景按钮文本"""
        # 添加一些道具到玩家背包
        self.controller.player.add_item(
            items.FlyingHammer("飞锤", cost=25, duration=3)
        )
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)
        # 进入道具使用场景
        use_item_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = use_item_scene.get_button_texts()
        self.assertEqual(len(buttons), 3, "按钮数量应该与道具数量相同")
        
        # 验证每个道具按钮的文本
        battle_items = self.controller.player.inventory[ItemType.BATTLE]
        for i, button in enumerate(buttons):
            self.assertEqual(button, battle_items[i].name, 
                           "按钮文本应该与道具名称相同")

    def test_game_over_scene_button_text(self):
        """测试游戏结束场景按钮文本"""
        # 进入游戏结束场景
        self.controller.scene_manager.go_to("game_over_scene")
        game_over_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = game_over_scene.get_button_texts()
        self.assertEqual(len(buttons), 3, "游戏结束场景应该有三个按钮")
        
        # 验证按钮文本
        self.assertEqual(buttons[0], "重启游戏")
        self.assertEqual(buttons[1], "使用复活卷轴")
        self.assertEqual(buttons[2], "退出游戏")

class TestScrollEffectStacking(unittest.TestCase):
    """测试卷轴效果叠加"""
    
    def setUp(self):
        self.controller = GameController()
        self.controller.player = self.controller.player
        
    def test_shop_scroll_effect_stacking(self):
        """测试商店购买卷轴时的效果叠加"""
        # 给玩家添加减伤卷轴效果
        self.controller.player.apply_status(StatusName.DAMAGE_REDUCTION.create_instance(duration=5, target=self.controller.player))
        self.assertIn(StatusName.DAMAGE_REDUCTION, self.controller.player.statuses)
        
        # 给玩家足够的金币
        self.controller.player.gold = 100
        
        # 创建一个商店物品
        scroll = items.DamageReductionScroll("减伤卷轴", cost=10, duration=5)
        
        # 购买并使用卷轴
        scroll.acquire(player=self.controller.player)
        scroll.effect(target=self.controller.player)
        
        # 检查状态持续时间是否叠加
        self.assertIn(StatusName.DAMAGE_REDUCTION, self.controller.player.statuses)
        self.assertEqual(self.controller.player.get_status_duration(StatusName.DAMAGE_REDUCTION), 10)
        
    def test_monster_drop_scroll_effect_stacking(self):
        """测试怪物掉落卷轴时的效果叠加"""
        # 给玩家添加减伤卷轴效果
        self.controller.player.apply_status(StatusName.DAMAGE_REDUCTION.create_instance(duration=5, target=self.controller.player))
        self.assertIn(StatusName.DAMAGE_REDUCTION, self.controller.player.statuses)
        
        # 创建一个必定掉落减伤卷轴的怪物
        test_monster = Monster("测试怪物", 20, 5, tier=4, effect_probability=0)
        test_monster.loot = [items.DamageReductionScroll("减伤卷轴", cost=10, duration=5)]
        
        # 击杀怪物并获得掉落
        test_monster.hp = 1
        self.controller.player.attack(test_monster)
        test_monster.process_loot(self.controller.player)
        
        # 检查状态持续时间是否叠加
        self.assertIn(StatusName.DAMAGE_REDUCTION, self.controller.player.statuses)
        self.assertEqual(self.controller.player.get_status_duration(StatusName.DAMAGE_REDUCTION), 10)
        
    def test_kill_monster_with_existing_scroll(self):
        """测试玩家已有卷轴效果时杀死掉落相同卷轴的怪物"""
        # 给玩家添加减伤卷轴效果
        self.controller.player.apply_status(StatusName.DAMAGE_REDUCTION.create_instance(duration=5, target=self.controller.player))
        self.assertIn(StatusName.DAMAGE_REDUCTION, self.controller.player.statuses)
        
        # 创建一个必定掉落减伤卷轴的怪物
        test_monster = Monster("测试怪物", 20, 5, tier=4, effect_probability=0)
        test_monster.loot = [items.DamageReductionScroll("减伤卷轴", cost=10, duration=5)]
        
        # 击杀怪物并处理掉落
        test_monster.hp = 1
        self.controller.player.attack(test_monster)
        test_monster.process_loot(self.controller.player)
        
        # 检查状态持续时间是否叠加
        self.assertIn(StatusName.DAMAGE_REDUCTION, self.controller.player.statuses)
        self.assertEqual(self.controller.player.get_status_duration(StatusName.DAMAGE_REDUCTION), 10)

class TestGameStability(unittest.TestCase):
    """测试游戏稳定性"""
    
    def setUp(self):
        self.controller = GameController()
        self.controller.scene_manager.current_scene.generate_doors()  # 初始化门
        self.scene_visits = {}  # 记录每个场景的访问次数
        self.print_messages = False
        
    def test_random_button_clicks(self):
        """测试随机点击按钮1000次，确保游戏不会崩溃"""
        self.print_messages = True
        try:
            # 随机点击1000次
            for i in range(1000):
                # 清空当前消息
                self.controller.clear_messages()
                
                # 记录当前场景访问次数
                current_scene = self.controller.scene_manager.current_scene.__class__.__name__
                if current_scene not in self.scene_visits:
                    self.scene_visits[current_scene] = 0
                self.scene_visits[current_scene] += 1
                
                # 确保当前场景有按钮
                if hasattr(self.controller.scene_manager.current_scene, 'button_texts'):
                    # 获取当前场景的按钮数量
                    button_count = len(self.controller.scene_manager.current_scene.button_texts)
                    if button_count > 0:
                        # 如果是游戏结束场景，避免选择"退出游戏"按钮
                        if isinstance(self.controller.scene_manager.current_scene, GameOverScene):
                            random_choice = random.randint(0, button_count - 2)
                        else:
                            random_choice = random.randint(0, button_count - 1)
                        
                        # 执行按钮点击
                        before_scene = self.controller.scene_manager.current_scene.enum
                        before_buttons = self.controller.scene_manager.current_scene.button_texts[:]
                        button_text = self.controller.scene_manager.current_scene.button_texts[random_choice]
                        
                        # 记录点击前的状态 (HP, Gold, Atk)
                        before_hp = self.controller.player.hp
                        before_gold = self.controller.player.gold
                        before_atk = self.controller.player.atk
                        
                        self.controller.scene_manager.current_scene.handle_choice(random_choice)
                        
                        # 记录点击后的状态
                        after_hp = self.controller.player.hp
                        after_gold = self.controller.player.gold
                        after_atk = self.controller.player.atk
                        
                        # 验证状态波动 (Exception: Game Over -> DoorScene (Reset) or using Revive Scroll)
                        # 如果不是重置游戏（GameOver -> Door），则检查波动
                        is_game_reset = (before_scene == SceneType.GAME_OVER and 
                                       self.controller.scene_manager.current_scene.enum == SceneType.DOOR)
                                       
                        if not is_game_reset:
                            # 允许复活卷轴导致 HP 恢复到初始值 (e.g. 100)，所以 check delta > 200
                            hp_delta = after_hp - before_hp
                            gold_delta = after_gold - before_gold
                            atk_delta = after_atk - before_atk
                            
                            # HP 检查：
                            # 1. 增加值不应过大（考虑到后期 MaxHP 可能增长，放宽到 500）
                            # 2. 当前血量不应超过最大血量
                            self.assertLess(hp_delta, 500, 
                                f"HP increased drastically by {hp_delta} after '{button_text}'! (Before: {before_hp}, After: {after_hp})")
                                
                            self.assertLess(gold_delta, 500, 
                                f"Gold increased drastically by {gold_delta} after '{button_text}'! (Before: {before_gold}, After: {after_gold})")
                            self.assertLess(atk_delta, 100, 
                                f"Atk increased drastically by {atk_delta} after '{button_text}'! (Before: {before_atk}, After: {after_atk})")
                        
                        # 验证是否有新的日志生成
                        current_messages = self.controller.messages
                        self.assertTrue(len(current_messages) > 0, f"点击按钮 '{button_text}' 后没有生成新的日志消息")
                        # 确保日志内容不是空字符串
                        self.assertTrue(any(msg.strip() for msg in current_messages), f"点击按钮 '{button_text}' 后生成了空日志")
                        
                        # 验证状态改变（防止死循环/无反应）
                        after_scene = self.controller.scene_manager.current_scene.enum
                        after_buttons = self.controller.scene_manager.current_scene.button_texts
                        
                        # 如果在 EventScene，点击后应该跳转（除非是无效点击，但这里我们只点击有效按钮）
                        if before_scene == SceneType.EVENT:
                            self.assertNotEqual(after_scene, SceneType.EVENT, 
                                f"EventScene stuck! Choice {random_choice} kept us in EventScene. Log: {current_messages}")
                            
                        # 如果场景没变，至少按钮文本或者是回合数、状态发生变化（除了无效操作）
                        if before_scene == after_scene:
                            # 门场景自循环必须刷新门（按钮改变）
                            if before_scene == SceneType.DOOR:
                                self.assertNotEqual(before_buttons, after_buttons,
                                    "DoorScene refreshed but buttons (doors) didn't change! Did verify_doors fail?")
                            # 某些场景可能不换场景但会有反馈（如 Battle）
                            pass

                # 验证死亡逻辑
                if self.controller.player.hp <= 0:
                     self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene, 
                                         f"Player died (HP={self.controller.player.hp}) but scene is {self.controller.scene_manager.current_scene.enum}!")
                else:
                     # 如果没死，生命值应该是正数 (Allow 0 if accidentally exact? No usually died at <=0)
                     # Actually hp <= 0 is dead. So hp > 0.
                     pass
                     
                # 每100次点击打印一次进度
                if (i + 1) % 500 == 0:
                    current_scene = self.controller.scene_manager.current_scene.__class__.__name__
                    print(f"\n已完成 {i + 1} 次随机点击测试")
                    print(f"当前场景：{current_scene}")
                    # 打印场景访问统计
                    print("\n场景访问统计：")
                    for scene, count in sorted(self.scene_visits.items(), key=lambda x: x[1], reverse=True):
                        print(f"{scene}: {count}次")
        except Exception as e:
            current_scene = self.controller.scene_manager.current_scene.__class__.__name__
            print(f"错误发生时的场景：{current_scene}")
            print(f"错误发生时的按钮：{self.controller.scene_manager.current_scene.button_texts}")
            raise e
        
        # 验证游戏状态
        self.assertIsNotNone(self.controller.player, "玩家对象不应该为None")
        self.assertIsNotNone(self.controller.scene_manager.current_scene, "当前场景不应该为None")
        
        # 打印场景访问统计
        print("\n场景访问统计：")
        for scene, count in sorted(self.scene_visits.items(), key=lambda x: x[1], reverse=True):
            print(f"{scene}: {count}次")
        
        print("\n测试完成：1000次随机点击测试成功完成")

class TestMonsterLoot(unittest.TestCase):
    """测试怪物掉落系统"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.controller = GameController()
        self.controller.player = self.controller.player
        self.monster = Monster("测试怪物", 20, 5)
        
    def test_loot_generation(self):
        """测试掉落物品生成"""
        # 测试掉落物品的类型
        loot = self.monster.generate_loot()
        if loot:
            self.assertIn(loot.item_type, [ItemType.CONSUMABLE, ItemType.BATTLE, ItemType.PASSIVE])
            
    def test_loot_application(self):
        """测试掉落物品的应用"""
        # 创建测试物品
        healing_potion = items.HealingPotion("小治疗药水", heal_amount=5, cost=5)
        self.monster.loot = [healing_potion]
        
        # 先扣血，确保能加血
        self.controller.player.hp = 1
        
        self.monster.process_loot(self.controller.player)
        self.assertGreater(self.controller.player.hp, 1)
        
        # 测试战斗物品添加到背包
        flying_hammer = items.FlyingHammer("飞锤", cost=25, duration=3)
        self.monster.loot = [flying_hammer]
        self.monster.process_loot(self.controller.player)
        self.assertIn(flying_hammer, self.controller.player.get_items_by_type(ItemType.BATTLE))
        
        # 测试被动物品添加到背包
        revive_scroll = items.ReviveScroll("复活卷轴", cost=3, duration=3)
        self.monster.loot = [revive_scroll]
        self.monster.process_loot(self.controller.player)
        self.assertIn(revive_scroll, self.controller.player.get_items_by_type(ItemType.PASSIVE))

class TestGame(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.controller.player = self.controller.player
        self.scene_manager = self.controller.scene_manager

    def test_initial_scene(self):
        """测试游戏启动时是否正确进入门场景"""
        # 检查当前场景是否为 DoorScene
        self.assertIsInstance(self.scene_manager.current_scene, DoorScene)
        
        # 检查门场景是否已初始化
        self.assertTrue(self.scene_manager.current_scene.has_initialized)
        self.assertEqual(len(self.scene_manager.current_scene.doors), 3)
        
        # 检查按钮文本是否正确
        button_texts = self.scene_manager.current_scene.get_button_texts()
        self.assertEqual(len(button_texts), 3)
        self.assertTrue(all(text.startswith("门") for text in button_texts))

class TestFlyingHammer(unittest.TestCase):
    """测试飞锤效果"""
    
    def setUp(self):
        self.controller = GameController()
        self.controller.player = self.controller.player
        self.monster = Monster("测试怪物", 20, 5)
        self.controller.current_monster = self.monster
        
    def test_flying_hammer_effect(self):
        """测试飞锤效果：怪物被晕眩后无法反击"""
        # 给玩家添加飞锤
        flying_hammer = items.FlyingHammer("飞锤", cost=0, duration=3)
        self.controller.player.add_item(flying_hammer)
        
        # 进入战斗场景
        self.controller.scene_manager.go_to("battle_scene")
        
        # 使用飞锤
        self.controller.scene_manager.current_scene.handle_choice(1)  # 使用道具
        self.controller.scene_manager.current_scene.handle_choice(0)  # 选择飞锤
        
        # 验证怪物是否被晕眩
        self.assertTrue(self.monster.has_status(StatusName.STUN))
        self.assertEqual(self.monster.get_status_duration(StatusName.STUN), 3)
        
        # 记录玩家当前生命值
        initial_hp = self.controller.player.hp
        
        # 尝试让怪物攻击
        self.monster.attack(self.controller.player)
        
        # 验证玩家生命值没有变化
        self.assertEqual(self.controller.player.hp, initial_hp)

class TestSceneSystem(unittest.TestCase):
    """测试场景系统"""
    
    def setUp(self):
        self.controller = GameController()
        
    def test_scene_transitions(self):
        """测试场景切换"""
        # 进入门场景
        self.controller.scene_manager.go_to("door_scene")
        door_scene = self.controller.scene_manager.current_scene
        
        # 测试怪物门切换
        door_scene.generate_doors(door_enums=[DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP])
        door_scene.handle_choice(0)  # 选择怪物门
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        self.assertIsNotNone(self.controller.current_monster)
        
        # 返回门场景
        self.controller.scene_manager.go_to("door_scene")
        door_scene = self.controller.scene_manager.current_scene
        
        # 测试商店门切换
        self.controller.player.gold = 100  # 确保有足够金币进入商店
        door_scene.generate_doors(door_enums=[DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP])
        door_scene.handle_choice(1)  # 选择商店门
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
        
        # 返回门场景
        self.controller.scene_manager.go_to("door_scene")
        door_scene = self.controller.scene_manager.current_scene
        
        # 测试陷阱门切换
        door_scene.generate_doors(door_enums=[DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP])
        door_scene.handle_choice(2)  # 选择陷阱门
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 测试战斗场景中的道具使用切换
        self.controller.scene_manager.go_to("battle_scene")
        battle_scene = self.controller.scene_manager.current_scene
        battle_scene.handle_choice(1)  # 选择使用道具
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)
        
        # 测试通过陷阱门进入游戏结束场景
        self.controller.scene_manager.go_to("door_scene")

        door_scene = self.controller.scene_manager.current_scene
        self.controller.player.clear_inventory()
        self.controller.player.hp = 1  # 设置玩家生命值很低
        door_scene.generate_doors(door_enums=[DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP])
        door_scene.handle_choice(2)  # 选择陷阱门
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)

    def test_door_battle_game_over_transition(self):
        """测试从门场景到战斗场景再到游戏结束场景的转换"""
        door_scene = self.controller.scene_manager.current_scene
        self.controller.player.hp = 1  # 设置玩家生命值很低
        self.controller.player.atk = 0 # 设置玩家攻击力很低
        
        door_scene.generate_doors([DoorEnum.MONSTER, DoorEnum.SHOP, DoorEnum.TRAP])
        door_scene.doors[0].monster = Monster("测试怪物", 100, 10)
        self.controller.scene_manager.go_to("door_scene", generate_new_doors=False)
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

        #清空玩家的物品栏
        self.controller.player.clear_inventory()
        self.controller.clear_messages()
        
        door_scene.handle_choice(0)  # 选择怪物门
        battle_scene = self.controller.scene_manager.current_scene
        
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        self.controller.clear_messages()
        self.assertEqual(self.controller.player.hp, 1)
        battle_scene.handle_choice(0)  # 选择攻击
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)



class TestTrapDoors(unittest.TestCase):
    """测试陷阱门"""
    
    def setUp(self):
        self.controller = GameController()
        self.controller.player = self.controller.player
        # Create a TrapDoor directly
        from models.door import TrapDoor
        self.trap_door = TrapDoor(controller=self.controller, damage=10)
        
    def test_spike_trap(self):
        """测试尖刺陷阱"""
        with unittest.mock.patch('random.choice', return_value='spike'):
            initial_hp = self.controller.player.hp
            self.trap_door.enter()
            
            # 验证伤害
            self.assertEqual(self.controller.player.hp, initial_hp - 10)
            # 验证消息
            self.assertTrue(any("尖刺" in msg for msg in self.controller.messages))
            self.assertTrue(any("触发了机关" in msg for msg in self.controller.messages))
            
    def test_poison_trap(self):
        """测试毒气陷阱"""
        with unittest.mock.patch('random.choice', return_value='poison'):
            self.trap_door.enter()
            
            # 验证中毒状态
            self.assertTrue(self.controller.player.has_status(StatusName.POISON))
            # 验证消息
            self.assertTrue(any("毒气" in msg for msg in self.controller.messages))
            
    def test_gold_trap(self):
        """测试窃贼陷阱"""
        self.controller.player.gold = 100
        with unittest.mock.patch('random.choice', return_value='gold'):
            with unittest.mock.patch('random.randint', return_value=20):
                self.trap_door.enter()
                
                # 验证金币损失
                self.assertEqual(self.controller.player.gold, 80)
                # 验证消息
                self.assertTrue(any("地精" in msg for msg in self.controller.messages))
                
    def test_weakness_trap(self):
        """测试虚弱陷阱"""
        with unittest.mock.patch('random.choice', return_value='weakness'):
            self.trap_door.enter()
            
            # 验证虚弱状态
            self.assertTrue(self.controller.player.has_status(StatusName.WEAK))
            # 验证消息
            self.assertTrue(any("虚弱" in msg for msg in self.controller.messages))

if __name__ == '__main__':
    unittest.main()