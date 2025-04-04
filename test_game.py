import unittest
from server import GameController, Player, DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene, GameConfig
from models.monster import get_random_monster, Monster
import random

class TestGameInitialization(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.config = GameConfig()

    def test_game_initialization(self):
        """测试游戏初始化"""
        self.assertIsNotNone(self.controller.player)
        self.assertEqual(self.controller.player.hp, self.config.START_PLAYER_HP)
        self.assertEqual(self.controller.player.atk, self.config.START_PLAYER_ATK)
        self.assertEqual(self.controller.player.gold, self.config.START_PLAYER_GOLD)
        self.assertEqual(self.controller.round_count, 0)
        self.assertIsNotNone(self.controller.scene_manager)
        self.assertIsNotNone(self.controller.door_scene)
        self.assertIsNotNone(self.controller.battle_scene)
        self.assertIsNotNone(self.controller.shop_scene)
        self.assertIsNotNone(self.controller.use_item_scene)
        self.assertIsNotNone(self.controller.game_over_scene)

    def test_initial_inventory(self):
        """测试初始道具栏"""
        self.assertEqual(len(self.controller.player.inventory), 4)
        inventory_types = [item["type"] for item in self.controller.player.inventory]
        self.assertIn("revive", inventory_types)
        self.assertIn("飞锤", inventory_types)
        self.assertIn("巨大卷轴", inventory_types)
        self.assertIn("结界", inventory_types)

class TestSceneTransitions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()

    def test_scene_transitions(self):
        """测试场景切换"""
        # 测试从门场景切换到战斗场景
        self.controller.go_to_scene("battle_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)

        # 测试从战斗场景切换到商店场景
        self.controller.go_to_scene("shop_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)

        # 测试从商店场景切换到道具使用场景
        self.controller.go_to_scene("use_item_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)

        # 测试从道具使用场景切换到游戏结束场景
        self.controller.go_to_scene("game_over_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)

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
        self.player.statuses["poison"] = {"duration": 3}
        self.assertEqual(self.player.statuses["poison"]["duration"], 3)
        
        # 测试状态效果描述
        status_desc = self.player.get_status_desc()
        self.assertIn("中毒", status_desc)

    def test_poison_damage(self):
        """测试中毒效果造成的伤害"""
        # 设置玩家生命值为100
        self.player.hp = 100
        # 添加中毒状态
        self.player.statuses["poison"] = {"duration": 3}
        
        # 应用回合效果
        self.player._apply_base_effects()
        
        # 验证生命值减少了10%（10点）
        self.assertEqual(self.player.hp, 90)
        
        # 验证消息是否被添加到控制器
        self.assertIn("中毒效果造成 10 点伤害！", self.controller.messages)

    def test_stun_effect(self):
        """测试晕眩效果"""
        # 添加晕眩状态
        self.player.statuses["stun"] = {"duration": 2}
        
        # 创建一个测试怪物
        test_monster = Monster("测试怪物", 20, 5)
        
        # 测试玩家在晕眩状态下无法攻击
        monster_dead = self.player.attack(test_monster)
        self.assertFalse(monster_dead)  # 晕眩状态下攻击应该失败
        
        # 测试玩家在晕眩状态下无法使用道具
        self.player.inventory.append({"name": "测试道具", "type": "heal", "value": 10, "active": True})
        self.assertTrue(self.player.is_stunned())
        
        # 测试晕眩状态持续时间减少
        self.player._update_status_durations(is_battle_turn=True)
        self.assertEqual(self.player.statuses["stun"]["duration"], 1)
        
        # 测试晕眩状态结束后可以正常行动
        self.player._update_status_durations(is_battle_turn=True)
        self.assertFalse(self.player.is_stunned())

    def test_immunity_effect(self):
        """测试免疫效果对怪物攻击的影响"""
        # 创建一个高等级怪物
        test_monster = Monster("测试怪物", 20, 5, tier=4)  # 使用tier 4的怪物来确保高概率触发负面效果
        
        # 给玩家添加免疫效果
        self.player.statuses["immune"] = {"duration": 5}
        
        # 进行多次攻击测试
        immunity_protected = False
        for _ in range(10):  # 测试10次以确保高概率触发
            test_monster.attack(self.player)
            # 检查是否收到免疫保护消息
            if any("免疫效果保护了你免受" in msg for msg in self.controller.messages):
                immunity_protected = True
                break
        
        # 验证免疫效果是否生效
        self.assertTrue(immunity_protected, "免疫效果应该保护玩家免受怪物的负面效果")
        
        # 验证玩家没有获得任何负面效果
        self.assertNotIn("weak", self.player.statuses)
        self.assertNotIn("poison", self.player.statuses)
        self.assertNotIn("stun", self.player.statuses)
        
        # 清除免疫效果并再次测试
        del self.player.statuses["immune"]
        self.controller.clear_messages()
        
        # 再次进行多次攻击测试
        negative_effect_applied = False
        for _ in range(10):  # 测试10次以确保高概率触发
            test_monster.attack(self.player)
            # 检查是否获得负面效果
            if any(effect in self.player.statuses for effect in ["weak", "poison", "stun"]):
                negative_effect_applied = True
                break
        
        # 验证在没有免疫效果时，负面效果可以正常应用
        self.assertTrue(negative_effect_applied, "在没有免疫效果时，怪物应该能够施加负面效果")

    def test_monster_loot(self):
        """测试怪物死亡后的掉落效果"""
        # 创建一个Tier 2的怪物
        monster = Monster("测试怪物", 10, 5, tier=2)
        initial_gold = self.player.gold
        initial_atk = self.player.atk
        
        # 攻击怪物直到死亡
        while monster.hp > 0:
            self.player.attack(monster)
        
        # 处理掉落
        monster.process_loot(self.player)
        
        # 验证金币增加
        self.assertGreater(self.player.gold, initial_gold, "怪物死亡后应该获得金币")
        
        # 验证攻击力可能增加（因为可能有装备掉落）
        self.assertGreaterEqual(self.player.atk, initial_atk, "怪物死亡后攻击力不应该降低")
        
        # 验证掉落物品数量
        self.assertGreaterEqual(len(monster.loot), 1, "怪物至少应该掉落金币")
        self.assertLessEqual(len(monster.loot), 3, "怪物最多掉落三种物品（金币、装备、卷轴）")
        
        # 验证掉落物品类型
        has_gold = False
        has_equip = False
        has_scroll = False
        
        for item_type, value in monster.loot:
            if item_type == "gold":
                has_gold = True
                self.assertGreaterEqual(value, 10, "Tier 2怪物的金币掉落应该至少为10")
                self.assertLessEqual(value, 30, "Tier 2怪物的金币掉落应该最多为30")
            elif item_type == "equip":
                has_equip = True
                self.assertEqual(value, 4, "Tier 2怪物的装备加成应该为4")
            elif item_type == "scroll":
                has_scroll = True
                scroll_name, scroll_desc, scroll_value = value
                self.assertIn(scroll_name, ["healing_scroll", "damage_reduction", "atk_up"])
                if scroll_name == "healing_scroll":
                    self.assertEqual(scroll_value, 10, "Tier 2怪物的恢复卷轴效果应该为10")
                elif scroll_name == "damage_reduction":
                    self.assertEqual(scroll_value, 20, "Tier 2怪物的减伤卷轴效果应该为20")
                elif scroll_name == "atk_up":
                    # 检查攻击力增益是否在正确的范围内
                    self.assertGreaterEqual(scroll_value, 7, "Tier 2怪物的攻击力增益卷轴效果应该至少为7")
                    self.assertLessEqual(scroll_value, 16, "Tier 2怪物的攻击力增益卷轴效果应该最多为16")
        
        self.assertTrue(has_gold, "怪物应该掉落金币")

class TestDoorGeneration(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.door_scene = self.controller.door_scene

    def test_door_generation(self):
        """测试门生成"""
        self.door_scene._generate_doors()
        self.assertEqual(len(self.door_scene.doors), 3)
        
        # 检查是否至少有一扇怪物门
        monster_doors = [door for door in self.door_scene.doors if door.event == "monster"]
        self.assertGreater(len(monster_doors), 0)

class TestGameReset(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.config = GameConfig()

    def test_game_reset(self):
        """测试游戏重置"""
        # 修改一些游戏状态
        self.controller.player.hp = 10
        self.controller.player.gold = 100
        self.controller.round_count = 5
        
        # 重置游戏
        self.controller.reset_game()
        
        # 验证重置后的状态
        self.assertEqual(self.controller.player.hp, self.config.START_PLAYER_HP)
        self.assertEqual(self.controller.player.gold, self.config.START_PLAYER_GOLD)
        self.assertEqual(self.controller.round_count, 0)
        self.assertEqual(len(self.controller.player.inventory), 4)

class TestButtonTransitions(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()

    def test_door_scene_buttons(self):
        """测试门场景按钮跳转"""
        # 确保当前在门场景
        self.controller.go_to_scene("door_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 测试每个门的点击
        for i in range(3):
            # 记录当前门的类型
            door = self.controller.scene_manager.current_scene.doors[i]
            self.controller.scene_manager.current_scene.handle_choice(i)
            
            # 根据门的类型验证场景跳转
            if door.event == "monster":
                self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
                # 回到门场景继续测试
                self.controller.go_to_scene("door_scene")
            elif door.event == "shop":
                self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
                # 回到门场景继续测试
                self.controller.go_to_scene("door_scene")
            elif door.event in ["trap", "reward"]:
                self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)

    def test_battle_scene_buttons(self):
        """测试战斗场景按钮跳转"""
        # 设置一个怪物并进入战斗场景
        self.controller.current_monster = get_random_monster()
        self.controller.go_to_scene("battle_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        
        # 测试攻击按钮
        self.controller.scene_manager.current_scene.handle_choice(0)
        # 如果怪物死亡，应该回到门场景
        if self.controller.current_monster and self.controller.current_monster.hp <= 0:
            self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 测试使用道具按钮
        self.controller.go_to_scene("battle_scene")
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)
        
        # 测试逃跑按钮 - 成功情况
        self.controller.go_to_scene("battle_scene")
        initial_hp = self.controller.player.hp
        self.controller.scene_manager.current_scene.handle_choice(2)
        # 如果逃跑成功，应该回到门场景
        if self.controller.scene_manager.current_scene.__class__.__name__ == "DoorScene":
            self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
            # 逃跑成功不应该受到伤害
            self.assertEqual(self.controller.player.hp, initial_hp)
        
        # 测试逃跑按钮 - 失败情况
        self.controller.go_to_scene("battle_scene")
        initial_hp = self.controller.player.hp
        # 设置玩家状态为虚弱，降低逃跑成功率
        self.controller.player.statuses["weak"] = {"duration": 3}
        self.controller.scene_manager.current_scene.handle_choice(2)
        # 如果逃跑失败，应该受到伤害
        if self.controller.scene_manager.current_scene.__class__.__name__ == "BattleScene":
            self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
            self.assertLess(self.controller.player.hp, initial_hp)

    def test_shop_scene_buttons(self):
        """测试商店场景按钮跳转"""
        # 给玩家一些金币并进入商店场景
        self.controller.player.gold = 100
        self.controller.go_to_scene("shop_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, ShopScene)
        
        # 测试购买按钮
        for i in range(3):
            self.controller.scene_manager.current_scene.handle_choice(i)
            # 购买后应该回到门场景
            self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
            # 回到商店场景继续测试
            self.controller.go_to_scene("shop_scene")

    def test_use_item_scene_buttons(self):
        """测试道具使用场景按钮跳转"""
        # 确保玩家有可用的道具
        self.controller.player.inventory = [
            {"name": "飞锤", "type": "飞锤", "value": 0, "cost": 0, "active": True},
            {"name": "结界", "type": "结界", "value": 0, "cost": 0, "active": True},
            {"name": "巨大卷轴", "type": "巨大卷轴", "value": 0, "cost": 0, "active": True}
        ]
        
        # 设置一个怪物并进入战斗场景
        self.controller.current_monster = get_random_monster()
        self.controller.go_to_scene("battle_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)
        
        # 进入道具使用场景
        self.controller.scene_manager.current_scene.handle_choice(1)
        self.assertIsInstance(self.controller.scene_manager.current_scene, UseItemScene)
        
        # 测试使用道具按钮
        initial_inventory_size = len(self.controller.player.inventory)
        self.controller.scene_manager.current_scene.handle_choice(0)  # 使用第一个道具
        
        # 验证道具使用后的状态
        self.assertEqual(len(self.controller.player.inventory), initial_inventory_size - 1)  # 道具应该被消耗
        self.assertIsInstance(self.controller.scene_manager.current_scene, BattleScene)  # 应该回到战斗场景

    def test_game_over_scene_buttons(self):
        """测试游戏结束场景按钮跳转"""
        # 进入游戏结束场景
        self.controller.go_to_scene("game_over_scene")
        self.assertIsInstance(self.controller.scene_manager.current_scene, GameOverScene)
        
        # 测试重启游戏按钮
        self.controller.scene_manager.current_scene.handle_choice(0)
        self.assertEqual(self.controller.player.hp, self.controller.game_config.START_PLAYER_HP)
        self.assertEqual(self.controller.player.gold, self.controller.game_config.START_PLAYER_GOLD)
        
        # 测试使用复活卷轴按钮
        self.controller.go_to_scene("game_over_scene")
        self.controller.scene_manager.current_scene.handle_choice(1)
        # 如果有复活卷轴，应该回到上一个场景
        if "revive" in [item["type"] for item in self.controller.player.inventory]:
            self.assertIsNotNone(self.controller.last_scene)

    def test_shop_no_gold(self):
        """测试玩家没有金币时进入商店的情况"""
        # 确保玩家没有金币
        self.controller.player.gold = 0
        
        # 进入商店场景
        self.controller.go_to_scene("shop_scene")
        
        # 验证是否回到了门场景
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
        # 检查消息是否包含"被踢出来"的提示
        self.assertTrue(any("被商人踢了出来" in msg for msg in self.controller.messages))

class TestButtonText(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.player = self.controller.player

    def test_door_scene_button_text(self):
        """测试门场景按钮文本"""
        # 进入门场景
        self.controller.go_to_scene("door_scene")
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
        self.controller.current_monster = get_random_monster()
        self.controller.go_to_scene("battle_scene")
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
        self.controller.go_to_scene("shop_scene")
        shop_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = shop_scene.get_button_texts()
        self.assertGreaterEqual(len(buttons), 3, "商店场景应该至少有3个按钮")
        
        # 验证每个商品按钮的文本格式
        for button in buttons:
            self.assertRegex(button, r".+\s+\(\d+G\)", "商品按钮文本应该包含价格信息")

    def test_use_item_scene_button_text(self):
        """测试道具使用场景按钮文本"""
        # 确保玩家有道具
        self.controller.player.inventory = [
            {"name": "飞锤", "type": "飞锤", "value": 0, "cost": 0, "active": True},
            {"name": "结界", "type": "结界", "value": 0, "cost": 0, "active": True},
            {"name": "巨大卷轴", "type": "巨大卷轴", "value": 0, "cost": 0, "active": True}
        ]
        
        # 进入道具使用场景
        self.controller.go_to_scene("use_item_scene")
        use_item_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = use_item_scene.get_button_texts()
        self.assertEqual(len(buttons), 3, "按钮数量应该与道具数量相同")
        
        # 验证每个道具按钮的文本
        for i, button in enumerate(buttons):
            self.assertEqual(button, self.controller.player.inventory[i]["name"], 
                           "按钮文本应该与道具名称相同")

    def test_game_over_scene_button_text(self):
        """测试游戏结束场景按钮文本"""
        # 进入游戏结束场景
        self.controller.go_to_scene("game_over_scene")
        game_over_scene = self.controller.scene_manager.current_scene
        
        # 验证初始按钮文本
        buttons = game_over_scene.get_button_texts()
        self.assertEqual(len(buttons), 3, "游戏结束场景应该有三个按钮")
        
        # 验证按钮文本
        self.assertEqual(buttons[0], "重启游戏")
        self.assertEqual(buttons[1], "使用复活卷轴")
        self.assertEqual(buttons[2], "退出游戏")

    def test_door_scene_button_text_update(self):
        """测试门场景点击按钮后按钮文本更新"""
        # 进入门场景
        self.controller.go_to_scene("door_scene")
        door_scene = self.controller.scene_manager.current_scene
        
        # 记录初始按钮文本
        initial_buttons = door_scene.get_button_texts()
        
        # 找到一个非怪物门的索引
        non_monster_door_index = None
        for i, door in enumerate(door_scene.doors):
            if door.event != "monster":
                non_monster_door_index = i
                break
        
        # 确保找到了非怪物门
        self.assertIsNotNone(non_monster_door_index, "应该至少有一个非怪物门")
        
        # 点击非怪物门
        door_scene.handle_choice(non_monster_door_index)
        
        # 获取更新后的按钮文本
        updated_buttons = door_scene.get_button_texts()
        
        # 验证新按钮文本的格式
        for button in updated_buttons:
            self.assertIn("门", button, "按钮文本应该包含'门'")
            self.assertRegex(button, r"门\d+ - .*", "按钮文本应该符合'门X - 描述'的格式")
            
        # 验证三个按钮的文本都不同
        self.assertEqual(len(set(updated_buttons)), 3, "三个按钮的文本应该各不相同")
        
        # 验证按钮文本已更新
        for i in range(3):
            self.assertRegex(updated_buttons[i], r"门\d+ - .*", "更新后的按钮文本应该符合'门X - 描述'的格式")

class TestScrollEffectStacking(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.player = self.controller.player

    def test_shop_scroll_effect_stacking(self):
        """测试商店购买卷轴时的效果叠加"""
        # 给玩家足够的金币
        self.player.gold = 100
        
        # 第一次购买减伤卷轴
        self.player.apply_item_effect("damage_reduction", 10)
        initial_duration = self.player.statuses["damage_reduction"]["duration"]
        
        # 第二次购买减伤卷轴
        self.player.apply_item_effect("damage_reduction", 10)
        new_duration = self.player.statuses["damage_reduction"]["duration"]
        
        # 验证持续时间是否叠加
        self.assertGreater(new_duration, initial_duration, "购买相同卷轴时持续时间应该叠加")
        
        # 测试攻击力增益卷轴
        self.player.apply_item_effect("atk_up", 10)
        initial_atk_duration = self.player.statuses["atk_up"]["duration"]
        initial_atk_value = self.player.statuses["atk_up"]["value"]
        
        # 再次购买攻击力增益卷轴
        self.player.apply_item_effect("atk_up", 15)  # 使用更大的值
        new_atk_duration = self.player.statuses["atk_up"]["duration"]
        new_atk_value = self.player.statuses["atk_up"]["value"]
        
        # 验证攻击力增益卷轴的叠加
        self.assertGreater(new_atk_duration, initial_atk_duration, "攻击力增益卷轴持续时间应该叠加")
        self.assertEqual(new_atk_value, 15, "攻击力增益卷轴应该取较大的值")

    def test_monster_drop_scroll_effect_stacking(self):
        """测试怪物掉落卷轴时的效果叠加"""
        # 创建一个Tier 2的怪物
        monster = Monster("测试怪物", 10, 5, tier=2)
        
        # 先给玩家一个减伤卷轴效果
        self.player.apply_item_effect("damage_reduction", 10)
        initial_duration = self.player.statuses["damage_reduction"]["duration"]
        
        # 修改怪物的掉落，确保掉落减伤卷轴
        monster.loot = [
            ("gold", 10),
            ("scroll", ("damage_reduction", "减伤卷轴", 10))
        ]
        
        # 处理怪物掉落
        monster.process_loot(self.player)
        new_duration = self.player.statuses["damage_reduction"]["duration"]
        
        # 验证持续时间是否叠加
        self.assertGreater(new_duration, initial_duration, "怪物掉落相同卷轴时持续时间应该叠加")
        
        # 测试攻击力增益卷轴
        self.player.apply_item_effect("atk_up", 10)
        initial_atk_duration = self.player.statuses["atk_up"]["duration"]
        initial_atk_value = self.player.statuses["atk_up"]["value"]
        
        # 修改怪物的掉落，确保掉落攻击力增益卷轴
        monster.loot = [
            ("gold", 10),
            ("scroll", ("atk_up", "攻击力增益卷轴", 15))
        ]
        
        # 处理怪物掉落
        monster.process_loot(self.player)
        new_atk_duration = self.player.statuses["atk_up"]["duration"]
        new_atk_value = self.player.statuses["atk_up"]["value"]
        
        # 验证攻击力增益卷轴的叠加
        self.assertGreater(new_atk_duration, initial_atk_duration, "怪物掉落的攻击力增益卷轴持续时间应该叠加")
        self.assertEqual(new_atk_value, 15, "怪物掉落的攻击力增益卷轴应该取较大的值")

    def test_kill_monster_with_existing_scroll(self):
        """测试玩家已有卷轴效果时杀死掉落相同卷轴的怪物"""
        # 创建一个Tier 2的怪物
        monster = Monster("测试怪物", 10, 5, tier=2)
        
        # 先给玩家一个减伤卷轴效果
        self.player.apply_item_effect("damage_reduction", 10)
        initial_duration = self.player.statuses["damage_reduction"]["duration"]
        
        # 修改怪物的掉落，确保掉落减伤卷轴
        monster.loot = [
            ("gold", 10),
            ("scroll", ("damage_reduction", "减伤卷轴", 10))
        ]
        
        # 攻击怪物直到死亡
        while monster.hp > 0:
            self.player.attack(monster)
        
        # 处理怪物掉落
        monster.process_loot(self.player)
        new_duration = self.player.statuses["damage_reduction"]["duration"]
        
        # 验证持续时间是否叠加
        self.assertGreater(new_duration, initial_duration, "杀死掉落相同卷轴的怪物时，卷轴持续时间应该叠加")
        
        # 测试攻击力增益卷轴
        self.player.apply_item_effect("atk_up", 10)
        initial_atk_duration = self.player.statuses["atk_up"]["duration"]
        initial_atk_value = self.player.statuses["atk_up"]["value"]
        
        # 创建新的怪物并修改掉落
        monster = Monster("测试怪物2", 10, 5, tier=2)
        monster.loot = [
            ("gold", 10),
            ("scroll", ("atk_up", "攻击力增益卷轴", 15))
        ]
        
        # 攻击怪物直到死亡
        while monster.hp > 0:
            self.player.attack(monster)
        
        # 处理怪物掉落
        monster.process_loot(self.player)
        new_atk_duration = self.player.statuses["atk_up"]["duration"]
        new_atk_value = self.player.statuses["atk_up"]["value"]
        
        # 验证攻击力增益卷轴的叠加
        self.assertGreater(new_atk_duration, initial_atk_duration, "杀死掉落攻击力增益卷轴的怪物时，持续时间应该叠加")
        self.assertEqual(new_atk_value, 15, "杀死掉落攻击力增益卷轴的怪物时，应该取较大的攻击力值")

class TestGameStability(unittest.TestCase):
    def setUp(self):
        self.controller = GameController()
        self.config = GameConfig()
        # Initialize tracking variables as instance variables
        self.scene_visits = {}  # 动态记录场景访问
        self.total_transitions = 0
        self.restart_count = 0
        
        # 保存原始的go_to_scene方法
        self.original_go_to_scene = self.controller.go_to_scene
        
        def go_to_scene_with_tracking(scene_name):
            # 获取当前场景名称
            before_scene = self.controller.scene_manager.current_scene.__class__.__name__
            
            # 调用原始方法
            self.original_go_to_scene(scene_name)
            
            # 获取新场景名称
            after_scene = self.controller.scene_manager.current_scene.__class__.__name__
            
            # 如果场景改变，更新统计
            if before_scene != after_scene:
                # 动态记录场景访问
                if after_scene not in self.scene_visits:
                    self.scene_visits[after_scene] = 0
                self.scene_visits[after_scene] += 1
                self.total_transitions += 1
                print(f"场景跳转: {before_scene} -> {after_scene}")
        
        # 替换go_to_scene方法
        self.controller.go_to_scene = go_to_scene_with_tracking

    def tearDown(self):
        # 恢复原始的go_to_scene方法
        self.controller.go_to_scene = self.original_go_to_scene

    def test_random_button_clicks(self):
        """测试随机点击按钮1000次，确保游戏不会崩溃"""
        # 重置游戏状态
        self.controller.reset_game()
        
        # 记录初始状态
        initial_hp = self.controller.player.hp
        initial_gold = self.controller.player.gold
        
        # 记录初始场景
        current_scene = self.controller.scene_manager.current_scene.__class__.__name__
        self.scene_visits[current_scene] = 1
        
        try:
            # 随机点击1000次
            for i in range(1000):
                # 清空当前消息
                self.controller.clear_messages()
                
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
                        button_text = self.controller.scene_manager.current_scene.button_texts[random_choice]
                        print(f"点击按钮: {button_text}")
                        self.controller.scene_manager.current_scene.handle_choice(random_choice)
                        
                        # 验证是否有新的日志生成
                        current_messages = self.controller.messages
                        self.assertTrue(len(current_messages) > 0, f"点击按钮 '{button_text}' 后没有生成新的日志消息")
                        for msg in current_messages:
                            print(msg)
                
                # 如果在游戏结束场景，通过点击按钮重置游戏
                if isinstance(self.controller.scene_manager.current_scene, GameOverScene):
                    # 确保有按钮可以点击
                    if hasattr(self.controller.scene_manager.current_scene, 'button_texts'):
                        # 点击"重新开始"按钮（通常是第一个按钮）
                        self.controller.scene_manager.current_scene.handle_choice(0)
                        self.restart_count += 1
                else:
                    # 只有在非游戏结束场景才检查玩家状态
                    self.assertGreaterEqual(self.controller.player.hp, 0, "玩家生命值不应该小于0")
                    self.assertGreaterEqual(self.controller.player.gold, 0, "玩家金币不应该小于0")
                
                # 每100次点击打印一次进度和场景统计
                if (i + 1) % 100 == 0:
                    current_scene = self.controller.scene_manager.current_scene.__class__.__name__
                    print(f"\n已完成 {i + 1} 次随机点击测试")
                    print(f"当前场景：{current_scene}")
                    print(f"场景跳转次数：{self.total_transitions}")
                    print("当前场景访问统计：")
                    for scene_type, count in self.scene_visits.items():
                        print(f"- {scene_type}: {count}次")
                    print(f"重开次数：{self.restart_count}\n")
                
        except Exception as e:
            current_scene = self.controller.scene_manager.current_scene.__class__.__name__
            print(f"错误发生时的场景：{current_scene}")
            print(f"错误发生时的按钮：{self.controller.scene_manager.current_scene.button_texts}")
            raise e
        
        # 验证游戏状态
        self.assertIsNotNone(self.controller.player, "玩家对象不应该为None")
        self.assertIsNotNone(self.controller.scene_manager.current_scene, "当前场景不应该为None")
        self.assertGreaterEqual(self.controller.player.hp, 0, "最终玩家生命值不应该小于0")
        self.assertGreaterEqual(self.controller.player.gold, 0, "最终玩家金币不应该小于0")
        
        # 打印最终统计信息
        print(f"\n测试完成：在1000次随机点击中的最终统计")
        print(f"总场景跳转次数：{self.total_transitions}")
        print("各场景访问次数：")
        for scene_type, count in self.scene_visits.items():
            print(f"- {scene_type}: {count}次")
        print(f"玩家重开次数：{self.restart_count}次")

if __name__ == '__main__':
    unittest.main() 