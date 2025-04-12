from abc import ABC, abstractmethod
from typing import Type, Any, Dict, Optional
from enum import Enum


class BaseClass(ABC):
    """
    游戏实体的抽象基类，定义了所有游戏实体必须实现的基本接口。
    """
    
    def __init__(self, **kwargs):
        """
        初始化基类实例。
        这个方法会在创建实例时自动调用。
        
        Args:
            **kwargs: 子类特定的初始化参数
        """
        self._initialize(**kwargs)
    
    @abstractmethod
    def _initialize(self, **kwargs) -> None:
        """
        子类必须实现的初始化方法。
        这个方法由__init__调用，用于实现子类特定的初始化逻辑。
        
        Args:
            **kwargs: 子类特定的初始化参数
        """
        self.controller = kwargs.get('controller', None)
        if not self.controller:
            raise ValueError("controller is required")


# 示例：如何创建新的类
class Player(BaseClass):
    """玩家类"""
    
    def _initialize(self, **kwargs) -> None:
        self.hp = kwargs.get('hp', 100)
        self.atk = kwargs.get('atk', 10)

class Monster(BaseClass):
    """怪物类"""
    
    def _initialize(self, **kwargs) -> None:
        self.hp = kwargs.get('hp', 50)
        self.atk = kwargs.get('atk', 5)
        self.name = kwargs.get('name', '未知怪物')


# 使用Enum管理子类
class ClassEnum(Enum):
    """实体类型枚举"""
    
    PLAYER = Player
    MONSTER = Monster
    
    def create_instance(self, **kwargs) -> BaseClass:
        """创建实体实例"""
        return self.value(**kwargs)