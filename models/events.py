
import random
from models.items import create_random_item

class EventChoice:
    def __init__(self, text, callback):
        self.text = text
        self.callback = callback

class Event:
    def __init__(self, controller):
        self.controller = controller
        self.title = "Event"
        self.description = "Something happens."
        self.choices = []

    def get_choices(self):
        return [c.text for c in self.choices]

    def resolve_choice(self, index):
        if 0 <= index < len(self.choices):
            return self.choices[index].callback()
        return "Invalid choice."

    def add_message(self, msg):
        self.controller.add_message(msg)
    
    def get_player(self):
        return self.controller.player


# 1. Injured Stranger
class StrangerEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Injured Stranger"
        self.description = "你看到一个满身是血的陌生人倒在路边，看起来非常虚弱。"
        self.choices = [
            EventChoice("救助他 (失去10金币)", self.help_stranger),
            EventChoice("抢劫他", self.rob_stranger),
            EventChoice("无视离开", self.ignore_stranger)
        ]

    def help_stranger(self):
        p = self.get_player()
        if p.gold >= 10:
            p.gold -= 10
            # Reward: Item
            item = create_random_item()
            item.acquire(player=p)
            self.add_message("你花费10金币为陌生人包扎。")
            self.add_message(f"陌生人感激地给了你 {item.name} 作为回报！")
        else:
            self.add_message("你囊中羞涩，无法提供帮助，只能遗憾离开。")
        return "Event Completed"

    def rob_stranger(self):
        p = self.get_player()
        gold = random.randint(5, 20)
        p.gold += gold
        self.add_message(f"你抢走了陌生人仅剩的 {gold} 金币。你的良心受到了一点谴责。")
        return "Event Completed"

    def ignore_stranger(self):
        self.add_message("你冷漠地走开了，不想惹麻烦。")
        return "Event Completed"


# 2. Smuggler
class SmugglerEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Smuggler"
        self.description = "一个看起来鬼鬼祟祟的走私犯向你兜售货物。"
        self.item = create_random_item()
        self.cost = max(10, int(self.item.cost * 0.7)) # 30% off usually
        
        self.choices = [
            EventChoice(f"购买 {self.item.name} ({self.cost}G)", self.buy_item),
            EventChoice("举报他", self.report_smuggler),
            EventChoice("离开", self.leave)
        ]

    def buy_item(self):
        p = self.get_player()
        if p.gold >= self.cost:
            p.gold -= self.cost
            self.item.acquire(player=p)
            self.add_message(f"你以 {self.cost}G 的低价买到了 {self.item.name}！")
        else:
            self.add_message("走私犯翻了个白眼：'没钱就滚！'")
        return "Event Completed"

    def report_smuggler(self):
        if random.random() < 0.5:
            reward = random.randint(30, 60)
            self.get_player().gold += reward
            self.add_message(f"卫兵抓住了走私犯，并奖励你 {reward} 金币！")
        else:
            dmg = random.randint(5, 15)
            self.get_player().take_damage(dmg)
            self.add_message(f"走私犯发现了你的意图，把你揍了一顿后跑了！受到 {dmg} 点伤害。")
        return "Event Completed"

    def leave(self):
        self.add_message("你摇摇头，转身离开了。")
        return "Event Completed"


# 3. Ancient Shrine
class AncientShrineEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Ancient Shrine"
        self.description = "一座古老的祭坛矗立在森林深处，上面刻满了神秘的符文。"
        self.choices = [
            EventChoice("虔诚祈祷 (恢复50HP)", self.pray),
            EventChoice("破坏祭坛", self.desecrate),
            EventChoice("仔细调查", self.inspect)
        ]

    def pray(self):
        p = self.get_player()
        p.heal(50) 
        self.add_message("一道温暖的光芒笼罩着你，你的伤势恢复了 50 点！")
        return "Event Completed"

    def desecrate(self):
        p = self.get_player()
        gold = random.randint(50, 100)
        p.gold += gold
        self.add_message(f"你在祭坛下挖出了 {gold} 金币！")
        if random.random() < 0.5:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"但这触怒了神灵，一道闪电劈中了你！受到 {dmg} 点伤害。")
        return "Event Completed"

    def inspect(self):
        if random.random() < 0.7:
             item = create_random_item()
             item.acquire(player=self.get_player())
             self.add_message(f"你在祭坛后面发现了一个遗落的包裹，里面有 {item.name}！")
        else:
             self.add_message("你研究了半天，除了一些灰尘什么也没发现。")
        return "Event Completed"

# 4. Gambler Event
class GamblerEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "The Gambler"
        self.description = "一个流浪赌徒向你发起挑战：'想不想玩把大的？'"
        self.choices = [
            EventChoice("玩把大的 (赌50G)", self.high_stakes),
            EventChoice("小玩一把 (赌10G)", self.low_stakes),
            EventChoice("拒绝", self.decline)
        ]

    def high_stakes(self):
        p = self.get_player()
        bet = 50
        if p.gold < bet:
            self.add_message("你没有足够的金币！赌徒嘲笑了你一番。")
            return "Event Completed"
        
        p.gold -= bet
        if random.random() < 0.4: # 40% win rate
            win = bet * 3
            p.gold += win
            self.add_message(f"你运气爆棚！赢了 {win} 金币！")
        else:
            self.add_message("你输了！50金币打水漂了。")
        return "Event Completed"

    def low_stakes(self):
        p = self.get_player()
        bet = 10
        if p.gold < bet:
             self.add_message("你连10金币都没有？真可怜。")
             return "Event Completed"
        
        p.gold -= bet
        if random.random() < 0.5: # 50% win rate
            win = bet * 2
            p.gold += win
            self.add_message(f"不错，赢了 {win} 金币。")
        else:
            self.add_message("哎呀，运气不好，输了10金币。")
        return "Event Completed"

    def decline(self):
        self.add_message("你拒绝了赌博，赌徒无趣地走开了。")
        return "Event Completed"


# 5. Lost Child Event
class LostChildEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Lost Child"
        self.description = "一个小女孩在森林里哭泣，看起来迷路了。"
        self.choices = [
            EventChoice("护送回家", self.guide_home),
            EventChoice("给点金币路费 (20G)", self.give_gold),
            EventChoice("无视", self.ignore)
        ]

    def guide_home(self):
        # High risk (time/encounter), High reward
        if random.random() < 0.3:
            # Encounter monster logic could be complex, for now simple damage from "exhaustion"
            dmg = 15
            self.get_player().take_damage(dmg)
            self.add_message(f"送回家的路上遭遇了野兽袭击，你为了保护孩子受了伤 ({dmg}点伤害)，但最终把她安全送达。")
            # Reward
            reward = 100
            self.get_player().gold += reward
            self.add_message(f"孩子的父母感激涕零，给了你 {reward} 金币作为谢礼！")
        else:
            reward = 50
            self.get_player().gold += reward
            self.add_message(f"你顺利把孩子送回了家。她父母给了你 {reward} 金币。")
        return "Event Completed"

    def give_gold(self):
        p = self.get_player()
        if p.gold >= 20:
            p.gold -= 20
            self.add_message("你给了小女孩20金币让她自己打车回家（虽然森林里没有出租车）。")
            # Karma reward (small heal)
            p.heal(10)
            self.add_message("做善事让你心情愉悦，恢复了 10 HP。")
        else:
            self.add_message("你想帮忙但没钱，只能尴尬地安慰了几句。")
        return "Event Completed"

    def ignore(self):
        self.add_message("这里是残酷的世界，你选择了无视。")
        return "Event Completed"


# 6. Cursed Chest
class CursedChestEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Cursed Chest"
        self.description = "一个散发着诡异紫光的宝箱，上面刻着警告语：'贪婪者必受惩罚'。"
        self.choices = [
            EventChoice("强行打开", self.open_chest),
            EventChoice("试图净化", self.purify),
            EventChoice("离开", self.leave)
        ]

    def open_chest(self):
        p = self.get_player()
        if random.random() < 0.6: # 60% bad
            dmg = 20
            p.take_damage(dmg)
            self.add_message(f"宝箱突然咬了你一口！受到 {dmg} 点巨大伤害。里面什么也没有。")
        else:
            item = create_random_item()
            item.acquire(player=p)
            gold = 100
            p.gold += gold
            self.add_message(f"你忍受着诅咒的侵蚀打开了箱子，获得了 {item.name} 和 {gold} 金币！")
        return "Event Completed"

    def purify(self):
        # Assume successful purify for now, or random
        if random.random() < 0.5:
            gold = 50
            self.get_player().gold += gold
            self.add_message(f"你成功净化了诅咒，箱子里只剩下一些普通的财宝 ({gold}G)。")
        else:
            self.add_message("你的净化失败了，箱子消失在虚空中。")
        return "Event Completed"

    def leave(self):
        self.add_message("你明智地远离了诅咒之物。")
        return "Event Completed"


# 7. Wise Sage
class WiseSageEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Wise Sage"
        self.description = "一位白胡子老者拦住了去路：'年轻的勇士，为了什么而战？'"
        self.choices = [
            EventChoice("为了力量 (加攻击)", self.power),
            EventChoice("为了财富 (加金币)", self.wealth),
            EventChoice("为了生存 (恢复50HP)", self.health)
        ]

    def power(self):
        p = self.get_player()
        p.atk += 3
        self.add_message("老者点了点头：'力量是双刃剑。' 你的攻击力永久 +3。")
        return "Event Completed"

    def wealth(self):
        p = self.get_player()
        gold = 200
        p.gold += gold
        self.add_message(f"老者叹了口气：'身外之物。' 他丢给你 {gold} 金币后消失了。")
        return "Event Completed"

    def health(self):
        p = self.get_player()
        p.heal(50)
        self.add_message("老者微笑道：'活着就有希望。' 你的生命值恢复了 50 点。")
        return "Event Completed"


def get_random_event(controller):
    events = [
        StrangerEvent, SmugglerEvent, AncientShrineEvent, 
        GamblerEvent, LostChildEvent, CursedChestEvent, WiseSageEvent
    ]
    event_cls = random.choice(events)
    return event_cls(controller)
