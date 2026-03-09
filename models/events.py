
import random
from models.items import create_random_item
from models.status import StatusName

class EventChoice:
    def __init__(self, text, callback):
        self.text = text
        self.callback = callback

class Event:
    TRIGGER_BASE_PROBABILITY = 0.1

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

    def register_story_choice(self, choice_flag, moral_delta=0, consequences=None):
        story = getattr(self.controller, "story", None)
        if not story:
            return
        story.register_choice(
            choice_flag=choice_flag,
            moral_delta=moral_delta,
            consequences=consequences or [],
        )

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return True

    @classmethod
    def get_trigger_probability(cls, controller):
        return cls.TRIGGER_BASE_PROBABILITY


# 1. Injured Stranger
class StrangerEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.12

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
        self.register_story_choice(
            choice_flag="stranger_helped",
            moral_delta=8,
            consequences=[
                {
                    "consequence_id": "stranger_help_village_gift",
                    "effect_key": "villagers_gift",
                    "chance": 0.32,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER"],
                    "trigger_monsters": ["土匪", "狼人", "野狼", "小哥布林"],
                    "payload": {"hint": "旧日善意", "message": "你救下的人来自这个族群，对方主动献上宝物。"},
                },
                {
                    "consequence_id": "stranger_help_thief_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.26,
                    "priority": 7,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.2,
                        "atk_ratio": 1.2,
                        "message": "你救人时得罪了打手，他们提前布好了伏击。",
                    },
                },
            ],
        )
        if p.gold >= 10:
            p.gold -= 10
            # 70% Reward, 30% Betrayal
            if random.random() < 0.7:
                self.add_message("你花费10金币为陌生人包扎。")
                item = create_random_item()
                self.add_message(f"陌生人感激地给了你 {item.name} 作为回报！")
                item.acquire(player=p)
            else:
                dmg = 15
                p.take_damage(dmg)
                self.add_message("你刚为他包扎好，他突然拔刀刺向你！")
                self.add_message(f"这个忘恩负义的家伙抢了你的钱就跑了。受到 {dmg} 点伤害。")
        else:
            self.add_message("你囊中羞涩，无法提供帮助，只能遗憾离开。")
        return "Event Completed"

    def rob_stranger(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="stranger_robbed",
            moral_delta=-10,
            consequences=[
                {
                    "consequence_id": "stranger_rob_black_market_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.34,
                    "priority": 7,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.72, "message": "因你之前抢劫过陌生人，黑市商人认出你的“手法”，给了同路折扣。"},
                },
                {
                    "consequence_id": "stranger_rob_bounty_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.33,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.28,
                        "atk_ratio": 1.18,
                        "message": "你抢劫陌生人的恶行传开，赏金猎人带着怪物来堵你。",
                    },
                },
            ],
        )
        # 60% Success, 40% Fail
        if random.random() < 0.6:
            gold = random.randint(5, 20)
            p.gold += gold
            self.add_message(f"你抢走了陌生人仅剩的 {gold} 金币。你的良心受到了一点谴责。")
        else:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"陌生人突然暴起反击！你受到 {dmg} 点伤害，狼狈逃跑。")
        return "Event Completed"

    def ignore_stranger(self):
        self.register_story_choice(
            choice_flag="stranger_ignored",
            moral_delta=-3,
            consequences=[
                {
                    "consequence_id": "stranger_ignore_guilt_curse",
                    "effect_key": "shrine_curse",
                    "chance": 0.22,
                    "trigger_door_types": ["TRAP", "EVENT"],
                    "payload": {"duration": 1, "message": "因你之前无视了受伤的陌生人，隐约想起那个眼神，动作开始迟滞。"},
                }
            ],
        )
        self.add_message("你冷漠地走开了，不想惹麻烦。")
        return "Event Completed"


# 2. Smuggler
class SmugglerEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.1

    @classmethod
    def get_trigger_probability(cls, controller):
        round_bonus = min(0.1, max(0, getattr(controller, "round_count", 0)) * 0.004)
        rich_bonus = 0.03 if getattr(controller.player, "gold", 0) >= 60 else 0.0
        return min(0.26, cls.TRIGGER_BASE_PROBABILITY + round_bonus + rich_bonus)

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
        self.register_story_choice(
            choice_flag="smuggler_bought_goods",
            moral_delta=-5,
            consequences=[
                {
                    "consequence_id": "smuggler_buy_friend_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.4,
                    "priority": 8,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.65,
                        "message": [
                            "你随口报了个假货编号，掌柜脸色一变，立刻把价格改成了“自己人价”。",
                            "柜台下那本黑账里刚好有你见过的记号，商人什么都没问就给你打了折。",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "smuggler_buy_discount_aftertaste",
                                "effect_key": "black_market_markup",
                                "chance": 0.26,
                                "trigger_door_types": ["SHOP"],
                                "required_flags": ["choice:smuggler_bought_goods"],
                                "payload": {
                                    "ratio": 1.18,
                                    "message": "第二次再去时，对方笑着说：'折扣是入场券，不是终身会员。'",
                                },
                            }
                        ],
                    },
                },
                {
                    "consequence_id": "smuggler_buy_counterfeit_penalty",
                    "effect_key": "black_market_markup",
                    "chance": 0.28,
                    "priority": 6,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.35, "message": "因你之前向走私犯买过货，你买赃物的事被盯上，后续商人趁机抬价。"},
                },
            ],
        )
        if p.gold >= self.cost:
            p.gold -= self.cost
            # 80% Real, 20% Fake
            if random.random() < 0.8:
                self.item.acquire(player=p)
                self.add_message(f"你以 {self.cost}G 的低价买到了 {self.item.name}！")
            else:
                self.add_message("你付了钱，打开包裹一看——里面是一块石头！走私犯早就没影了。")
        else:
            self.add_message("走私犯翻了个白眼：'没钱就滚！'")
        return "Event Completed"

    def report_smuggler(self):
        self.register_story_choice(
            choice_flag="smuggler_reported",
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "smuggler_report_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.35,
                    "priority": 7,
                    "trigger_door_types": ["SHOP", "EVENT", "REWARD"],
                    "payload": {
                        "gold": random.randint(25, 55),
                        "message": [
                            "因你之前举报了走私犯，巡逻队长把一袋赏金塞给你，还嘱咐你下次别单独逞强。",
                            "因你之前举报了走私犯，卫兵把查扣赃款按功劳分了你一份。",
                        ],
                    },
                },
                {
                    "consequence_id": "smuggler_report_gang_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.32,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.3,
                        "atk_ratio": 1.2,
                        "message": [
                            "因你之前举报了走私犯，巷口有人喊“线人就是他”，下一秒伏击就从阴影里扑了出来。",
                            "因你之前举报了走私犯，走私团伙没来找你讲道理，直接把怪物引到了你必经的门后。",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "smuggler_report_aftershock",
                                "effect_key": "black_market_markup",
                                "chance": 0.35,
                                "trigger_door_types": ["SHOP"],
                                "required_flags": ["consumed:smuggler_report_gang_revenge"],
                                "payload": {
                                    "ratio": 1.25,
                                    "message": "因你举报了走私犯，在黑市被认出来后，摊主们统一改了“举报者价”。",
                                },
                            }
                        ],
                    },
                },
            ],
        )
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
        self.register_story_choice(choice_flag="smuggler_left", moral_delta=0)
        self.add_message("你摇摇头，转身离开了。")
        return "Event Completed"


# 3. Ancient Shrine
class AncientShrineEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.1

    @classmethod
    def get_trigger_probability(cls, controller):
        p = getattr(controller, "player", None)
        if not p:
            return cls.TRIGGER_BASE_PROBABILITY
        hp_cap = max(1, getattr(p, "hp", 1))
        # 以初始生命 100 作为参考上限，低血时更容易触发祭坛事件
        hp_rate = p.hp / max(100, hp_cap)
        return min(0.25, cls.TRIGGER_BASE_PROBABILITY + (0.12 if hp_rate < 0.5 else 0.0))

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
        self.register_story_choice(
            choice_flag="shrine_prayed",
            moral_delta=4,
            consequences=[
                {
                    "consequence_id": "shrine_pray_bless",
                    "effect_key": "shrine_blessing",
                    "chance": 0.34,
                    "priority": 7,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {"message": "因你曾在祭坛虔诚祈祷，神圣余辉在关键时刻生效。"},
                },
                {
                    "consequence_id": "shrine_pray_fanatic_hunt",
                    "effect_key": "revenge_ambush",
                    "chance": 0.22,
                    "priority": 6,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"hp_ratio": 1.18, "atk_ratio": 1.15, "message": "因你曾在祭坛虔诚祈祷，附近的狂信徒误会了你的意图，设下埋伏。"},
                },
            ],
        )
        # 70% Heal, 30% Curse
        if random.random() < 0.7:
            healed = p.heal(50) 
            self.add_message(f"一道温暖的光芒笼罩着你，你的伤势恢复了 {healed} 点！")
        else:
            duration = 3
            p.apply_status(StatusName.WEAK.create_instance(duration=duration, target=p))
            self.add_message(f"祭坛突然喷出一股黑气！你被诅咒了，进入虚弱状态 {duration} 回合。")
        return "Event Completed"

    def desecrate(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="shrine_desecrated",
            moral_delta=-9,
            consequences=[
                {
                    "consequence_id": "shrine_desecrate_curse",
                    "effect_key": "shrine_curse",
                    "chance": 0.45,
                    "priority": 8,
                    "trigger_door_types": ["TRAP", "MONSTER", "EVENT"],
                    "payload": {"duration": 2, "message": "你破坏祭坛的行为引来持续诅咒。"},
                },
                {
                    "consequence_id": "shrine_desecrate_looter_bonus",
                    "effect_key": "guard_reward",
                    "chance": 0.26,
                    "priority": 5,
                    "trigger_door_types": ["REWARD", "SHOP"],
                    "payload": {"gold": random.randint(20, 40), "message": "你记住了祭坛藏宝手法，顺手又捞到一笔。"},
                },
            ],
        )
        gold = random.randint(50, 100)
        p.gold += gold
        self.add_message(f"你在祭坛下挖出了 {gold} 金币！")
        if random.random() < 0.5:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"但这触怒了神灵，一道闪电劈中了你！受到 {dmg} 点伤害。")
        return "Event Completed"

    def inspect(self):
        self.register_story_choice(
            choice_flag="shrine_inspected",
            moral_delta=1,
            consequences=[
                {
                    "consequence_id": "shrine_inspect_training",
                    "effect_key": "atk_training",
                    "chance": 0.2,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"delta": 1, "message": "因你调查过祭坛符文，符文学识让你看穿敌人破绽，攻击微幅提升。"},
                }
            ],
        )
        if random.random() < 0.7:
             self.add_message("你在祭坛后面发现了一个遗落的包裹...")
             item = create_random_item()
             self.add_message(f"里面有 {item.name}！")
             item.acquire(player=self.get_player())
        else:
             self.add_message("你研究了半天，除了一些灰尘什么也没发现。")
        return "Event Completed"

# 4. Gambler Event
class GamblerEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.08

    @classmethod
    def get_trigger_probability(cls, controller):
        gold = max(0, getattr(controller.player, "gold", 0))
        return min(0.22, cls.TRIGGER_BASE_PROBABILITY + min(0.14, gold / 1000))

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
        self.register_story_choice(
            choice_flag="gambler_high_stakes",
            moral_delta=-2,
            consequences=[
                {
                    "consequence_id": "gambler_high_debtor_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.31,
                    "priority": 7,
                    "trigger_door_types": ["MONSTER"],
                    "payload": {"hp_ratio": 1.23, "atk_ratio": 1.2, "message": "赌局输家雇了打手，你被截杀。"},
                },
                {
                    "consequence_id": "gambler_high_hot_hand_bonus",
                    "effect_key": "guard_reward",
                    "chance": 0.28,
                    "priority": 6,
                    "trigger_door_types": ["REWARD", "SHOP"],
                    "payload": {"gold": random.randint(25, 55), "message": "因你之前在赌局上手气正旺，后续交易也有额外进账。"},
                },
            ],
        )
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
        self.register_story_choice(
            choice_flag="gambler_low_stakes",
            moral_delta=-1,
            consequences=[
                {
                    "consequence_id": "gambler_low_small_revenge",
                    "effect_key": "lose_gold",
                    "chance": 0.2,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": random.randint(10, 20), "message": "因你之前小玩了一把，被赌徒顺走了点钱，事后才发现。"},
                },
                {
                    "consequence_id": "gambler_low_lucky_tip",
                    "effect_key": "black_market_discount",
                    "chance": 0.22,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.82, "message": "因你之前小玩了一把，赌徒给你的小道消息让你捡了便宜。"},
                },
            ],
        )
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
        self.register_story_choice(
            choice_flag="gambler_declined",
            moral_delta=2,
            consequences=[
                {
                    "consequence_id": "gambler_decline_prudent_bless",
                    "effect_key": "shrine_blessing",
                    "chance": 0.25,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {"message": "克制欲望带来的专注，让你更容易避开危险。"},
                },
                {
                    "consequence_id": "gambler_decline_mocked_markup",
                    "effect_key": "black_market_markup",
                    "chance": 0.15,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.2, "message": "你拒绝赌局得罪了地头蛇，熟人商店也不给你好脸色。"},
                },
            ],
        )
        self.add_message("你拒绝了赌博，赌徒无趣地走开了。")
        return "Event Completed"


# 5. Lost Child Event
class LostChildEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.11

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
        self.register_story_choice(
            choice_flag="lost_child_guided_home",
            moral_delta=10,
            consequences=[
                {
                    "consequence_id": "lost_child_village_gift",
                    "effect_key": "villagers_gift",
                    "chance": 0.38,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER"],
                    "trigger_monsters": ["土匪", "狼人", "野狼", "食人魔"],
                    "payload": {
                        "hint": "小女孩的谢礼",
                        "message": [
                            "你正要拔剑，对方却把武器倒插在地上：'你救过我们村的小孩，这仗不打。'",
                            "怪物没冲上来，反而递来一个包裹：'欠你的，不是命，是人情。'",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "lost_child_village_scout_tip",
                                "effect_key": "atk_training",
                                "chance": 0.28,
                                "trigger_door_types": ["MONSTER", "EVENT"],
                                "required_flags": ["choice:lost_child_guided_home"],
                                "payload": {
                                    "delta": 1,
                                    "message": "村里的猎人后来给你演示了两招，出手更稳了。",
                                },
                            }
                        ],
                    },
                },
                {
                    "consequence_id": "lost_child_fame_backfire",
                    "effect_key": "revenge_ambush",
                    "chance": 0.27,
                    "priority": 7,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.2,
                        "atk_ratio": 1.18,
                        "message": [
                            "“专挑好人下手”不是笑话——赏金猎人把你当成了最值钱的目标。",
                            "你的名声救过人，也暴露了行踪；埋伏的人比感谢你的人先到。",
                        ],
                    },
                },
            ],
        )
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
        self.register_story_choice(
            choice_flag="lost_child_gave_gold",
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "lost_child_give_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.3,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"gold": random.randint(15, 35), "heal": 5, "message": "因你之前资助了迷路的孩子，这事被传开后，路人对你伸出了援手。"},
                },
                {
                    "consequence_id": "lost_child_give_pickpocket",
                    "effect_key": "lose_gold",
                    "chance": 0.23,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": random.randint(12, 28), "message": "因你之前资助孩子时出手阔绰，被人盯上后顺走了一笔钱。"},
                },
            ],
        )
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
        self.register_story_choice(
            choice_flag="lost_child_ignored",
            moral_delta=-8,
            consequences=[
                {
                    "consequence_id": "lost_child_ignore_curse",
                    "effect_key": "shrine_curse",
                    "chance": 0.33,
                    "trigger_door_types": ["TRAP", "MONSTER", "EVENT"],
                    "payload": {"duration": 2, "message": "因你之前无视了迷路的孩子，心底的不安挥之不去，战斗时更易露出破绽。"},
                },
                {
                    "consequence_id": "lost_child_ignore_black_market",
                    "effect_key": "black_market_discount",
                    "chance": 0.25,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.78, "message": "因你之前冷酷地无视了迷路的孩子，地下商人觉得你“够狠”，愿意给折扣。"},
                },
            ],
        )
        self.add_message("这里是残酷的世界，你选择了无视。")
        return "Event Completed"


# 6. Cursed Chest
class CursedChestEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.09

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
        self.register_story_choice(
            choice_flag="cursed_chest_opened",
            moral_delta=-4,
            consequences=[
                {
                    "consequence_id": "chest_open_curse_follow",
                    "effect_key": "shrine_curse",
                    "chance": 0.36,
                    "trigger_door_types": ["MONSTER", "TRAP", "EVENT"],
                    "payload": {"duration": 2, "message": "贪婪的回响仍缠着你，诅咒持续发作。"},
                },
                {
                    "consequence_id": "chest_open_rogue_profit",
                    "effect_key": "black_market_discount",
                    "chance": 0.24,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.8, "message": "你敢开诅咒箱的名声传到黑市，商人愿和你做“高风险生意”。"},
                },
            ],
        )
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
        self.register_story_choice(
            choice_flag="cursed_chest_purified",
            moral_delta=5,
            consequences=[
                {
                    "consequence_id": "chest_purify_blessing",
                    "effect_key": "shrine_blessing",
                    "chance": 0.32,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {"message": "你净化诅咒后的灵力在下一次危险中保护了你。"},
                },
                {
                    "consequence_id": "chest_purify_cult_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.22,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"hp_ratio": 1.18, "atk_ratio": 1.16, "message": "因你之前净化了诅咒宝箱，崇拜它的邪教徒盯上了你。"},
                },
            ],
        )
        # Assume successful purify for now, or random
        if random.random() < 0.5:
            gold = 50
            self.get_player().gold += gold
            self.add_message(f"你成功净化了诅咒，箱子里只剩下一些普通的财宝 ({gold}G)。")
        else:
            self.add_message("你的净化失败了，箱子消失在虚空中。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag="cursed_chest_left", moral_delta=1)
        self.add_message("你明智地远离了诅咒之物。")
        return "Event Completed"


# 7. Wise Sage
class WiseSageEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.09

    @classmethod
    def get_trigger_probability(cls, controller):
        round_count = max(0, getattr(controller, "round_count", 0))
        return min(0.2, cls.TRIGGER_BASE_PROBABILITY + min(0.11, round_count * 0.005))

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
        self.register_story_choice(
            choice_flag="sage_power_choice",
            moral_delta=-1,
            consequences=[
                {
                    "consequence_id": "sage_power_training",
                    "effect_key": "atk_training",
                    "chance": 0.3,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"delta": 2, "message": "老者的教诲回响在你脑海，出手更加凌厉。"},
                },
                {
                    "consequence_id": "sage_power_backlash",
                    "effect_key": "shrine_curse",
                    "chance": 0.22,
                    "trigger_door_types": ["MONSTER", "TRAP"],
                    "payload": {"duration": 2, "message": "你对力量的执念引发反噬，行动变得沉重。"},
                },
            ],
        )
        if random.random() < 0.7:
            self.add_message("老者点了点头：'力量是双刃剑。'")
            p.change_base_atk(3)
        else:
            duration = 3
            p.apply_status(StatusName.WEAK.create_instance(duration=duration, target=p))
            self.add_message(f"老者摇头：'你渴望力量，却被力量吞噬。' 你变得虚弱了 ({duration}回合)。")
        return "Event Completed"

    def wealth(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="sage_wealth_choice",
            moral_delta=-3,
            consequences=[
                {
                    "consequence_id": "sage_wealth_windfall",
                    "effect_key": "guard_reward",
                    "chance": 0.28,
                    "trigger_door_types": ["SHOP", "REWARD", "EVENT"],
                    "payload": {"gold": random.randint(30, 70), "message": "因你在老者处选了财富，嗅到机会后顺手又赚了一笔。"},
                },
                {
                    "consequence_id": "sage_wealth_fine",
                    "effect_key": "lose_gold",
                    "chance": 0.3,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": random.randint(20, 50), "message": "因你在老者处选了财富，逐利行为引来盘查，被罚了一笔钱。"},
                },
            ],
        )
        if random.random() < 0.7:
            gold = 200
            p.gold += gold
            self.add_message(f"老者叹了口气：'身外之物。' 他丢给你 {gold} 金币后消失了。")
        else:
            lost = min(p.gold, 50)
            p.gold -= lost
            self.add_message(f"老者手一挥，你口袋里的 {lost} 金币变成了石头。'贪婪是原罪。'")
        return "Event Completed"

    def health(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="sage_health_choice",
            moral_delta=4,
            consequences=[
                {
                    "consequence_id": "sage_health_guard_help",
                    "effect_key": "guard_reward",
                    "chance": 0.27,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"gold": random.randint(10, 30), "heal": 8, "message": "因你在老者处选了生存，重视生存的态度感染了路人，获得援助。"},
                },
                {
                    "consequence_id": "sage_health_dependency",
                    "effect_key": "black_market_markup",
                    "chance": 0.2,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.25, "message": "因你在老者处选了生存，显得过于求稳，被商人看穿后趁机抬价。"},
                },
            ],
        )
        if random.random() < 0.7:
            p.heal(50)
            self.add_message("老者微笑道：'活着就有希望。' 你的生命值恢复了 50 点。")
        else:
            duration = 3
            p.apply_status(StatusName.FIELD_POISON.create_instance(duration=duration, target=p))
            self.add_message(f"老者给你喝了一杯水，你却感到腹痛。'不仅是身体，心灵也需净化。' 你中毒了 ({duration}回合)。")
        return "Event Completed"


class RefugeeCaravanEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.08

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Refugee Caravan"
        self.description = "一支逃难车队拦住了你，他们请求食物与路费。"
        self.choices = [
            EventChoice("捐助 25G", self.donate),
            EventChoice("索要保护费", self.extort),
            EventChoice("假装没看见", self.walk_away),
        ]

    def donate(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="caravan_donated",
            moral_delta=7,
            consequences=[
                {
                    "consequence_id": "caravan_donate_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.35,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.7, "message": "因你之前捐助了逃难车队，车队里有人是商会亲属，后续商店给你打了折。"},
                },
                {
                    "consequence_id": "caravan_donate_bandit_envy",
                    "effect_key": "revenge_ambush",
                    "chance": 0.24,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"hp_ratio": 1.2, "atk_ratio": 1.16, "message": "你帮助难民的事惹怒了劫匪，他们要拿你开刀。"},
                },
            ],
        )
        if p.gold >= 25:
            p.gold -= 25
            self.add_message("你捐出了 25 金币，车队成员向你致谢。")
        else:
            self.add_message("你想捐助，但钱不够。")
        return "Event Completed"

    def extort(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="caravan_extorted",
            moral_delta=-9,
            consequences=[
                {
                    "consequence_id": "caravan_extort_markup",
                    "effect_key": "black_market_markup",
                    "chance": 0.38,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.35, "message": "商会知道你勒索车队后，把你列入高风险名单。"},
                },
                {
                    "consequence_id": "caravan_extort_black_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.27,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.75,
                        "message": [
                            "你的恶名先你一步到了黑市，摊主把价格写低了，语气却更客气了。",
                            "掌柜把算盘往你这边一推：'我们欣赏效率，尤其是你那种。'",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "caravan_extort_enforcer_test",
                                "effect_key": "revenge_ambush",
                                "chance": 0.24,
                                "trigger_door_types": ["MONSTER", "EVENT"],
                                "required_flags": ["choice:caravan_extorted"],
                                "payload": {
                                    "hp_ratio": 1.18,
                                    "atk_ratio": 1.15,
                                    "message": "地下行会想“试试你够不够狠”，于是派人来探底。",
                                },
                            }
                        ],
                    },
                },
            ],
        )
        gain = random.randint(20, 45)
        p.gold += gain
        self.add_message(f"你恐吓了车队，抢到 {gain} 金币。")
        return "Event Completed"

    def walk_away(self):
        self.register_story_choice(choice_flag="caravan_ignored", moral_delta=-2)
        self.add_message("你低头赶路，不愿卷入是非。")
        return "Event Completed"


class FallenKnightEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.08

    @classmethod
    def get_trigger_probability(cls, controller):
        round_count = getattr(controller, "round_count", 0)
        return min(0.18, cls.TRIGGER_BASE_PROBABILITY + (0.05 if round_count >= 12 else 0.0))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Fallen Knight"
        self.description = "一名重伤骑士倒在路边，盔甲上有王国徽记。"
        self.choices = [
            EventChoice("救治骑士", self.aid_knight),
            EventChoice("搜刮装备", self.loot_knight),
            EventChoice("谨慎离开", self.leave),
        ]

    def aid_knight(self):
        self.register_story_choice(
            choice_flag="knight_aided",
            moral_delta=8,
            consequences=[
                {
                    "consequence_id": "knight_aid_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.36,
                    "trigger_door_types": ["EVENT", "SHOP", "REWARD"],
                    "payload": {"gold": random.randint(20, 50), "heal": 10, "message": "因你之前救治了骑士，王国巡逻队认出你的善举，给予补给。"},
                },
                {
                    "consequence_id": "knight_aid_traitor_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.23,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.2,
                        "atk_ratio": 1.18,
                        "hunter_name": "暗影刺客",
                        "message": "因你救治了骑士，追杀他的叛徒盯上了你。",
                    },
                },
            ],
        )
        healed = self.get_player().heal(15)
        self.add_message(f"你为骑士包扎，自己也振作起来，恢复了 {healed} 生命。")
        return "Event Completed"

    def loot_knight(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="knight_looted",
            moral_delta=-10,
            consequences=[
                {
                    "consequence_id": "knight_loot_bounty",
                    "effect_key": "lose_gold",
                    "chance": 0.34,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"amount": random.randint(20, 40), "message": "你洗劫骑士的事被追责，花钱才摆平。"},
                },
                {
                    "consequence_id": "knight_loot_underworld_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.29,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.74,
                        "message": [
                            "你拿出的徽记还带着血渍，黑市商人却只问了一句：'整套还是散卖？'",
                            "对方认出那是军械制式，压低声音说：'这种货，今天我给你高价低税。'",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "knight_loot_witness",
                                "effect_key": "lose_gold",
                                "chance": 0.26,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "required_flags": ["choice:knight_looted"],
                                "payload": {
                                    "amount": random.randint(15, 35),
                                    "message": "有人认出了那套装备，你花钱才堵住了对方的嘴。",
                                },
                            }
                        ],
                    },
                },
            ],
        )
        gain = random.randint(25, 55)
        p.gold += gain
        self.add_message(f"你扒下骑士身上的值钱物件，获得 {gain} 金币。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag="knight_left", moral_delta=0)
        self.add_message("你不确定这是陷阱，选择绕开。")
        return "Event Completed"


class TimePawnshopEvent(Event):
    """新事件：时间当铺"""
    TRIGGER_BASE_PROBABILITY = 0.07

    @classmethod
    def get_trigger_probability(cls, controller):
        round_count = max(0, getattr(controller, "round_count", 0))
        return min(0.16, cls.TRIGGER_BASE_PROBABILITY + min(0.09, round_count * 0.004))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Time Pawnshop"
        self.description = "巷口出现一家只在黄昏开门的当铺，掌柜说：'我们收今天，押明天。'"
        self.choices = [
            EventChoice("抵押明天，立刻拿钱", self.pawn_tomorrow),
            EventChoice("赎回旧债，清掉利息", self.redeem_debt),
            EventChoice("砸碎沙漏柜台", self.break_hourglass),
        ]

    def pawn_tomorrow(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="time_pawned_future",
            moral_delta=-3,
            consequences=[
                {
                    "consequence_id": "time_pawn_quick_cash",
                    "effect_key": "guard_reward",
                    "chance": 1.0,
                    "priority": 9,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {
                        "gold": 30,
                        "message": "前情：你把明天的份额押给了时间当铺。掌柜按约给了你一袋现钱。",
                        "chain_followups": [
                            {
                                "consequence_id": "time_pawn_interest_collection",
                                "effect_key": "lose_gold",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "payload": {
                                    "amount": 24,
                                    "message": "前情：你之前抵押了明天。利息到期后，当铺伙计追上来从你身上划走了一笔。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        gain = 28
        p.gold += gain
        self.add_message(f"你在契约上按下手印，先拿到 {gain}G。掌柜提醒你：'到期我们自己来取。'")
        return "Event Completed"

    def redeem_debt(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="time_redeemed_debt",
            moral_delta=4,
            consequences=[
                {
                    "consequence_id": "time_redeem_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.34,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.78,
                        "message": "前情：你在时间当铺主动结清旧债。商人把你标记为守约客户，愿意给你折扣。",
                    },
                },
                {
                    "consequence_id": "time_redeem_focus_training",
                    "effect_key": "atk_training",
                    "chance": 0.26,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "delta": 1,
                        "message": "前情：你赎回了欠下的时间。你的节奏重新稳定，出手更果断了。",
                    },
                },
            ],
        )
        fee = 20
        if p.gold >= fee:
            p.gold -= fee
            healed = p.heal(10)
            self.add_message(f"你付了 {fee}G 利息，账本上你的名字被划掉，恢复了 {healed} 点生命。")
        else:
            self.add_message("你想赎债，但钱不够。掌柜把账页翻到下一行，笑而不语。")
        return "Event Completed"

    def break_hourglass(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="time_broke_hourglass",
            moral_delta=-7,
            consequences=[
                {
                    "consequence_id": "time_break_hunter",
                    "effect_key": "revenge_ambush",
                    "chance": 1.0,
                    "priority": 10,
                    "trigger_door_types": ["EVENT", "MONSTER"],
                    "payload": {
                        "force_hunter": True,
                        "hunter_name": "暗影刺客",
                        "consume_on_defeat": True,
                        "message": "前情：你砸了时间当铺的沙漏。清算人沿着碎砂的痕迹追了上来。",
                        "hunter_hint": "前情：你破坏了当铺契约。门后有清算人在等你。",
                    },
                },
                {
                    "consequence_id": "time_break_reward_confiscated",
                    "effect_key": "treasure_vanish",
                    "chance": 0.45,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "fake_gold": 8,
                        "message": "前情：你砸柜台后被全行记名。宝物门已被提前冻结，只剩手续找零。",
                    },
                },
            ],
        )
        loot = random.randint(18, 35)
        p.gold += loot
        self.add_message(f"你踢碎沙漏柜台抢出 {loot}G。墙上的钟同时停了一秒。")
        return "Event Completed"


class MirrorTheaterEvent(Event):
    """新事件：镜剧场"""
    TRIGGER_BASE_PROBABILITY = 0.07

    @classmethod
    def get_trigger_probability(cls, controller):
        moral = abs(getattr(getattr(controller, "story", None), "moral_score", 0))
        return min(0.17, cls.TRIGGER_BASE_PROBABILITY + min(0.1, moral / 600))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Mirror Theater"
        self.description = "废墟里有一座镜面剧场，导演递来三张面具：英雄、恶徒、或观众。"
        self.choices = [
            EventChoice("戴上英雄面具", self.play_hero),
            EventChoice("戴上恶徒面具", self.play_villain),
            EventChoice("撕掉剧本离场", self.tear_script),
        ]

    def play_hero(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="mirror_played_hero",
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "mirror_hero_support",
                    "effect_key": "guard_reward",
                    "chance": 0.34,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {
                        "gold": random.randint(18, 36),
                        "heal": 8,
                        "message": "前情：你在镜剧场演了英雄。后续路人愿意给你补给和消息。",
                    },
                },
                {
                    "consequence_id": "mirror_hero_bless",
                    "effect_key": "shrine_blessing",
                    "chance": 0.28,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {
                        "message": "前情：你选择了英雄剧本。临门一脚时，那份信念帮你压住了危险。",
                    },
                },
            ],
        )
        healed = p.heal(12)
        self.add_message(f"掌声从空剧场里响起，你从角色里抽离时恢复了 {healed} 点生命。")
        return "Event Completed"

    def play_villain(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="mirror_played_villain",
            moral_delta=-6,
            consequences=[
                {
                    "consequence_id": "mirror_villain_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.3,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.74,
                        "message": "前情：你在镜剧场演了恶徒。黑市把你当成同类，先给了交易甜头。",
                    },
                },
                {
                    "consequence_id": "mirror_villain_hunt",
                    "effect_key": "revenge_ambush",
                    "chance": 0.32,
                    "trigger_door_types": ["EVENT", "MONSTER"],
                    "payload": {
                        "force_hunter": True,
                        "hunter_name": "冥界使者",
                        "message": "前情：你在舞台上选了恶徒结局。想要你人头的人很快循着剧评找到了你。",
                    },
                },
            ],
        )
        gain = random.randint(22, 42)
        p.gold += gain
        self.add_message(f"导演把反派分成递给你，你拿到 {gain}G。谢幕时你听见观众席有人记下了你的脸。")
        return "Event Completed"

    def tear_script(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="mirror_tore_script",
            moral_delta=0,
            consequences=[
                {
                    "consequence_id": "mirror_script_force_echo_court",
                    "effect_key": "force_story_event",
                    "chance": 1.0,
                    "priority": 9,
                    "trigger_door_types": ["EVENT"],
                    "payload": {
                        "event_key": "echo_court_event",
                        "hint": "前情：你撕了镜剧场剧本，回声法庭要你解释",
                        "message": "前情：你拒绝在镜剧场扮演任何角色。下一扇事件门被改写成回声法庭。",
                    },
                },
                {
                    "consequence_id": "mirror_script_aftershock",
                    "effect_key": "shrine_curse",
                    "chance": 0.25,
                    "trigger_door_types": ["MONSTER", "TRAP", "EVENT"],
                    "payload": {
                        "duration": 1,
                        "message": "前情：你撕碎剧本后强行离场。余震般的回声让你短暂失衡。",
                    },
                },
            ],
        )
        if random.random() < 0.6:
            item = create_random_item()
            item.acquire(player=p)
            self.add_message(f"你把剧本撕成碎片，幕后人竟鼓掌离席，留下了 {item.name}。")
        else:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"你撕剧本时镜面反噬，碎光割伤了你，受到 {dmg} 点伤害。")
        return "Event Completed"


class MoonBountyEvent(Event):
    """长链1：月蚀通缉令"""
    TRIGGER_BASE_PROBABILITY = 0.07

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Moon Bounty"
        self.description = "你在墙上看到一张会发光的通缉令：'月蚀前带回叛徒，生死不论。'"
        self.choices = [
            EventChoice("接单追猎", self.accept_contract),
            EventChoice("暗中护送叛徒", self.protect_target),
            EventChoice("两头通吃，伪造线索", self.double_cross),
        ]

    def accept_contract(self):
        self.register_story_choice(
            choice_flag="moon_bounty_accept",
            moral_delta=-4,
            consequences=self._build_moon_chain(
                route="accept",
                shop_effect="black_market_discount",
                shop_ratio=0.74,
                hunter_name="野狼",
                shop_message="你拿出的通缉印章被商人认出，货架立刻给出猎手折扣。",
            ),
        )
        p = self.get_player()
        prep_cost = min(p.gold, 8)
        p.gold -= prep_cost
        if prep_cost > 0:
            self.add_message(f"你先花了 {prep_cost}G 买线人情报，把通缉令折进袖口。有人在暗处轻轻点头，像是在确认你的身份。")
        else:
            self.add_message("你把通缉令折进袖口，但没钱买情报，只能硬着头皮追猎。")
        return "Event Completed"

    def protect_target(self):
        self.register_story_choice(
            choice_flag="moon_bounty_protect",
            moral_delta=6,
            consequences=self._build_moon_chain(
                route="protect",
                shop_effect="black_market_markup",
                shop_ratio=1.32,
                hunter_name="死亡骑士",
                shop_message="你坏了悬赏行会的规矩，商人把你列成高风险客户。",
            ),
        )
        healed = self.get_player().heal(10)
        self.add_message(f"你把通缉令撕成两半，护送行动让你重整呼吸，恢复 {healed} 点生命。风里传来一句低语：'那你就替他付账。'")
        return "Event Completed"

    def double_cross(self):
        self.register_story_choice(
            choice_flag="moon_bounty_double",
            moral_delta=-1,
            consequences=self._build_moon_chain(
                route="double",
                shop_effect="black_market_discount",
                shop_ratio=0.82,
                hunter_name="暗影刺客",
                shop_message="你放出的假线索搅乱了盘口，黑市一时分不清该杀你还是拉拢你。",
            ),
        )
        p = self.get_player()
        p.gold += 18
        p.take_damage(6)
        self.add_message("你把真假线索分别卖给两边，先赚到 18G；但双方都在试探你，你在撤离时受了 6 点伤害。")
        return "Event Completed"

    def _build_moon_chain(self, route, shop_effect, shop_ratio, hunter_name, shop_message):
        return [
            {
                "consequence_id": f"moon_chain_{route}_hunter",
                "effect_key": "revenge_ambush",
                "chance": 1.0,
                "priority": 10,
                "trigger_door_types": ["EVENT", "MONSTER"],
                "payload": {
                    "force_hunter": True,
                    "consume_on_defeat": True,
                    "hunter_name": hunter_name,
                    "message": "前情：你刚在月蚀通缉令里做了站队选择。你刚迈过门槛，追猎令就被激活了，脚步声在你背后同步响起。",
                    "hunter_hint": "前情：你的月蚀选择已被记档。猎杀钟摆开始摆动，你被迫跟着它的节奏走。",
                    "chain_followups": [
                        {
                            "consequence_id": f"moon_chain_{route}_shop",
                            "effect_key": shop_effect,
                            "chance": 1.0,
                            "trigger_door_types": ["SHOP"],
                            "payload": {
                                "ratio": shop_ratio,
                                "message": shop_message,
                                "chain_followups": [
                                    {
                                        "consequence_id": f"moon_chain_{route}_force_verdict",
                                        "effect_key": "force_story_event",
                                        "chance": 1.0,
                                        "trigger_door_types": ["EVENT"],
                                        "payload": {
                                            "event_key": "moon_verdict_event",
                                            "hint": "前情：你已经历追猎与黑市结算，审判庭在等你签最后一笔账",
                                            "message": "前情：你的通缉案已进入结算阶段。你发现一扇门后坐着记账人：'该结案了。'",
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                },
            }
        ]


class MoonVerdictEvent(Event):
    """月蚀链中继：决定宝物门与后续余波。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Moon Verdict"
        self.description = "你在月蚀通缉链里一路追到这里，审判席上的书记官推来三份结案文书，每一份都要你签名。"
        self.choices = [
            EventChoice("按规矩结案", self.file_clean),
            EventChoice("销毁证物", self.burn_records),
            EventChoice("反向勒索审判庭", self.extort_court),
        ]

    def file_clean(self):
        self.register_story_choice(
            choice_flag="moon_verdict_clean",
            moral_delta=4,
            consequences=[
                {
                    "consequence_id": "moon_verdict_clean_treasure",
                    "effect_key": "treasure_marked_item",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "item_key": "revive_scroll",
                        "gold_bonus": 35,
                        "message": "前情：你在审判庭按规矩签字结案。你打开宝物门时，最上层放着盖过公章的复活卷轴。",
                        "chain_followups": [
                            {
                                "consequence_id": "moon_verdict_clean_aftercare",
                                "effect_key": "guard_reward",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "payload": {
                                    "gold": 25,
                                    "heal": 12,
                                    "message": "前情：你选择了规范结案并留档。审判庭没有再追责，甚至给了你一笔办案补贴。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        p = self.get_player()
        p.gold += 12
        healed = p.heal(6)
        self.add_message(f"你签了字。书记官把印泥按在卷轴边缘，先发了 12G 办案费，你也恢复了 {healed} 点生命。")
        return "Event Completed"

    def burn_records(self):
        self.register_story_choice(
            choice_flag="moon_verdict_burned",
            moral_delta=-5,
            consequences=[
                {
                    "consequence_id": "moon_verdict_burn_treasure_void",
                    "effect_key": "treasure_vanish",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "fake_gold": 9,
                        "message": "前情：你刚亲手焚毁了审判档案。你推开宝物门，只剩一张纸条：'证物已焚，奖励也一并焚毁。'",
                        "chain_followups": [
                            {
                                "consequence_id": "moon_verdict_burn_retribution",
                                "effect_key": "revenge_ambush",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "MONSTER"],
                                "payload": {
                                    "force_hunter": True,
                                    "hunter_name": "冥界使者",
                                    "hp_ratio": 1.16,
                                    "atk_ratio": 1.16,
                                    "message": "前情：你烧掉了关键卷宗并切断证据链。焚卷的烟味还没散，执法者已经追到门后。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        dmg = 12
        self.get_player().take_damage(dmg)
        self.add_message(f"火焰吞掉了档案，也吞掉了你的一部分退路。你在浓烟中受了 {dmg} 点伤害。")
        return "Event Completed"

    def extort_court(self):
        self.register_story_choice(
            choice_flag="moon_verdict_extorted",
            moral_delta=-2,
            consequences=[
                {
                    "consequence_id": "moon_verdict_extort_treasure",
                    "effect_key": "treasure_marked_item",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "item_key": "giant_scroll",
                        "keep_gold": False,
                        "message": "前情：你把结案谈判变成了勒索。宝物门里只留下一卷被红蜡封死的巨大卷轴。",
                        "chain_followups": [
                            {
                                "consequence_id": "moon_verdict_extort_tax",
                                "effect_key": "black_market_markup",
                                "chance": 1.0,
                                "trigger_door_types": ["SHOP"],
                                "payload": {
                                    "ratio": 1.28,
                                    "message": "前情：你勒索审判庭的传闻已经传开。商人都想先从你身上捞一层。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        gain = 22
        self.get_player().gold += gain
        self.add_message(f"你把谈判变成了敲诈，当场卷走 {gain}G。书记官笑得很轻，像记下了你的名字。")
        return "Event Completed"


class ClockworkBazaarEvent(Event):
    """长链2：齿轮黑市"""
    TRIGGER_BASE_PROBABILITY = 0.06

    @classmethod
    def get_trigger_probability(cls, controller):
        round_count = max(0, getattr(controller, "round_count", 0))
        return min(0.17, cls.TRIGGER_BASE_PROBABILITY + min(0.11, round_count * 0.004))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Clockwork Bazaar"
        self.description = "移动黑市停在岔路口，主持人说今天只收'会动的故事'。"
        self.choices = [
            EventChoice("校准摊位机械，换取信誉", self.calibrate),
            EventChoice("偷改优惠码", self.hack_coupon),
            EventChoice("破坏竞品摊位", self.sabotage),
        ]

    def calibrate(self):
        self.register_story_choice(
            choice_flag="clockwork_calibrated",
            moral_delta=5,
            consequences=self._build_clockwork_chain(
                route="calibrate",
                shop_effect="black_market_discount",
                ratio=0.68,
                hunter_name="食人魔",
                shop_message="机械账本认可了你的调校记录，后续商店对你亮起绿灯。",
            ),
        )
        tip = 12
        self.get_player().gold += tip
        self.add_message(f"你修好了计价机关，黑市主持人把一枚齿轮徽章别在你肩上，并付给你 {tip}G 调校费。")
        return "Event Completed"

    def hack_coupon(self):
        self.register_story_choice(
            choice_flag="clockwork_hacked",
            moral_delta=-6,
            consequences=self._build_clockwork_chain(
                route="hack",
                shop_effect="black_market_discount",
                ratio=0.8,
                hunter_name="狼人",
                shop_message="第一家店没识破你的优惠码，给了你离谱折扣。",
            ),
        )
        gain = 16
        self.get_player().gold += gain
        self.add_message(f"你改了校验齿轮，券码短暂有效，先白赚了 {gain}G。倒计时已经开始。")
        return "Event Completed"

    def sabotage(self):
        self.register_story_choice(
            choice_flag="clockwork_sabotaged",
            moral_delta=-8,
            consequences=self._build_clockwork_chain(
                route="sabotage",
                shop_effect="black_market_markup",
                ratio=1.35,
                hunter_name="死亡骑士",
                shop_message="你砸摊的录像被同步给全市场，几乎所有店都给你涨价。",
            ),
        )
        p = self.get_player()
        p.gold += 20
        p.take_damage(8)
        self.add_message("你踢翻了对面摊位，抢到 20G 材料费，但飞溅零件划伤了你，受到 8 点伤害。")
        return "Event Completed"

    def _build_clockwork_chain(self, route, shop_effect, ratio, hunter_name, shop_message):
        if route == "calibrate":
            return [
                {
                    "consequence_id": "clock_chain_calibrate_shop_open",
                    "effect_key": shop_effect,
                    "chance": 1.0,
                    "priority": 9,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": ratio,
                        "message": shop_message,
                        "chain_followups": [
                            {
                                "consequence_id": "clock_chain_calibrate_force_audit",
                                "effect_key": "force_story_event",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT"],
                                "payload": {
                                    "event_key": "cog_audit_event",
                                    "hint": "前情：你已在黑市留下调校记录，门后摆着一台审计机关",
                                    "message": "前情：你刚靠调校机械换到信誉。你刚离开柜台，门后就传来齿轮审计员的敲桌声。",
                                },
                            }
                        ],
                    },
                },
                {
                    "consequence_id": "clock_chain_calibrate_combat_tuning",
                    "effect_key": "atk_training",
                    "chance": 1.0,
                    "priority": 7,
                    "trigger_door_types": ["MONSTER"],
                    "payload": {
                        "delta": 1,
                        "message": "前情：你在黑市调校过计价机关。你调过的机械节奏帮你看清了敌人的出招空档。",
                        "chain_followups": [
                            {
                                "consequence_id": "clock_chain_calibrate_reward_cache",
                                "effect_key": "treasure_marked_item",
                                "chance": 1.0,
                                "trigger_door_types": ["REWARD"],
                                "payload": {
                                    "item_key": "barrier",
                                    "gold_bonus": 15,
                                    "message": "前情：你的调校记录通过了对账。你按协议领取技术红利，宝物门里是结界发生器。",
                                },
                            }
                        ],
                    },
                },
            ]

        if route == "hack":
            return [
                {
                    "consequence_id": "clock_chain_hack_shop_discount",
                    "effect_key": shop_effect,
                    "chance": 1.0,
                    "priority": 9,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": ratio,
                        "message": shop_message,
                        "chain_followups": [
                            {
                                "consequence_id": "clock_chain_hack_chargeback",
                                "effect_key": "lose_gold",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "payload": {
                                    "amount": 22,
                                    "message": "前情：你先前偷改了优惠码并拿过折扣。优惠码被追溯后触发回滚扣款，你被系统追缴了差价。",
                                    "chain_followups": [
                                        {
                                            "consequence_id": "clock_chain_hack_force_audit",
                                            "effect_key": "force_story_event",
                                            "chance": 1.0,
                                            "trigger_door_types": ["EVENT"],
                                            "payload": {
                                                "event_key": "cog_audit_event",
                                                "hint": "前情：伪造优惠码已被锁定，审计门要求你复核",
                                                "message": "前情：你的伪码交易已进入追责流程。你以为躲过了，审计门却自动在前方亮起。",
                                            },
                                        },
                                        {
                                            "consequence_id": "clock_chain_hack_reward_frozen",
                                            "effect_key": "treasure_vanish",
                                            "chance": 1.0,
                                            "trigger_door_types": ["REWARD"],
                                            "payload": {
                                                "fake_gold": 12,
                                                "message": "前情：伪码触发了系统回滚与风控。库存冻结把宝物门清空了，只给你留了点找零。",
                                            },
                                        },
                                    ],
                                },
                            }
                        ],
                    },
                }
            ]

        return [
            {
                "consequence_id": "clock_chain_sabotage_hunter",
                "effect_key": "revenge_ambush",
                "chance": 1.0,
                "priority": 10,
                "trigger_door_types": ["EVENT", "MONSTER"],
                "payload": {
                    "force_hunter": True,
                    "consume_on_defeat": True,
                    "hunter_name": hunter_name,
                    "message": "前情：你刚公开破坏了竞品摊位。碎片还在地上转，清算队已经顺着标记追来了。",
                    "chain_followups": [
                        {
                            "consequence_id": "clock_chain_sabotage_trap_backfire",
                            "effect_key": "shrine_curse",
                            "chance": 1.0,
                            "trigger_door_types": ["TRAP", "MONSTER"],
                            "payload": {
                                "duration": 2,
                                "message": "前情：你先前改坏了黑市机关。现在机关反向写入你的战斗节奏，行动开始迟滞。",
                            },
                        },
                        {
                            "consequence_id": "clock_chain_sabotage_reward_confiscated",
                            "effect_key": "treasure_vanish",
                            "chance": 1.0,
                            "trigger_door_types": ["REWARD"],
                            "payload": {
                                "message": "前情：你破坏摊位后被列入重点清算名单。市场执法先一步扣押了你的奖励，宝物门只剩封条。",
                            },
                        },
                    ],
                },
            }
        ]


class CogAuditEvent(Event):
    """齿轮链中继：宝物门被审计。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Cog Audit"
        self.description = "你在齿轮黑市留下的操作记录已经触发审计。审计员递给你三种结算方式：补税、做假账，或者买断风声。"
        self.choices = [
            EventChoice("补税结清", self.pay_tax),
            EventChoice("做假账", self.fake_ledger),
            EventChoice("买断风声", self.buy_silence),
        ]

    def pay_tax(self):
        self.register_story_choice(
            choice_flag="cog_audit_tax_paid",
            moral_delta=3,
            consequences=[
                {
                    "consequence_id": "cog_audit_tax_treasure",
                    "effect_key": "treasure_marked_item",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "item_key": "healing_scroll",
                        "gold_bonus": 22,
                        "message": "前情：你接受了审计并选择补税。补税凭证换来一份正式补给：恢复卷轴和一小袋金币。",
                        "chain_followups": [
                            {
                                "consequence_id": "cog_audit_tax_rebate",
                                "effect_key": "black_market_discount",
                                "chance": 1.0,
                                "trigger_door_types": ["SHOP"],
                                "payload": {
                                    "ratio": 0.84,
                                    "message": "前情：你在审计里按章补税并清账。你被记成合规客户，后续成交价更友好。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        p = self.get_player()
        paid = min(p.gold, 18)
        p.gold -= paid
        self.add_message(f"你先按章补缴了 {paid}G。审计员在你通行证上盖了一个'已清算'。")
        return "Event Completed"

    def fake_ledger(self):
        self.register_story_choice(
            choice_flag="cog_audit_faked",
            moral_delta=-4,
            consequences=[
                {
                    "consequence_id": "cog_audit_fake_treasure_void",
                    "effect_key": "treasure_vanish",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "message": "前情：你在审计环节选择做假账。假账生效了，但你的宝物门也被系统判定为'异常库存'并清空。",
                        "chain_followups": [
                            {
                                "consequence_id": "cog_audit_fake_fine",
                                "effect_key": "lose_gold",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "payload": {
                                    "amount": 35,
                                    "message": "前情：你的假账被系统标记并进入追缴。延迟罚款追到了你，金币被直接划扣。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        gain = 24
        self.get_player().gold += gain
        self.add_message(f"你在账本里塞进了假齿轮。它转得很顺，但声音很假——你先套走了 {gain}G。")
        return "Event Completed"

    def buy_silence(self):
        self.register_story_choice(
            choice_flag="cog_audit_silenced",
            moral_delta=-1,
            consequences=[
                {
                    "consequence_id": "cog_audit_silence_treasure",
                    "effect_key": "treasure_marked_item",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "item_key": "barrier",
                        "gold_bonus": 10,
                        "message": "前情：你在审计桌上选择买断风声。对方收了封口费，回赠你一枚战斗结界发生器。",
                        "chain_followups": [
                            {
                                "consequence_id": "cog_audit_silence_hunt",
                                "effect_key": "revenge_ambush",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "MONSTER"],
                                "payload": {
                                    "force_hunter": True,
                                    "hunter_name": "暗影刺客",
                                    "hp_ratio": 1.14,
                                    "atk_ratio": 1.15,
                                    "message": "前情：你用封口费压住了明面审计。买断风声只挡住台面，补丁猎手从后台追上来了。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        p = self.get_player()
        paid = min(p.gold, 20)
        p.gold -= paid
        self.add_message(f"你先花了 {paid}G 封口。审计员收钱很快，收尾更快。")
        return "Event Completed"


class DreamWellEvent(Event):
    """长链3：梦井回声"""
    TRIGGER_BASE_PROBABILITY = 0.06

    @classmethod
    def get_trigger_probability(cls, controller):
        moral = abs(getattr(getattr(controller, "story", None), "moral_score", 0))
        return min(0.18, cls.TRIGGER_BASE_PROBABILITY + min(0.12, moral / 500))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Dream Well"
        self.description = "井里映出的不是你的脸，而是三种未来：喝下、封井、或把梦卖掉。"
        self.choices = [
            EventChoice("喝下梦井水", self.drink_dream),
            EventChoice("封住井口", self.seal_well),
            EventChoice("把梦卖给行脚商", self.sell_dream),
        ]

    def drink_dream(self):
        self.register_story_choice(
            choice_flag="dream_well_drank",
            moral_delta=-2,
            consequences=self._build_dream_chain(
                route="drink",
                shop_effect="black_market_discount",
                ratio=0.79,
                hunter_name="幽灵",
                shop_message="你描述的梦境太精准，商人把你当成'消息源'，先给了折扣。",
            ),
        )
        healed = self.get_player().heal(12)
        self.add_message(f"梦井水让你清醒得发冷，恢复了 {healed} 点生命。")
        return "Event Completed"

    def seal_well(self):
        self.register_story_choice(
            choice_flag="dream_well_sealed",
            moral_delta=7,
            consequences=self._build_dream_chain(
                route="seal",
                shop_effect="black_market_markup",
                ratio=1.22,
                hunter_name="美杜莎",
                shop_message="你封井断了很多人的生意，商人们把这笔账算在你头上。",
            ),
        )
        healed = self.get_player().heal(8)
        self.add_message(f"你用石板封住了井口，紧绷的神经终于放松，恢复了 {healed} 点生命。")
        return "Event Completed"

    def sell_dream(self):
        self.register_story_choice(
            choice_flag="dream_well_sold",
            moral_delta=-5,
            consequences=self._build_dream_chain(
                route="sell",
                shop_effect="black_market_discount",
                ratio=0.7,
                hunter_name="冥界使者",
                shop_message="你把梦卖成货币，黑市把你列为优先交易对象。",
            ),
        )
        p = self.get_player()
        p.gold += 26
        p.take_damage(6)
        self.add_message("你卖掉了一个关于胜利的梦，立刻拿到 26G；但精神被抽走一截，受到 6 点伤害。")
        return "Event Completed"

    def _build_dream_chain(self, route, shop_effect, ratio, hunter_name, shop_message):
        if route == "drink":
            return [
                {
                    "consequence_id": "dream_chain_drink_force_court",
                    "effect_key": "force_story_event",
                    "chance": 1.0,
                    "priority": 10,
                    "trigger_door_types": ["EVENT"],
                    "payload": {
                        "event_key": "echo_court_event",
                        "hint": "前情：你刚喝下梦井水，回声法庭正在点名",
                        "message": "前情：你先前喝了梦井水。你刚靠近事件门，法槌回声就把门后的剧情改写成了庭审。",
                        "chain_followups": [
                            {
                                "consequence_id": "dream_chain_drink_bless",
                                "effect_key": "shrine_blessing",
                                "chance": 1.0,
                                "trigger_door_types": ["TRAP", "MONSTER"],
                                "payload": {
                                    "message": "前情：梦井水仍在你体内回响。你对危险的直觉短暂提升。",
                                },
                            }
                        ],
                    },
                }
            ]

        if route == "seal":
            return [
                {
                    "consequence_id": "dream_chain_seal_echo_weight",
                    "effect_key": "shrine_curse",
                    "chance": 1.0,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER", "TRAP", "EVENT"],
                    "payload": {
                        "duration": 1,
                        "message": "前情：你刚亲手封住梦井井口。未散的回声压在你身上，动作变得沉重。",
                        "chain_followups": [
                            {
                                "consequence_id": "dream_chain_seal_relic_cache",
                                "effect_key": "treasure_marked_item",
                                "chance": 1.0,
                                "trigger_door_types": ["REWARD"],
                                "payload": {
                                    "item_key": "immune_scroll",
                                    "gold_bonus": 14,
                                    "message": "前情：你选择了封井并承担了回声反噬。封井守望者在宝物门里留了免疫卷轴作为报酬。",
                                    "chain_followups": [
                                        {
                                            "consequence_id": "dream_chain_seal_trade_penalty",
                                            "effect_key": "black_market_markup",
                                            "chance": 1.0,
                                            "trigger_door_types": ["SHOP"],
                                            "payload": {
                                                "ratio": 1.2,
                                                "message": "前情：你封井后切断了梦境交易链。商人把利润损失全摊到你身上。",
                                            },
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                }
            ]

        return [
            {
                "consequence_id": "dream_chain_sell_shop_boom",
                "effect_key": shop_effect,
                "chance": 1.0,
                "priority": 9,
                "trigger_door_types": ["SHOP"],
                "payload": {
                    "ratio": ratio,
                    "message": shop_message,
                    "chain_followups": [
                        {
                            "consequence_id": "dream_chain_sell_treasure_contract",
                            "effect_key": "treasure_marked_item",
                            "chance": 1.0,
                            "trigger_door_types": ["REWARD"],
                            "payload": {
                                "item_key": "attack_up_scroll",
                                "keep_gold": False,
                                "message": "前情：你先把梦卖给行脚商，再继续滚动交易。你把梦境债券兑成攻击卷轴，宝物门里只剩这一件硬货。",
                                "chain_followups": [
                                    {
                                        "consequence_id": "dream_chain_sell_hunter",
                                        "effect_key": "revenge_ambush",
                                        "chance": 1.0,
                                        "trigger_door_types": ["EVENT", "MONSTER"],
                                        "payload": {
                                            "force_hunter": True,
                                            "consume_on_defeat": True,
                                            "hunter_name": hunter_name,
                                            "message": "前情：你持续倒卖梦境并扩大交易。你越卖越顺手，梦税征收官也越追越近。",
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                },
            }
        ]


class EchoCourtEvent(Event):
    """梦井链中继：根据庭审抉择改写宝物门。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Echo Court"
        self.description = "你与梦井相关的交易已被回声法庭立案。法庭只问一个问题：你要赎回梦、上缴梦，还是继续交易？"
        self.choices = [
            EventChoice("赎回梦境记忆", self.redeem_dream),
            EventChoice("上缴梦境税", self.pay_dream_tax),
            EventChoice("继续倒卖梦境", self.keep_trading),
        ]

    def redeem_dream(self):
        self.register_story_choice(
            choice_flag="echo_court_redeemed",
            moral_delta=5,
            consequences=[
                {
                    "consequence_id": "echo_redeem_treasure",
                    "effect_key": "treasure_marked_item",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "item_key": "immune_scroll",
                        "gold_bonus": 18,
                        "message": "前情：你在回声法庭选择赎回梦境记忆。你赎回的梦凝成了一张免疫卷轴，安静地躺在宝箱里。",
                        "chain_followups": [
                            {
                                "consequence_id": "echo_redeem_recovery",
                                "effect_key": "guard_reward",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "payload": {
                                    "gold": 18,
                                    "heal": 10,
                                    "message": "前情：你已在法庭完成赎回并接受补救。法庭判你有诚意，后续旅途得到额外补给。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        healed = self.get_player().heal(10)
        self.add_message(f"你把梦赎了回来，耳边的低语终于安静了一瞬，恢复了 {healed} 点生命。")
        return "Event Completed"

    def pay_dream_tax(self):
        self.register_story_choice(
            choice_flag="echo_court_taxed",
            moral_delta=1,
            consequences=[
                {
                    "consequence_id": "echo_tax_treasure_void",
                    "effect_key": "treasure_vanish",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "fake_gold": 5,
                        "message": "前情：你在回声法庭选择上缴梦境税。税官先你一步打开了宝物门，只给你留了 5G 手续费找零。",
                        "chain_followups": [
                            {
                                "consequence_id": "echo_tax_discount",
                                "effect_key": "black_market_discount",
                                "chance": 1.0,
                                "trigger_door_types": ["SHOP"],
                                "payload": {
                                    "ratio": 0.88,
                                    "message": "前情：你已按法庭裁定补齐梦税。部分商人愿意给你一点面子。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        p = self.get_player()
        paid = min(p.gold, 15)
        p.gold -= paid
        self.add_message(f"你先补交了 {paid}G 梦税，法槌暂时不再追着你敲。")
        return "Event Completed"

    def keep_trading(self):
        self.register_story_choice(
            choice_flag="echo_court_trading",
            moral_delta=-4,
            consequences=[
                {
                    "consequence_id": "echo_trade_treasure",
                    "effect_key": "treasure_marked_item",
                    "chance": 1.0,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "item_key": "attack_up_scroll",
                        "keep_gold": False,
                        "message": "前情：你当庭决定继续倒卖梦境。你继续交易梦境，宝物门只剩下一张攻击卷轴和一张赊账单。",
                        "chain_followups": [
                            {
                                "consequence_id": "echo_trade_hunt",
                                "effect_key": "revenge_ambush",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "MONSTER"],
                                "payload": {
                                    "force_hunter": True,
                                    "hunter_name": "暗影刺客",
                                    "hp_ratio": 1.2,
                                    "atk_ratio": 1.19,
                                    "message": "前情：你无视法庭警告继续交易梦境。收割者自然也继续追你。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        p = self.get_player()
        p.gold += 20
        p.take_damage(8)
        self.add_message("你选择把梦继续当货币，当场多赚了 20G；但回声反噬让你受了 8 点伤害。")
        return "Event Completed"


def get_story_event_by_key(event_key, controller):
    event_map = {
        "moon_verdict_event": MoonVerdictEvent,
        "cog_audit_event": CogAuditEvent,
        "echo_court_event": EchoCourtEvent,
    }
    event_cls = event_map.get(event_key)
    return event_cls(controller) if event_cls else None


STARTER_EVENT_POOL = [
    StrangerEvent,
    SmugglerEvent,
    AncientShrineEvent,
    GamblerEvent,
    LostChildEvent,
    CursedChestEvent,
    WiseSageEvent,
    RefugeeCaravanEvent,
    FallenKnightEvent,
    TimePawnshopEvent,
    MirrorTheaterEvent,
    MoonBountyEvent,
    ClockworkBazaarEvent,
    DreamWellEvent,
]


def _clamp_probability(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _weighted_pick(event_classes, weights):
    if not event_classes:
        return None
    safe_weights = [max(0.0, float(w)) for w in weights]
    total = sum(safe_weights)
    if total <= 0:
        return random.choice(event_classes)
    roll = random.uniform(0, total)
    acc = 0.0
    for event_cls, weight in zip(event_classes, safe_weights):
        acc += weight
        if roll <= acc:
            return event_cls
    return event_classes[-1]


RECENT_EVENT_WINDOW = 6  # 最近 N 次事件门内尽量不重复


def get_random_event(controller):
    candidates = [event_cls for event_cls in STARTER_EVENT_POOL if event_cls.is_trigger_condition_met(controller)]
    if not candidates:
        candidates = list(STARTER_EVENT_POOL)

    # 非后续事件门：优先排除最近出现过的类型
    recent = set(getattr(controller, "recent_event_classes", []))
    fresh = [c for c in candidates if c.__name__ not in recent]
    if fresh:
        candidates = fresh

    passed = []
    candidate_probs = []
    for event_cls in candidates:
        trigger_prob = _clamp_probability(event_cls.get_trigger_probability(controller))
        candidate_probs.append(trigger_prob)
        if random.random() <= trigger_prob:
            passed.append((event_cls, trigger_prob))

    if passed:
        event_cls = _weighted_pick(
            [event_cls for event_cls, _ in passed],
            [prob for _, prob in passed],
        )
        return event_cls(controller)

    fallback_cls = _weighted_pick(candidates, candidate_probs)
    return fallback_cls(controller)
