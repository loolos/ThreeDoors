from models.door import Door
from models.monster import Monster, get_random_monster
from .status import Status, StatusName
from .game_config import GameConfig
from models.items import ItemType, ReviveScroll, FlyingHammer, GiantScroll, Barrier
import random

class Player:
    def __init__(self, controller):
        """初始化玩家"""
        self.controller = controller
        self._atk = 0  # 基础攻击力
        self.reset()

    @property
    def atk(self):
        """获取当前攻击力（基础 + 状态修正）"""
        total_atk = self._atk
        
        # 1. 加法修正
        if self.has_status(StatusName.ATK_UP):
            total_atk += self.statuses[StatusName.ATK_UP].value
        if self.has_status(StatusName.WEAK):
            total_atk -= 2 # 虚弱固定减2
            
        # 2. 乘法修正
        if self.has_status(StatusName.ATK_MULTIPLIER):
            total_atk *= self.statuses[StatusName.ATK_MULTIPLIER].value
            
        return max(1, int(total_atk))

    @atk.setter
    def atk(self, value):
        """兼容性 setter，以后应尽量使用 change_base_atk"""
        self._atk = value

    def change_base_atk(self, delta: int):
        """修改基础攻击力并记录日志"""
        old_atk = self._atk
        self._atk += delta
        self.controller.add_message(f"你的基础攻击力增加了 {delta} 点! (当前基础: {self._atk})")

    def _init_default_items(self):
        """初始化默认物品"""
        revive_scroll = ReviveScroll("复活卷轴", cost=0)
        flying_hammer = FlyingHammer("飞锤", cost=0, duration=3)
        giant_scroll = GiantScroll("巨大卷轴", cost=0, duration=3)
        barrier = Barrier("结界", cost=0, duration=3)
        
        self.add_item(revive_scroll)
        self.add_item(flying_hammer)
        self.add_item(giant_scroll)
        self.add_item(barrier)

    def take_damage(self, damage: int):
        """受到伤害"""
        # 检查是否有减伤效果
        if self.has_status(StatusName.DAMAGE_REDUCTION):
            # 获取减伤比例 (默认 0.7 即减免 30%，如果是减伤卷轴可能是 0.25)
            reduction = self.statuses[StatusName.DAMAGE_REDUCTION].value
            damage = max(1, int(damage * reduction))
            self.controller.add_message(f"减伤效果触发，受到伤害减至 {int(reduction * 100)}%!")
            
        # 应用伤害
        self.hp -= damage
        self.controller.add_message(f"你受到了 {damage} 点伤害! 剩余生命值: {self.hp}。")
        
        # 检查是否死亡
        if self.hp <= 0:
            # 检查是否有复活卷轴
            for item in self.inventory.get(ItemType.PASSIVE, []):
                if item.name == "复活卷轴":
                    self.hp = GameConfig.START_PLAYER_HP  # 使用初始生命值
                    self.inventory[ItemType.PASSIVE].remove(item)  # 移除复活卷轴

                    self.controller.add_message("复活卷轴效果触发，你复活了!")
                    return
                    
            # 如果没有复活卷轴，游戏结束
            self.controller.add_message("你被击败了!")
            self.controller.scene_manager.go_to("game_over_scene")
            return
    def clear_inventory(self):
        """重置背包"""
        self.inventory = {
            ItemType.CONSUMABLE: [],
            ItemType.BATTLE: [],
            ItemType.PASSIVE: []
        }
    def player_desc(self):
        """玩家描述"""
        return f"生命值: {self.hp}, 攻击力: {self.atk}, 金币: {self.gold}, 背包: {self.inventory}"
    def heal(self, amount):
        """恢复生命值"""
        old_hp = self.hp
        self.hp += amount
        return self.hp - old_hp  # 返回实际恢复的生命值

    def add_gold(self, amt):
        self.gold += amt

    def attack(self, target):
        """玩家攻击目标"""
        # 检查是否晕眩
        if self.has_status(StatusName.STUN):
            self.controller.add_message("你处于眩晕状态, 无法行动")
            return False
            
        # 应用战斗状态效果
        
        # 计算伤害
        dmg = max(1, self.atk - random.randint(0, 1))
        
        # 如果有攻击力翻倍效果
        if self.has_status(StatusName.ATK_MULTIPLIER):
            dmg *= self.statuses[StatusName.ATK_MULTIPLIER].value
        
        # 造成伤害
        target.take_damage(dmg)
        self.controller.add_message(f"你攻击 {target.name} 造成 {dmg} 点伤害.")
        # 检查目标是否死亡
        if target.hp <= 0:
            self.controller.add_message(f"你击败了 {target.name}!")
            return True
        
        return False

    def try_escape(self, monster):
        """尝试逃跑"""
        # 计算逃跑概率
        escape_chance = 0.3  # 基础30%概率
        if self.has_status(StatusName.WEAK):
            escape_chance -= 0.1  # 虚弱状态降低10%概率
        if self.has_status(StatusName.POISON):
            escape_chance -= 0.1  # 中毒状态降低10%概率
        if self.has_status(StatusName.STUN):
            escape_chance -= 1  # 晕眩状态降低100%概率
            
        # 尝试逃跑
        if random.random() < escape_chance:
            self.controller.add_message("你成功逃脱了!")
            return True
        else:
            # 逃跑失败，受到伤害
            mdmg = max(1, monster.atk - random.randint(0, 1))
            actual_dmg = self.take_damage(mdmg)
            self.controller.add_message(f"逃跑失败，{monster.name} 反击造成 {actual_dmg} 点伤害!")
            return False

    def adventure_status_duration_pass(self) -> None:
        """处理冒险回合的状态持续时间"""
        expired = []
        for st in self.statuses:
            if not self.statuses[st].is_battle_only:
                if self.statuses[st].duration_pass():
                    expired.append(st)
        
        # 移除过期状态
        for st in expired:
            del self.statuses[st]

    def battle_status_duration_pass(self) -> None:
        """处理战斗回合的状态持续时间"""
        expired = []
        for st in self.statuses:
            if self.statuses[st].is_battle_only:
                if self.statuses[st].duration_pass():
                    expired.append(st)
        
        # 移除过期状态
        for st in expired:
            del self.statuses[st]

    def clear_battle_status(self) -> None:
        """清除所有战斗状态"""
        expired = []
        for status_name, status in self.statuses.items():
            if status.is_battle_only:
                expired.append(status_name)
        
        # 移除战斗状态
        for status_name in expired:
            del self.statuses[status_name]

    def get_status_desc(self):
        """获取状态描述"""
        if not self.statuses:
            return "无"
            
        desc = []
        for status_enum, status in self.statuses.items():
            if isinstance(status, Status):
                # 获取状态名称的中文描述
                status_name_cn = status_enum.cn_name
                
                # 如果有特殊值（如攻击力翻倍的倍数），显示出来
                if status_enum == StatusName.ATK_MULTIPLIER and hasattr(status, 'value'):
                    desc.append(f"{status_name_cn}({status.duration}回合)x{status.value}")
                else:
                    desc.append(f"{status_name_cn}({status.duration}回合)")
                    
        return ", ".join(desc)

    def add_item(self, item):
        """添加物品到背包"""
        item_type = item.get_type()
        if item_type not in self.inventory:
            self.inventory[item_type] = []
        self.inventory[item_type].append(item)
        
    def get_items_by_type(self, item_type):
        """获取指定类型的物品列表"""
        return self.inventory.get(item_type, [])
        
    def remove_item(self, item):
        """从背包中移除物品"""
        item_type = item.get_type()
        if item_type in self.inventory and item in self.inventory[item_type]:
            self.inventory[item_type].remove(item)
            if not self.inventory[item_type]:
                del self.inventory[item_type]
                
    def get_inventory_size(self):
        """获取背包中物品总数"""
        return sum(len(items) for items in self.inventory.values())

    def reset(self):
        """重置玩家状态"""
        self.hp = GameConfig.START_PLAYER_HP
        self._atk = GameConfig.START_PLAYER_ATK
        self.gold = 0
        self.inventory = {
            ItemType.CONSUMABLE: [],
            ItemType.BATTLE: [],
            ItemType.PASSIVE: []
        }
        self.statuses = {}
        self._init_default_items()


    def apply_status(self, status: Status) -> None:
        """应用状态效果
        
        Args:
            status: 要应用的状态
        """
        # 检查状态是否在StatusName枚举中
        if not isinstance(status.enum, StatusName):
            return
            
        # 检查是否是负面状态且是否有免疫效果
        negative_statuses = [StatusName.WEAK, StatusName.POISON, StatusName.STUN, StatusName.FIELD_POISON]
        if status.enum in negative_statuses and self.has_status(StatusName.IMMUNE):
            if hasattr(self, 'controller') and self.controller:
                # 获取状态名称的中文描述
                status_name_cn = status.enum.cn_name
                self.controller.add_message(f"免疫效果保护了你免受 {status_name_cn} 效果!")
            return
            
        if status.enum in self.statuses:
            # 如果已有相同状态，进行叠加
            self.statuses[status.enum].combine(status)
        else:
            # 如果是新状态，直接添加并启动效果
            status.start_effect()  # 确保状态效果被正确启动
            self.statuses[status.enum] = status

    def has_status(self, status_name: StatusName) -> bool:
        """检查是否具有指定状态
        
        Args:
            status_name: 要检查的状态名称
            
        Returns:
            如果具有该状态且持续时间大于0，返回 True
        """
        # 检查状态是否在StatusName枚举中
        if not isinstance(status_name, StatusName):
            return False
            
        return (status_name in self.statuses and 
                isinstance(self.statuses[status_name], Status) and 
                self.statuses[status_name].duration > 0)

    def get_status_duration(self, status_name: StatusName) -> int:
        """获取指定状态的剩余持续时间
        
        Args:
            status_name: 状态名称
            
        Returns:
            状态的剩余持续时间，如果状态不存在则返回0
        """
        if self.has_status(status_name):
            return self.statuses[status_name].duration
        return 0