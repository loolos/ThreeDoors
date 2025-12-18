"""
游戏集成测试
"""
from test.test_base import BaseTest
from models.game_config import GameConfig
from scenes import DoorScene, SceneType
from models.items import ItemType
import random

class TestGameSystem(BaseTest):
    """游戏系统集成测试"""
    
    def test_initialization(self):
        """测试游戏初始化状态"""
        self.assertEqual(self.player.hp, GameConfig.START_PLAYER_HP)
        self.assertEqual(self.player.gold, 0)
        self.assertEqual(self.controller.round_count, 0)
        self.assertIsInstance(self.controller.scene_manager.current_scene, DoorScene)
        
    def test_game_reset(self):
        """测试游戏重置功能"""
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

    def test_stability_random_walk(self):
        """随机游走稳定性测试"""
        # 简单模拟50步随机操作，确保不崩
        for _ in range(50):
            scene = self.controller.scene_manager.current_scene
            # 获取按钮数量
            btn_count = len(scene.get_button_texts())
            if btn_count > 0:
                choice = random.randint(0, btn_count - 1)
                # 避免并在GameOver时退出
                if scene.enum == SceneType.GAME_OVER and choice == 2:
                    choice = 0
                scene.handle_choice(choice)