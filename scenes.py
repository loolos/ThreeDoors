"""场景与场景管理：选门、战斗、商店、道具使用、游戏结束与事件场景。"""
from models.door import Door, DoorEnum
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
        # 检查是否死亡（可能从EventScene带着0血量回来）
        if self.controller.player.hp <= 0:
            self.controller.scene_manager.go_to("game_over_scene")
            return

        # 首次进入冒险世界（新局或重置后）：展示世界观与真相暗示
        if self.controller.round_count == 0:
            self.controller.add_message(
                "你睁开眼，发现自己站在一条幽长的走廊里。眼前是三扇紧闭的门——"
                "据说每一扇背后都藏着截然不同的命运：战斗、奇遇、或是陷阱。\n"
                "这里无数走廊与门扉交织成一座没有出口的迷宫；"
                "而你，是又一位被卷入其中的闯入者。\n"
                "走廊深处传来若有若无的弦音与低语，像是早已写好的台词在暗处回响。\n"
                "这场冒险的终幕，或许正取决于你即将做出的每一个选择。"
            )

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
        if hasattr(c, "story") and c.story and hasattr(c.story, "ensure_default_normal_ending_schedule"):
            c.story.ensure_default_normal_ending_schedule()
        c.update_player_power_peaks()
        c.check_and_unlock_monster_tier()
        
        # 如果选择了非怪物门，清除所有战斗状态
        door = self.doors[index]
        if door.enum != DoorEnum.MONSTER:
            p.clear_battle_status()
            if hasattr(c, "clear_battle_extensions"):
                c.clear_battle_extensions()
            
        p.adventure_status_duration_pass()  # Adventure turn effects
        
        # 进入门并处理事件
        if hasattr(c, "story") and c.story:
            door = c.story.apply_pre_enter_checks(door)
            self.doors[index] = door
        door.enter()

        # 某些门在 enter 中会主动切场景（如被改写成剧情事件的商店门）
        cur = c.scene_manager.current_scene
        if not cur or cur.enum != SceneType.DOOR:
            return door.enum.name
        
        # 检查玩家生命值
        if p.hp <= 0:
            c.scene_manager.go_to("game_over_scene")
            return
            
        # 根据门类型切换到相应场景
        elif door.enum == DoorEnum.MONSTER:
            c.scene_manager.go_to("battle_scene")
        elif door.enum == DoorEnum.SHOP:
            if self.controller.player.gold <= 0:
                self.controller.add_message("你没有钱，于是被商人踢了出来。")
            else:
                c.scene_manager.go_to("shop_scene")
        # 如果不是怪物门，重新生成门
        if door.enum != DoorEnum.MONSTER:
            self.generate_doors()
        
        return door.enum.name
        

        

    def generate_doors(self, door_enums=None):
        """生成三扇门，确保至少一扇是怪物门
        
        Args:
            door_enums (list, optional): 指定门的类型列表，如 ["monster", "shop", "trap"]。
                                        如果为None，则随机生成门类型。
        """
        # 如果指定了门类型，使用指定的类型
        if door_enums and len(door_enums) == 3:
            self.doors = []
            for door_enum in door_enums:
                if DoorEnum.is_valid_door_enum(door_enum):
                    door = DoorEnum.create_instance(door_enum, controller=self.controller)
                    self.doors.append(door)
                else:
                    raise ValueError(f"无效的门类型: {door_enum}")
        else:
            # 获取非怪物门类型：用于生成另外两扇互不重复的门
            non_monster_door_enums = [door_enum for door_enum in DoorEnum if door_enum != DoorEnum.MONSTER]

            # 生成一扇怪物门
            monster = get_random_monster(
                current_round=self.controller.round_count,
                player=getattr(self.controller, "player", None),
                unlocked_tier=getattr(self.controller, "unlocked_monster_tier", GameConfig.START_UNLOCKED_MONSTER_TIER),
            )
            monster_door = DoorEnum.MONSTER.create_instance(monster=monster, controller=self.controller)
            # 生成其他两扇门（从非怪物类型中无放回抽样，确保类型不重复）
            extra_door_enums = random.sample(non_monster_door_enums, 2)
            self.doors = [monster_door]
            for door_enum in extra_door_enums:
                self.doors.append(door_enum.create_instance(controller=self.controller))
            
            # 随机打乱三扇门的顺序
            random.shuffle(self.doors)
        
        # 更新按钮文本（仅当至少 3 扇门时按索引访问，避免 IndexError）
        if len(self.doors) >= 3:
            self.button_texts = [
                f"门1 - {self.doors[0].hint}",
                f"门2 - {self.doors[1].hint}",
                f"门3 - {self.doors[2].hint}"
            ]
        else:
            self.button_texts = ["门1", "门2", "门3"]

class BattleScene(Scene):
    """战斗场景：与当前怪物战斗（攻击/使用道具/逃跑）。"""

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
        if self.monster is None:
            self.controller.add_message("未找到怪物，返回选门。")
            self.controller.scene_manager.go_to("door_scene")
            return
        p = self.controller.player
        if p.has_status(StatusName.STUN):
            # 玩家晕眩时，怪物进行攻击
            self.controller.add_message("你处于眩晕状态, 无法行动!")
            self.monster.attack(p)
            p.battle_status_duration_pass()  # 处理玩家状态持续时间
            self.monster.battle_status_duration_pass() # 处理怪物状态持续时间
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
                    if hasattr(self.controller, "story") and self.controller.story:
                        self.controller.story.resolve_battle_consequence(self.monster, defeated=True)
                        self.controller.story.record_elf_side_monster_outcome(self.monster, defeated=True)
                    # 若战斗收尾触发了结局（如即兴谢幕、普通结局），直接进入结局场景
                    if getattr(self.controller, "game_clear_info", None):
                        self.controller.scene_manager.go_to("game_over_scene")
                        return
                    # 若设置了战后事件（如击败木偶回声后的三选一事件门），先进入事件场景
                    pending_key = getattr(self.controller, "pending_post_battle_event_key", None)
                    if pending_key:
                        from models.events import get_story_event_by_key
                        event = get_story_event_by_key(pending_key, self.controller)
                        setattr(self.controller, "pending_post_battle_event_key", None)
                        if event is not None:
                            self.controller.current_event = event
                            if hasattr(self.controller, "clear_battle_extensions"):
                                self.controller.clear_battle_extensions()
                            self.controller.scene_manager.go_to("event_scene")
                            return
                    p.clear_battle_status() # 战斗胜利，清除战斗状态
                    if hasattr(self.controller, "clear_battle_extensions"):
                        self.controller.clear_battle_extensions()
                    self.controller.scene_manager.go_to("door_scene")
                
                # 无论怪物是否死亡，只要玩家行动了，就推进状态计时
                if not p.has_status(StatusName.STUN):
                    p.battle_status_duration_pass()
                    self.monster.battle_status_duration_pass()
            elif index == 1:
                self.do_use_item(p)
            elif index == 2:
                escaped = p.try_escape(self.monster)
                if escaped:
                    if hasattr(self.controller, "story") and self.controller.story:
                        self.controller.story.resolve_battle_consequence(self.monster, defeated=False)
                        self.controller.story.record_elf_side_monster_outcome(self.monster, defeated=False)
                    p.clear_battle_status()
                    self.monster.clear_battle_status()
                    if hasattr(self.controller, "clear_battle_extensions"):
                        self.controller.clear_battle_extensions()
                    self.controller.scene_manager.go_to("door_scene", generate_new_doors=False)
                else:
                    self.monster.attack(p)
                    self.controller.add_message("逃跑失败，怪物追了上来！")
                    p.battle_status_duration_pass()
                    self.monster.battle_status_duration_pass()
            if self.controller.player.hp <= 0:
                self.controller.scene_manager.go_to("game_over_scene")

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
    """商店场景：购买当前商店中的三件商品之一。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.button_texts = ["购买物品1", "购买物品2", "购买物品3"]
        self.enum = SceneType.SHOP

    def on_enter(self):
        """进入商店场景时的处理"""
        shop = self.controller.current_shop
        if shop is None:
            self.controller.add_message("商店未初始化")
            return
        shop.generate_items()
        if len(shop.shop_items) < 3:
            raise ValueError("商店没有足够的物品")
            
        # 更新按钮文本
        if shop.shop_items:
            self.button_texts = [
                f"{shop.shop_items[0].name} ({shop.shop_items[0].cost}G)",
                f"{shop.shop_items[1].name} ({shop.shop_items[1].cost}G)",
                f"{shop.shop_items[2].name} ({shop.shop_items[2].cost}G)"
            ]
        self.controller.add_message("你进入了杂货铺，老板热情的招呼你。")

    def handle_choice(self, index):
        logic = self.controller.current_shop
        if logic is None:
            self.controller.add_message("商店未就绪，返回选门。")
            self.controller.scene_manager.go_to("door_scene")
            return
        logic.purchase_item(index)
        self.controller.scene_manager.go_to("door_scene")

class UseItemScene(Scene):
    """使用道具场景：从战斗场景进入，选择一件战斗道具使用后返回战斗。"""

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
        # 如果选择的索引超出当前道具数量，视为“返回”
        if index >= len(self.active_items):
            self.controller.add_message("返回战斗...")
            self.controller.scene_manager.resume_scene()
            return

        if index < 0:
             self.controller.add_message("无效的选择")
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
    """游戏结束场景：可重启、使用复活卷轴或退出游戏。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.button_texts = ["重启游戏", "使用复活卷轴", "退出游戏"]
        self.enum = SceneType.GAME_OVER
    def on_enter(self):
        clear_info = getattr(self.controller, "game_clear_info", None)
        if clear_info:
            self.button_texts = ["重启游戏", "结局已达成", "退出游戏"]
            title = str(clear_info.get("ending_title", "")).strip()
            description = str(clear_info.get("ending_description", "")).strip()
            if title:
                self.controller.add_message(title)
            if description:
                self.controller.add_message(description)
            return
        self.button_texts = ["重启游戏", "使用复活卷轴", "退出游戏"]
        self.controller.add_message("游戏结束！")

    def handle_choice(self, index):
        clear_info = getattr(self.controller, "game_clear_info", None)
        if index == 0:  # 重启游戏
            self.controller.reset_game()
            self.controller.add_message("游戏已重置")
            self.controller.scene_manager.go_to("door_scene")
        elif index == 1:  # 使用复活卷轴
            if clear_info:
                self.controller.add_message("你已经抵达结局，无需使用复活卷轴。")
                return
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
            return "EXIT_GAME"

class EventScene(Scene):
    """事件场景：展示当前剧情事件选项并处理选择。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.enum = SceneType.EVENT
        self.button_texts = ["", "", ""]

    def on_enter(self):
        event = self.controller.current_event
        if event:
            choices = event.get_choices()
            # Ensure 3 buttons, fill empty with ""
            self.button_texts = (choices + ["", "", ""])[:3]

    def handle_choice(self, index):
        event = self.controller.current_event
        if event:
             if index < len(event.choices):
                 event.resolve_choice(index)
                 # Only transition if we haven't already switched scenes (e.g. to Game Over or Battle)
                 # AND if the player is still alive
                 if self.controller.player.hp > 0:
                     current = self.controller.scene_manager.current_scene
                     if current.enum == SceneType.EVENT:
                         self.controller.scene_manager.go_to("door_scene")
             else:
                 self.controller.add_message("无效的选择")


class SceneType(Enum):
    """场景名称枚举类"""
    DOOR =  DoorScene
    BATTLE = BattleScene
    SHOP = ShopScene
    USE_ITEM = UseItemScene
    GAME_OVER = GameOverScene
    EVENT = EventScene

    @staticmethod
    def get_name_scene_dict():
        """返回场景名称到场景类的映射。"""
        return {
            "door_scene": DoorScene,
            "battle_scene": BattleScene,
            "shop_scene": ShopScene,
            "use_item_scene": UseItemScene,
            "game_over_scene": GameOverScene,
            "event_scene": EventScene
        }

    @staticmethod
    def is_scene_name(name: str) -> bool:
        """判断给定名称是否为已注册的场景名。"""
        return name in SceneType.get_name_scene_dict().keys()

    @staticmethod
    def get_scene_class_by_name(name: str) -> type:
        """根据场景名返回对应的场景类，未找到则返回 None。"""
        return SceneType.get_name_scene_dict().get(name)


class SceneManager:
    """管理当前场景、上一场景及场景切换。"""

    def __init__(self):
        self.current_scene = None
        self.last_scene = None
        self.game_controller = None
        self.scene_dict = {}

    def set_game_controller(self, game_controller):
        """设置场景所依赖的游戏控制器。"""
        self.game_controller = game_controller
    
    def initialize_scenes(self):
        """初始化所有场景"""
        for scene_name in SceneType.get_name_scene_dict().keys():
            self.scene_dict[scene_name] = SceneType.get_scene_class_by_name(scene_name)(self.game_controller)
            scene = self.scene_dict[scene_name]
            if not scene.button_texts or all(not text for text in scene.button_texts):
                scene.button_texts = ["选项1", "选项2", "选项3"]
        self.go_to("door_scene")

    def go_to(self, name, generate_new_doors=True):
        """切换到指定场景"""
        if SceneType.is_scene_name(name):
            self.last_scene = self.current_scene
            self.current_scene = self.scene_dict[name]
            self.current_scene.on_enter()
            if generate_new_doors and name == "door_scene":
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
