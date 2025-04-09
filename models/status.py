import random
from enum import Enum
from typing import Any, Optional

class StatusName(Enum):
    WEAK = "weak"              # 虚弱状态
    POISON = "poison"          # 中毒状态
    STUN = "stun"             # 晕眩状态
    ATK_MULTIPLIER = "atk_multiplier"  # 攻击力翻倍
    BARRIER = "barrier"        # 结界状态
    ATK_UP = "atk_up"         # 攻击力提升
    DAMAGE_REDUCTION = "damage_reduction"  # 伤害减免
    HEALING_SCROLL = "healing_scroll"  # 恢复卷轴
    IMMUNE = "immune"         # 免疫状态

    @property
    def cn_name(self) -> str:
        """获取状态的中文名称"""
        return {
            StatusName.WEAK: "虚弱",
            StatusName.POISON: "中毒",
            StatusName.STUN: "晕眩",
            StatusName.ATK_MULTIPLIER: "攻击力翻倍",
            StatusName.BARRIER: "结界",
            StatusName.ATK_UP: "攻击力提升",
            StatusName.DAMAGE_REDUCTION: "减伤",
            StatusName.HEALING_SCROLL: "恢复",
            StatusName.IMMUNE: "免疫"
        }.get(self, self.value)

class Status:
    """状态效果基类"""
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "未知状态")
        self.enum = StatusName(self.name)  # 直接设置 enum 属性
        self.duration = kwargs.get("duration", 0)
        self.is_battle_only = kwargs.get("is_battle_only", False)
        self.description = kwargs.get("description", "")
        self.target = kwargs.get("target", None)
        self.start_effect()
        
    def start_effect(self) -> None:
        """状态效果开始时调用"""
        pass
        
    def end_effect(self) -> None:
        """状态效果结束时调用"""
        pass
        
    def duration_pass(self) -> bool:
        """每回合结束时调用"""
        self.duration -= 1
        if self.duration <= 0:
            self.end_effect()
            return True
        return False

    def combine(self, other: 'Status') -> None:
        """处理相同状态的叠加
        
        Args:
            other: 要叠加的状态
        """
        if not isinstance(other, Status) or self.name != other.name:
            return
            
        # 默认叠加规则：取最大持续时间
        old_duration = self.duration
        self.duration = max(self.duration, other.duration)
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            self.target.controller.add_message(f"{self.name} 状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class WeakStatus(Status):
    """虚弱状态"""
    def __init__(self, **kwargs):
        super().__init__(
            name=StatusName.WEAK,
            description="攻击力降低2点",
            duration=kwargs.get("duration", 3),
            is_battle_only=True,
            target=kwargs.get("target")
        )
        
    def start_effect(self) -> None:
        self.target.atk = max(1, self.target.atk - 2)
        
    def end_effect(self) -> None:
        self.target.atk = self.target.atk + 2

    def combine(self, other: 'Status') -> None:
        """虚弱状态叠加：只叠加持续时间"""
        if not isinstance(other, WeakStatus):
            return
        old_duration = self.duration
        self.duration = max(self.duration, other.duration)
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            self.target.controller.add_message(f"虚弱状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class PoisonStatus(Status):
    """中毒状态"""
    def __init__(self, **kwargs):
        super().__init__(
            name=StatusName.POISON,
            description="每回合损失10%生命值",
            duration=kwargs.get("duration", 3),
            is_battle_only=True,
            target=kwargs.get("target")
        )
        
    def duration_pass(self) -> bool:
        if not self.target.has_status(StatusName.IMMUNE):
            damage = max(1, int(self.target.hp * 0.1))
            self.target.take_damage(damage)
            self.target.controller.add_message(f"中毒效果造成 {damage} 点伤害！")
        return super().duration_pass()

    def combine(self, other: 'Status') -> None:
        """中毒状态叠加：只叠加持续时间"""
        if not isinstance(other, PoisonStatus):
            return
        old_duration = self.duration
        self.duration = max(self.duration, other.duration)
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            self.target.controller.add_message(f"中毒状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class StunStatus(Status):
    """晕眩状态"""
    def __init__(self, **kwargs):
        super().__init__(
            name=StatusName.STUN,
            description="无法行动",
            duration=kwargs.get("duration", 2),
            is_battle_only=True,
            target=kwargs.get("target")
        )

    def combine(self, other: 'Status') -> None:
        """晕眩状态叠加：只叠加持续时间"""
        if not isinstance(other, StunStatus):
            return
        old_duration = self.duration
        self.duration = max(self.duration, other.duration)
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            self.target.controller.add_message(f"晕眩状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class AtkMultiplierStatus(Status):
    """攻击力翻倍状态"""
    def __init__(self, **kwargs):
        self.value = kwargs.get("value", 2)
        if self.value <= 0:
            raise ValueError("Value must be positive")
        super().__init__(
            name=StatusName.ATK_MULTIPLIER,
            description="攻击力翻倍",
            duration=kwargs.get("duration", 1),
            is_battle_only=True,
            target=kwargs.get("target")
        )
        
    def start_effect(self) -> None:
        self.target.atk *= self.value
        
    def end_effect(self) -> None:
        self.target.atk //= self.value

    def combine(self, other: 'Status') -> None:
        """攻击力翻倍状态叠加：取最大倍数"""
        if not isinstance(other, AtkMultiplierStatus):
            return
        old_duration = self.duration
        old_value = self.value
        self.duration = max(self.duration, other.duration)
        self.value = max(self.value, other.value)
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            if old_value != self.value:
                self.target.controller.add_message(f"攻击力翻倍效果从 {old_value} 倍提升至 {self.value} 倍!")
            if old_duration != self.duration:
                self.target.controller.add_message(f"攻击力翻倍状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class BarrierStatus(Status):
    """结界状态"""
    def __init__(self, **kwargs):
        super().__init__(
            name=StatusName.BARRIER,
            description="免疫怪物伤害",
            duration=kwargs.get("duration", 3),
            is_battle_only=True,
            target=kwargs.get("target")
        )

    def combine(self, other: 'Status') -> None:
        """结界状态叠加：只叠加持续时间"""
        if not isinstance(other, BarrierStatus):
            return
        old_duration = self.duration
        self.duration = max(self.duration, other.duration)
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            self.target.controller.add_message(f"结界状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class AtkUpStatus(Status):
    """攻击力提升状态"""
    def __init__(self, **kwargs):
        self.value = kwargs.get("value", 2)
        if self.value <= 0:
            raise ValueError("Value must be positive")
        super().__init__(
            name=StatusName.ATK_UP,
            description="攻击力增加",
            duration=kwargs.get("duration", 5),
            is_battle_only=False,
            target=kwargs.get("target")
        )
        
    def start_effect(self) -> None:
        self.target.atk += self.value
        
    def end_effect(self) -> None:
        self.target.atk -= self.value

    def combine(self, other: 'Status') -> None:
        """攻击力提升状态叠加：效果值相加"""
        if not isinstance(other, AtkUpStatus):
            return
        old_duration = self.duration
        old_value = self.value
        self.duration = max(self.duration, other.duration)
        self.value += other.value
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            if old_value != self.value:
                self.target.controller.add_message(f"攻击力提升效果从 {old_value} 点提升至 {self.value} 点!")
            if old_duration != self.duration:
                self.target.controller.add_message(f"攻击力提升状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class DamageReductionStatus(Status):
    """伤害减免状态"""
    def __init__(self, **kwargs):
        super().__init__(
            name=StatusName.DAMAGE_REDUCTION,
            description="受到伤害减少30%",
            duration=kwargs.get("duration", 5),
            is_battle_only=False,
            target=kwargs.get("target")
        )
        self.value = kwargs.get("value", 0.7)
        if not 0 < self.value < 1:
            raise ValueError("Value must be between 0 and 1")

    def combine(self, other: 'Status') -> None:
        """减伤状态叠加：叠加持续时间"""
        if not isinstance(other, DamageReductionStatus):
            return
        old_duration = self.duration
        self.duration += other.duration
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            self.target.controller.add_message(f"减伤状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class HealingScrollStatus(Status):
    """恢复卷轴状态"""
    def __init__(self, **kwargs):
        super().__init__(
            name=StatusName.HEALING_SCROLL,
            description="每回合恢复生命",
            duration=kwargs.get("duration", 10),
            is_battle_only=False,
            target=kwargs.get("target")
        )
        self.value = kwargs.get("value", 5)
        if self.value <= 0:
            raise ValueError("Value must be positive")
        
    def duration_pass(self) -> bool:
        heal_amount = random.randint(1, self.value)
        self.target.heal(heal_amount)
        self.target.controller.add_message(f"恢复卷轴生效，恢复 {heal_amount} 点生命！")
        return super().duration_pass()

    def combine(self, other: 'Status') -> None:
        """恢复卷轴状态叠加：叠加持续时间"""
        if not isinstance(other, HealingScrollStatus):
            return
        old_duration = self.duration
        self.duration += other.duration
        if hasattr(self, 'target') and self.target and hasattr(self.target, 'controller'):
            self.target.controller.add_message(f"恢复卷轴状态持续时间从 {old_duration} 回合延长至 {self.duration} 回合!")

class ImmuneStatus(Status):
    """免疫状态"""
    def __init__(self, **kwargs):
        super().__init__(
            name=StatusName.IMMUNE,
            description="免疫所有负面效果",
            duration=kwargs.get("duration", 5),
            is_battle_only=False,
            target=kwargs.get("target")
        )

    def combine(self, other: 'Status') -> None:
        """免疫状态叠加：叠加持续时间"""
        if not isinstance(other, ImmuneStatus):
            return
        old_duration = self.duration
        self.duration += other.duration
        if old_duration != self.duration:
            self.target.controller.add_message(f"免疫效果从 {old_duration} 回合提升至 {self.duration} 回合!")

def CreateStatusByName(status_name: StatusName, **kwargs) -> Status:
    """根据状态名称创建对应的状态实例
    
    Args:
        status_name: 状态名称枚举
        **kwargs: 传递给状态构造函数的参数
        
    Returns:
        创建的状态实例
    """
    status_map = {
        StatusName.WEAK: WeakStatus,
        StatusName.POISON: PoisonStatus,
        StatusName.STUN: StunStatus,
        StatusName.ATK_MULTIPLIER: AtkMultiplierStatus,
        StatusName.BARRIER: BarrierStatus,
        StatusName.ATK_UP: AtkUpStatus,
        StatusName.DAMAGE_REDUCTION: DamageReductionStatus,
        StatusName.HEALING_SCROLL: HealingScrollStatus,
        StatusName.IMMUNE: ImmuneStatus
    }
    
    if status_name not in status_map:
        raise ValueError(f"Unknown status name: {status_name}")
        
    return status_map[status_name](**kwargs)