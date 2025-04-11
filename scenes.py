from models.door import Door
from models.monster import Monster, get_random_monster
from models.status import Status, StatusName
import random
import os
from models.items import ItemType
from models.game_config import GameConfig
from enum import Enum, auto

class Scene:
    """场景基类"""
    def __init__(self, controller):
        self.controller = controller
        self.button_texts = ["", "", ""]  # 默认三个空按钮
        self.enum = None

    def on_enter(self):
        """进入场景时的处理"""
        pass

    def handle_choice(self, index):
        """处理按钮选择"""
        pass

    def get_button_texts(self):
        """获取按钮文本"""
        return self.button_texts

class DoorScene(Scene):
    """选择门的场景"""
    def __init__(self, controller):
        super().__init__(controller)
        self.doors = []
        self.has_initialized = False
        self.button_texts = ["门1", "门2", "门3"]
        self.enum = SceneType.DOOR

    def on_enter(self):
        if not self.has_initialized:
            self.generate_doors()
            self.has_initialized = True

    def handle_choice(self, index):
        c = self.controller
        p = c.player
        if index < 0 or index >= len(self.doors):
            c.add_message("无效的门选择")
            return
            
        c.round_count += 1
        c.add_message(f"第{c.round_count}回合：")
        
        # 如果选择了非怪物门，清除所有战斗状态
        door = self.doors[index]
        if door.event != "monster":
            p.clear_battle_status()  # 使用新的清除战斗状态方法
        p.adventure_status_duration_pass()  # Adventure turn effects
        
        # 进入门并处理事件
        door.enter(p, c)
        
        # 检查玩家生命值
        if p.hp <= 0:
            c.scene_manager.go_to("game_over_scene")
            return
            
        # 根据门类型切换到相应场景
        elif door.event == "monster":
            c.scene_manager.go_to("battle_scene")
        elif door.event == "shop":
            c.scene_manager.go_to("shop_scene")
        
        # 如果不是怪物门，重新生成门
        if door.event != "monster":
            self.generate_doors()

    def generate_doors(self, door_types=None):
        """生成三扇门，确保至少一扇是怪物门
        
        Args:
            door_types (list, optional): 指定门的类型列表，如 ["monster", "shop", "trap"]。
                                        如果为None，则随机生成门类型。
        """
        # 如果指定了门类型，使用指定的类型
        if door_types and len(door_types) == 3:
            self.doors = []
            for door_type in door_types:
                if door_type == "monster":
                    monster = get_random_monster(current_round=self.controller.round_count)
                    self.doors.append(Door.generate_monster_door(monster))
                elif door_type == "trap":
                    self.doors.append(Door.generate_trap_door())
                elif door_type == "reward":
                    self.doors.append(Door.generate_reward_door())
                elif door_type == "shop":
                    self.doors.append(Door.generate_shop_door())
        else:
            # 获取可用的门类型
            available_doors = ["trap", "reward", "shop"]
            if self.controller.player.gold > 0:
                available_doors.append("shop")
                
            # 生成一扇怪物门
            monster = get_random_monster(current_round=self.controller.round_count)
            monster_door = Door.generate_monster_door(monster)
            
            # 生成其他两扇门
            other_doors = []
            for _ in range(2):
                door_type = random.choice(available_doors)
                if door_type == "trap":
                    door = Door.generate_trap_door()
                elif door_type == "reward":
                    door = Door.generate_reward_door()
                elif door_type == "shop":
                    door = Door.generate_shop_door()
                other_doors.append(door)
                
            # 随机打乱三扇门的顺序
            self.doors = [monster_door] + other_doors
            random.shuffle(self.doors)
        
        # 更新按钮文本
        if self.doors:
            self.button_texts = [
                f"门1 - {self.doors[0].hint}",
                f"门2 - {self.doors[1].hint}",
                f"门3 - {self.doors[2].hint}"
            ]
        else:
            self.button_texts = ["门1", "门2", "门3"]

class BattleScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.monster = None
        self.button_texts = ["攻击", "使用道具", "逃跑"]
        self.monster_dead = False
        self.enum = SceneType.BATTLE

    def on_enter(self):
        # 使用 DoorScene 中提前生成的怪物
        self.monster = self.controller.current_monster

    def handle_choice(self, index):
        p = self.controller.player
        if p.has_status(StatusName.STUN):
            # 玩家晕眩时，怪物进行攻击
            self.controller.add_message("你处于眩晕状态, 无法行动!")
            self.monster.attack(p)
            p.battle_status_duration_pass()  # 处理状态持续时间
            self.monster.battle_status_duration_pass()
        else:
            monster_dead = False
            escaped = False
            if index == 0:
                monster_dead = p.attack(self.monster)
                
                if not monster_dead:
                    self.monster.attack(p)
                # 如果怪物死亡，处理战利品
                else:
                    # 处理怪物掉落
                    self.monster.process_loot(p)
                    # 清除所有战斗状态
                    p.clear_battle_status()  # 使用新的清除战斗状态方法
                    # 返回门场景
                    self.controller.scene_manager.go_to("door_scene")
            elif index == 1:
                self.do_use_item(p)
            elif index == 2:
                escaped = p.try_escape(self.monster)
                if escaped:
                    p.clear_battle_status()  # 使用新的清除战斗状态方法
                    self.monster.clear_battle_status()
                    self.controller.scene_manager.go_to("door_scene", generate_doors=False)
                else:
                    self.monster.attack(p)
                    self.controller.add_message("逃跑失败，怪物追了上来！")
                    p.battle_status_duration_pass()
                    self.monster.battle_status_duration_pass()

    def do_use_item(self, p):
        """处理使用道具的逻辑"""
        # 检查是否有可用的战斗物品
        battle_items = p.get_items_by_type(ItemType.BATTLE)
        if not battle_items:
            self.controller.add_message("你没有可用的道具！")
            return
        # 保存当前战斗场景作为上一个场景
        self.controller.scene_manager.last_scene = self
        # 跳转到道具使用场景
        self.controller.scene_manager.go_to("use_item_scene")
        self.controller.add_message("进入使用道具界面")

class ShopScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.button_texts = ["购买物品1", "购买物品2", "购买物品3"]
        self.enum = SceneType.SHOP
    def on_enter(self):
        """进入商店场景时的处理"""
        shop = self.controller.shop
        if shop is None:
            self.controller.add_message("商店未初始化")
            return
        shop.generate_items()
        if len(shop.shop_items) < 3:
            raise ValueError("商店没有足够的物品")
        if self.controller.player.gold == 0:
            self.controller.add_message("你没有钱，于是被商人踢了出来。")
            self.controller.scene_manager.go_to("door_scene")
            return
            
        # 更新按钮文本
        if shop.shop_items:
            self.button_texts = [
                f"{shop.shop_items[0].name} ({shop.shop_items[0].cost}G)",
                f"{shop.shop_items[1].name} ({shop.shop_items[1].cost}G)",
                f"{shop.shop_items[2].name} ({shop.shop_items[2].cost}G)"
            ]

    def handle_choice(self, index):
        logic = self.controller.shop
        success = logic.purchase_item(index)
        self.controller.scene_manager.go_to("door_scene")

class UseItemScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.active_items = []
        self.button_texts = ["返回", "返回", "返回"]
        self.enum = SceneType.USE_ITEM

    def on_enter(self):
        p = self.controller.player
        # 获取所有战斗物品
        battle_items = p.get_items_by_type(ItemType.BATTLE)
        self.active_items = battle_items
                
        if not self.active_items:
            self.controller.add_message("你没有可用的道具！返回战斗场景。")
            self.controller.scene_manager.go_to("battle_scene")
            return
            
        # 更新按钮文本
        self.button_texts = [
            self.active_items[0].name if len(self.active_items) > 0 else "返回",
            self.active_items[1].name if len(self.active_items) > 1 else "返回",
            self.active_items[2].name if len(self.active_items) > 2 else "返回"
        ]

    def handle_choice(self, index):
        p = self.controller.player
        if index < 0 or index >= len(self.active_items):
            self.controller.add_message("无效的道具选择")
            return
        item = self.active_items[index]
        if not item:
            self.controller.add_message("你没有选择任何道具")
            return
            
        # 使用物品效果
        item.effect(player=p, monster=self.controller.current_monster)
        
        # 使用完道具后，从背包中移除
        p.remove_item(item)
        
        self.controller.scene_manager.resume_scene()

class GameOverScene(Scene):
    def __init__(self, controller):
        super().__init__(controller)
        self.button_texts = ["重启游戏", "使用复活卷轴", "退出游戏"]
        self.enum = SceneType.GAME_OVER
    def on_enter(self):
        self.controller.add_message("游戏结束！")

    def handle_choice(self, index):
        if index == 0:  # 重启游戏
            self.controller.reset_game()
            self.controller.add_message("游戏已重置")
            self.controller.scene_manager.go_to("door_scene")
        elif index == 1:  # 使用复活卷轴
            p = self.controller.player
            # 检查是否有复活卷轴
            revive_scrolls = [item for item in p.get_items_by_type(ItemType.PASSIVE) 
                            if item.name == "复活卷轴"]
            if revive_scrolls:
                revive_scroll = revive_scrolls[0]
                p.hp = GameConfig.START_PLAYER_HP  # 恢复生命值
                p.remove_item(revive_scroll)  # 移除复活卷轴
                
                # 如果有上一个场景，恢复到那个场景，否则回到门场景
                if self.controller.scene_manager.last_scene:
                    self.controller.add_message(f"使用复活卷轴成功, 回到上一个场景: {self.controller.scene_manager.last_scene.__class__.__name__}!")
                    self.controller.scene_manager.resume_scene()
                else:
                    self.controller.add_message("使用复活卷轴成功, 回到门场景!")
                    self.controller.scene_manager.go_to("door_scene")
            else:
                self.controller.add_message("你没有可用的复活卷轴！")
        elif index == 2:  # 退出游戏
            self.controller.add_message("感谢游玩！")
            import sys
            sys.exit(0)  # 正常退出游戏

class SceneType(Enum):
    """场景名称枚举类"""
    DOOR =  DoorScene
    BATTLE = BattleScene
    SHOP = ShopScene
    USE_ITEM = UseItemScene
    GAME_OVER = GameOverScene

    @staticmethod
    def get_name_scene_dict():
        return {
            "door_scene": DoorScene,
            "battle_scene": BattleScene,
            "shop_scene": ShopScene,
            "use_item_scene": UseItemScene,
            "game_over_scene": GameOverScene
        }

    def is_scene_name(name: str)->bool:
        return name in SceneType.get_name_scene_dict().keys()
    
    def get_scene_class_by_name(name: str)->Scene:
        return SceneType.get_name_scene_dict().get(name)

class SceneManager:
    def __init__(self):
        self.current_scene = None
        self.last_scene = None
        self.game_controller = None
        self.scene_dict = {}
    
    def set_game_controller(self, game_controller):
        self.game_controller = game_controller
    
    def initialize_scenes(self):
        """初始化所有场景"""
        for scene_name in SceneType.get_name_scene_dict().keys():
            self.scene_dict[scene_name] = SceneType.get_scene_class_by_name(scene_name)(self.game_controller)
            self.scene_dict[scene_name].on_enter()
            scene = self.scene_dict[scene_name]
            if scene_name == SceneType.DOOR.value:
                scene.generate_doors()
        # 确保场景有默认按钮文本
            if not scene.button_texts or all(not text for text in scene.button_texts):
                scene.button_texts = ["选项1", "选项2", "选项3"]
        self.current_scene = self.scene_dict["door_scene"]

    def go_to(self, name, generate_doors=True):
        """切换到指定场景"""
        if SceneType.is_scene_name(name):
            self.last_scene = self.current_scene
            self.current_scene = self.scene_dict[name]
            self.current_scene.on_enter()
            if generate_doors and name == "door_scene":
                self.current_scene.generate_doors()
        else:
            print(f"场景 {name} 未注册!")
            # 如果场景不存在，返回到门场景
            self.go_to("door_scene")
    
    def resume_scene(self):
        """恢复上一个场景"""
        if self.last_scene is not None:
            self.current_scene = self.last_scene
        else:
            self.go_to("door_scene")