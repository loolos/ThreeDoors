"""
综合游戏稳定性测试
"""
import unittest
import random
from server import GameController
from models.player import Player
from models.monster import Monster
from models.items import ItemType
from scenes import DoorScene, BattleScene, ShopScene, UseItemScene, GameOverScene, EventScene, SceneType
from models.door import DoorEnum
from test.test_base import BaseTest

class TestGameStability(BaseTest):
    """综合稳定性测试"""
    
    def test_random_button_clicks(self):
        """
        随机点击测试 (Fuzz Testing)
        模拟玩家随机点击按钮，验证游戏是否会崩溃或进入非法状态
        """
        print("\n开始 1000 次随机点击测试...")
        
        scene_stats = {}
        
        try:
            for i in range(1000):
                # 清空当前消息
                self.controller.clear_messages()
                
                # 记录当前场景访问次数
                current_scene = self.controller.scene_manager.current_scene
                scene_name = current_scene.__class__.__name__
                scene_stats[scene_name] = scene_stats.get(scene_name, 0) + 1
                
                # 确保当前场景有按钮
                if not hasattr(current_scene, 'button_texts') or not current_scene.button_texts:
                    continue
                    
                button_count = len(current_scene.button_texts)
                # 过滤掉空按钮
                valid_indices = [idx for idx, text in enumerate(current_scene.button_texts) if text.strip()]
                
                if not valid_indices:
                    continue
                
                # 如果是游戏结束场景，避免选择"退出游戏"按钮 (索引 2)
                if isinstance(current_scene, GameOverScene):
                    valid_indices = [idx for idx in valid_indices if idx != 2]
                
                if not valid_indices:
                    continue
                    
                random_choice = random.choice(valid_indices)
                
                # 记录点击前的状态 (Always use self.controller.player because reset_game replaces the object)
                p = self.controller.player
                before_scene = current_scene.enum
                button_text = current_scene.button_texts[random_choice]
                before_hp = p.hp
                before_gold = p.gold
                before_atk = p.atk
                
                # 执行点击
                try:
                    current_scene.handle_choice(random_choice)
                except Exception as e:
                    print(f"FAILED on click {i} in scene {scene_name} with button '{button_text}'")
                    raise e
                
                # 记录点击后的状态
                p = self.controller.player # Re-fetch in case of reset
                after_hp = p.hp
                after_gold = p.gold
                after_atk = p.atk
                after_scene_obj = self.controller.scene_manager.current_scene
                after_scene = after_scene_obj.enum
                
                # 验证状态波动
                is_game_reset = (before_scene == SceneType.GAME_OVER and after_scene == SceneType.DOOR)
                
                if not is_game_reset:
                    # 检查数值异常增加
                    self.assertLess(after_hp - before_hp, 1000, f"HP jump too high after '{button_text}'")
                    self.assertLess(after_gold - before_gold, 1000, f"Gold jump too high after '{button_text}'")
                    self.assertLess(after_atk - before_atk, 1000, f"Atk jump too high after '{button_text}'")
                
                # 验证场景跳转逻辑 (例如死亡必须进结算)
                if p.hp <= 0:
                    self.assertIsInstance(after_scene_obj, GameOverScene, 
                        f"Player dead (HP={p.hp}) but scene is {after_scene}")
                
                # 每 500 次打印进度
                if (i + 1) % 500 == 0:
                    print(f"已完成 {i + 1} 次点击，当前场景: {after_scene_obj.__class__.__name__}")

            print("\n场景访问统计：")
            for name, count in sorted(scene_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"{name}: {count}次")
            print("1000 次随机点击测试成功完成")
            
        except Exception as e:
            print(f"ERROR: Testing failed with exception: {str(e)}")
            raise e

if __name__ == "__main__":
    unittest.main()