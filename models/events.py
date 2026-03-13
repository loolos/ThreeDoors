
import random
from models.items import create_random_item, create_reward_door_item
from models.status import StatusName

class EventChoice:
    def __init__(self, text, callback):
        self.text = text
        self.callback = callback

class Event:
    TRIGGER_BASE_PROBABILITY = 0.1
    MIN_TRIGGER_ROUND = 0
    MAX_TRIGGER_ROUND = None
    POSITIVE_STAGE_SCALE = (1.0, 1.12, 1.27, 1.45)
    NEGATIVE_STAGE_SCALE = (1.0, 1.1, 1.22, 1.35)
    ONLY_TRIGGER_ONCE = False

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
        return cls.is_unlocked(
            controller,
            min_round=getattr(cls, "MIN_TRIGGER_ROUND", 0),
        ) and cls._is_within_round_window(controller)

    @classmethod
    def _is_within_round_window(cls, controller):
        max_round = getattr(cls, "MAX_TRIGGER_ROUND", None)
        if max_round is None:
            return True
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        return round_count <= max_round

    @classmethod
    def get_trigger_probability(cls, controller):
        return cls.TRIGGER_BASE_PROBABILITY

    @classmethod
    def get_progress_stage(cls, controller):
        """按回合和基础攻击力估算当前事件强度阶段。"""
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        player = getattr(controller, "player", None)
        base_atk = 5
        if player is not None:
            base_atk = max(1, int(getattr(player, "_atk", getattr(player, "atk", 5))))
        score = round_count * 2 + base_atk * 4
        if score >= 130:
            return 3
        if score >= 90:
            return 2
        if score >= 55:
            return 1
        return 0

    @classmethod
    def is_unlocked(cls, controller, min_round=0, min_stage=0):
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        return round_count >= min_round and cls.get_progress_stage(controller) >= min_stage

    def scale_value(self, base_value, positive=True, aggressive=False, minimum=1):
        """按玩家阶段缩放事件数值。"""
        stage = self.get_progress_stage(self.controller)
        scales = self.POSITIVE_STAGE_SCALE if positive else self.NEGATIVE_STAGE_SCALE
        scale = scales[min(stage, len(scales) - 1)]
        if aggressive and stage > 0:
            scale += stage * 0.04
        scaled = int(round(base_value * scale))
        if base_value >= 0:
            return max(minimum, scaled)
        return min(-minimum, scaled)


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
        help_cost = self.scale_value(10, positive=False)
        self.register_story_choice(
            choice_flag="stranger_helped",
            moral_delta=8,
            consequences=[
                {
                    "consequence_id": "stranger_help_village_gift",
                    "effect_key": "villagers_gift",
                    "delay_rounds": 2,
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
        if p.gold >= help_cost:
            p.gold -= help_cost
            # 70% Reward, 30% Betrayal
            if random.random() < 0.7:
                self.add_message(f"你花费{help_cost}金币为陌生人包扎。")
                item = create_random_item()
                self.add_message(f"陌生人感激地给了你 {item.name} 作为回报！")
                item.acquire(player=p)
            else:
                dmg = self.scale_value(15, positive=False, aggressive=True)
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
            gold = self.scale_value(random.randint(5, 20), positive=True)
            p.gold += gold
            self.add_message(f"你抢走了陌生人仅剩的 {gold} 金币。你的良心受到了一点谴责。")
        else:
            dmg = self.scale_value(10, positive=False)
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
    MIN_TRIGGER_ROUND = 2

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
                    "delay_rounds": 1,
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
                                "delay_rounds": 2,
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
            EventChoice("虔诚祈祷 (恢复生命)", self.pray),
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
            healed = p.heal(self.scale_value(50, positive=True, aggressive=True))
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
        gold = self.scale_value(random.randint(50, 100), positive=True, aggressive=True)
        p.gold += gold
        self.add_message(f"你在祭坛下挖出了 {gold} 金币！")
        if random.random() < 0.5:
            dmg = self.scale_value(10, positive=False, aggressive=True)
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
    MIN_TRIGGER_ROUND = 3

    @classmethod
    def get_trigger_probability(cls, controller):
        gold = max(0, getattr(controller.player, "gold", 0))
        return min(0.22, cls.TRIGGER_BASE_PROBABILITY + min(0.14, gold / 1000))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "The Gambler"
        self.description = "一个流浪赌徒向你发起挑战：'想不想玩把大的？'"
        high_bet = self.scale_value(50, positive=False, aggressive=True)
        low_bet = self.scale_value(10, positive=False)
        self.choices = [
            EventChoice(f"玩把大的 (赌{high_bet}G)", self.high_stakes),
            EventChoice(f"小玩一把 (赌{low_bet}G)", self.low_stakes),
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
                    "delay_rounds": 2,
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
        bet = self.scale_value(50, positive=False, aggressive=True)
        if p.gold < bet:
            self.add_message("你没有足够的金币！赌徒嘲笑了你一番。")
            return "Event Completed"
        
        p.gold -= bet
        if random.random() < 0.4: # 40% win rate
            win = self.scale_value(bet * 3, positive=True, aggressive=True)
            p.gold += win
            self.add_message(f"你运气爆棚！赢了 {win} 金币！")
        else:
            self.add_message(f"你输了！{bet}金币打水漂了。")
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
        bet = self.scale_value(10, positive=False)
        if p.gold < bet:
             self.add_message(f"你连{bet}金币都没有？真可怜。")
             return "Event Completed"
        
        p.gold -= bet
        if random.random() < 0.5: # 50% win rate
            win = self.scale_value(bet * 2, positive=True)
            p.gold += win
            self.add_message(f"不错，赢了 {win} 金币。")
        else:
            self.add_message(f"哎呀，运气不好，输了{bet}金币。")
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
    MIN_TRIGGER_ROUND = 4

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Lost Child"
        self.description = "一个小女孩在森林里哭泣，看起来迷路了。"
        donation = self.scale_value(20, positive=False)
        self.choices = [
            EventChoice("护送回家", self.guide_home),
            EventChoice(f"给点金币路费 ({donation}G)", self.give_gold),
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
            dmg = self.scale_value(15, positive=False)
            self.get_player().take_damage(dmg)
            self.add_message(f"送回家的路上遭遇了野兽袭击，你为了保护孩子受了伤 ({dmg}点伤害)，但最终把她安全送达。")
            # Reward
            reward = self.scale_value(100, positive=True, aggressive=True)
            self.get_player().gold += reward
            self.add_message(f"孩子的父母感激涕零，给了你 {reward} 金币作为谢礼！")
        else:
            reward = self.scale_value(50, positive=True)
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
        donation = self.scale_value(20, positive=False)
        if p.gold >= donation:
            p.gold -= donation
            self.add_message(f"你给了小女孩{donation}金币让她自己打车回家（虽然森林里没有出租车）。")
            # Karma reward (small heal)
            healed = p.heal(self.scale_value(10, positive=True))
            self.add_message(f"做善事让你心情愉悦，恢复了 {healed} HP。")
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
            dmg = self.scale_value(20, positive=False, aggressive=True)
            p.take_damage(dmg)
            self.add_message(f"宝箱突然咬了你一口！受到 {dmg} 点巨大伤害。里面什么也没有。")
        else:
            item = create_random_item()
            item.acquire(player=p)
            gold = self.scale_value(100, positive=True, aggressive=True)
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
        heal_hint = self.scale_value(50, positive=True)
        self.choices = [
            EventChoice("为了力量 (加攻击)", self.power),
            EventChoice("为了财富 (加金币)", self.wealth),
            EventChoice(f"为了生存 (恢复{heal_hint}HP)", self.health)
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
            p.change_base_atk(self.scale_value(3, positive=True))
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
            gold = self.scale_value(200, positive=True, aggressive=True)
            p.gold += gold
            self.add_message(f"老者叹了口气：'身外之物。' 他丢给你 {gold} 金币后消失了。")
        else:
            lost = min(p.gold, self.scale_value(50, positive=False, aggressive=True))
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
            healed = p.heal(self.scale_value(50, positive=True, aggressive=True))
            self.add_message(f"老者微笑道：'活着就有希望。' 你的生命值恢复了 {healed} 点。")
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
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(controller, min_round=6, min_stage=0)

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
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(controller, min_round=8, min_stage=1)

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
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(controller, min_round=10, min_stage=1)

    @classmethod
    def get_trigger_probability(cls, controller):
        moral = abs(getattr(getattr(controller, "story", None), "moral_score", 0))
        return min(0.17, cls.TRIGGER_BASE_PROBABILITY + min(0.1, moral / 600))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Mirror Theater"
        self.description = "废墟尽头亮着一座镜面剧场。传闻它会把过路人的抉择写进下一段命运：演得像谁，世界就按谁来回应你。导演不问姓名，只催你立刻选一张面具——英雄、恶徒，或直接撕本离场。"
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
                        "message": "前情：你在镜剧场把英雄演到了谢幕。你的名声先一步传开，路上有人愿意补给并提醒风险。",
                    },
                },
                {
                    "consequence_id": "mirror_hero_bless",
                    "effect_key": "shrine_blessing",
                    "chance": 0.28,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {
                        "message": "前情：你坚持了英雄剧本。危急一刻，你更容易稳住呼吸并抓住反击窗口。",
                    },
                },
            ],
        )
        healed = p.heal(12)
        self.add_message(f"谢幕时空席间竟有掌声回荡。你摘下面具后像卸下一层重负，恢复了 {healed} 点生命。")
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
                        "message": "前情：你在镜剧场把恶徒演得太像。黑市误把你当自己人，先递来一轮试探性折扣。",
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
                        "message": "前情：你在舞台上选了恶徒结局。悬赏客顺着剧评和目击者描述，很快锁定了你的行踪。",
                    },
                },
            ],
        )
        gain = random.randint(22, 42)
        p.gold += gain
        self.add_message(f"导演把反派分成塞进你手里，你拿到 {gain}G。退场时你注意到观众席有人在素描本上勾勒你的脸。")
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
                        "message": "前情：你当场撕毁剧本并拒绝入戏。剧场把这次违约上报，下一扇事件门被改写成回声法庭。",
                    },
                },
                {
                    "consequence_id": "mirror_script_aftershock",
                    "effect_key": "shrine_curse",
                    "chance": 0.25,
                    "trigger_door_types": ["MONSTER", "TRAP", "EVENT"],
                    "payload": {
                        "duration": 1,
                        "message": "前情：你撕碎剧本后强行离场。破碎台词像回音钩住神经，让你短暂失衡。",
                    },
                },
            ],
        )
        if random.random() < 0.6:
            item = create_random_item()
            item.acquire(player=p)
            self.add_message(f"你把剧本撕成纸雨，幕后人沉默片刻后反而鼓掌离席，只在台口留下了 {item.name}。")
        else:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"你撕剧本的一瞬间镜幕反噬，碎光像刀一样回卷，令你受到 {dmg} 点伤害。")
        return "Event Completed"


class MoonBountyEvent(Event):
    """长链1：月蚀通缉令"""
    TRIGGER_BASE_PROBABILITY = 0.07

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(controller, min_round=12, min_stage=1)

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
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(controller, min_round=14, min_stage=2)

    @classmethod
    def get_trigger_probability(cls, controller):
        round_count = max(0, getattr(controller, "round_count", 0))
        return min(0.17, cls.TRIGGER_BASE_PROBABILITY + min(0.11, round_count * 0.004))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Clockwork Bazaar"
        self.description = "一列会自行换轨的摊车停在岔路口。这里的移动黑市不认身份，只认你能带来多少'可兑现的经历'：修好它的机关可换信誉，篡改规则能赚快钱，砸摊则会立刻树敌。主持人敲钟，催你马上选一种做法。"
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
                shop_message="你留下的调校参数通过了总账验证，后续摊位把你标记为可靠客户。",
            ),
        )
        tip = 12
        self.get_player().gold += tip
        self.add_message(f"你把卡死的计价机关重新校到同频，主持人当众给你别上齿轮徽章，并付了 {tip}G 调校费。")
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
                shop_message="第一家摊位没识破你伪造的优惠码，价格被你压到了近乎成本线。",
            ),
        )
        gain = 16
        self.get_player().gold += gain
        self.add_message(f"你偷改了校验齿轮，伪码在短窗口内生效，先白赚 {gain}G；但系统回滚的倒计时已经亮起。")
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
                shop_message="你砸摊的画面被市场广播循环播放，几乎所有摊位都把你列进高风险名单并抬价。",
            ),
        )
        p = self.get_player()
        p.gold += 20
        p.take_damage(8)
        self.add_message("你踢翻竞品摊位后抢走 20G 材料费，但飞溅齿片反弹划开护甲，让你受到 8 点伤害。")
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
                                    "message": "前情：你靠调校机械换到了信誉额度。离柜台没几步，下一扇门后就响起齿轮审计员的敲桌声。",
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
                        "message": "前情：你在黑市调校过计价机关。熟悉的节拍感让你更容易预判敌人的出招空档。",
                        "chain_followups": [
                            {
                                "consequence_id": "clock_chain_calibrate_reward_cache",
                                "effect_key": "treasure_marked_item",
                                "chance": 1.0,
                                "trigger_door_types": ["REWARD"],
                                "payload": {
                                    "item_key": "barrier",
                                    "gold_bonus": 15,
                                    "message": "前情：你的调校记录通过了对账。按技术分成协议，宝物门里为你预留了一台结界发生器。",
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
                                    "message": "前情：你先前偷改优惠码拿走折扣。风控完成追溯后触发回滚扣款，系统直接从你账上追缴差价。",
                                    "chain_followups": [
                                        {
                                            "consequence_id": "clock_chain_hack_force_audit",
                                            "effect_key": "force_story_event",
                                            "chance": 1.0,
                                            "trigger_door_types": ["EVENT"],
                                            "payload": {
                                                "event_key": "cog_audit_event",
                                                "hint": "前情：伪造优惠码已被锁定，审计门要求你复核",
                                                "message": "前情：你的伪码交易已进入追责流程。你以为已经脱身，审计门却在前方自动点亮并锁定你。",
                                            },
                                        },
                                        {
                                            "consequence_id": "clock_chain_hack_reward_frozen",
                                            "effect_key": "treasure_vanish",
                                            "chance": 1.0,
                                            "trigger_door_types": ["REWARD"],
                                            "payload": {
                                                "fake_gold": 12,
                                                "message": "前情：伪码触发系统回滚与风控。库存先被临时冻结，宝物门被清空后只给你留了点找零。",
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
                    "message": "前情：你刚公开破坏竞品摊位。碎片还在地上打转，市场清算队已沿着追踪标记赶来。",
                    "chain_followups": [
                        {
                            "consequence_id": "clock_chain_sabotage_trap_backfire",
                            "effect_key": "shrine_curse",
                            "chance": 1.0,
                            "trigger_door_types": ["TRAP", "MONSTER"],
                            "payload": {
                                "duration": 2,
                                "message": "前情：你先前改坏了黑市机关。故障反馈反向干扰你的动作节奏，让你出手变得迟滞。",
                            },
                        },
                        {
                            "consequence_id": "clock_chain_sabotage_reward_confiscated",
                            "effect_key": "treasure_vanish",
                            "chance": 1.0,
                            "trigger_door_types": ["REWARD"],
                            "payload": {
                                "message": "前情：你破坏摊位后被列入重点清算名单。市场执法提前扣押奖励，宝物门上只剩未拆的封条。",
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
        self.description = "你在齿轮黑市留下的每一步操作都被总账追踪，如今正式触发审计。审计员把账本摊到你面前：要么补税认账、要么继续做假账硬闯、要么花钱买断风声。你必须当场给出结算方案。"
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
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(controller, min_round=16, min_stage=2)

    @classmethod
    def get_trigger_probability(cls, controller):
        moral = abs(getattr(getattr(controller, "story", None), "moral_score", 0))
        return min(0.18, cls.TRIGGER_BASE_PROBABILITY + min(0.12, moral / 500))

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Dream Well"
        self.description = "梦井的水面映出的不是你的脸，而是被提前剪好的三段结局。传闻井水会把你的念头放大成现实，所以每个选择都会留下可追踪的后果：喝下它、封住它，或把梦折价卖给行脚商。你得现在决定要把哪条线继续下去。"
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
                shop_message="你复述的梦境细节精准到可交易，商人把你当成消息源，先给了试探性折扣。",
            ),
        )
        healed = self.get_player().heal(12)
        self.add_message(f"梦井水入口冰冷，你的意识却短暂异常清明，恢复了 {healed} 点生命。")
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
                shop_message="你封井等于切断了整条梦境供货线，商人们把损失统一记在你名下。",
            ),
        )
        healed = self.get_player().heal(8)
        self.add_message(f"你用石板和封钉压死井口，耳边的低语终于减弱，恢复了 {healed} 点生命。")
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
                shop_message="你把梦直接折算成可流通凭证，黑市把你标为优先接待的高价值卖家。",
            ),
        )
        p = self.get_player()
        p.gold += 26
        p.take_damage(6)
        self.add_message("你把一个关于胜利的梦打包卖出，立刻拿到 26G；但精神像被抽走一层，受到 6 点伤害。")
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
                        "message": "前情：你先前喝下梦井水并触发了回声记录。你刚靠近事件门，法槌回声就把门后的剧情改写成庭审。",
                        "chain_followups": [
                            {
                                "consequence_id": "dream_chain_drink_bless",
                                "effect_key": "shrine_blessing",
                                "chance": 1.0,
                                "trigger_door_types": ["TRAP", "MONSTER"],
                                "payload": {
                                    "message": "前情：梦井水仍在你体内回响。你对威胁的预感被短暂放大，能更早察觉危险。",
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
                        "message": "前情：你刚亲手封住梦井井口。回声尚未散去，沉重感压在肩上，让动作变慢。",
                        "chain_followups": [
                            {
                                "consequence_id": "dream_chain_seal_relic_cache",
                                "effect_key": "treasure_marked_item",
                                "chance": 1.0,
                                "trigger_door_types": ["REWARD"],
                                "payload": {
                                    "item_key": "immune_scroll",
                                    "gold_bonus": 14,
                                    "message": "前情：你选择封井并承担了回声反噬。守望者认可你的代价，在宝物门里留下一张免疫卷轴。",
                                    "chain_followups": [
                                        {
                                            "consequence_id": "dream_chain_seal_trade_penalty",
                                            "effect_key": "black_market_markup",
                                            "chance": 1.0,
                                            "trigger_door_types": ["SHOP"],
                                            "payload": {
                                                "ratio": 1.2,
                                                "message": "前情：你封井后切断了梦境交易链。商人们把断供损失计入你的风险价并抬高报价。",
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
                                "message": "前情：你先把梦卖给行脚商，再滚动做大交易。你把梦境债券兑成攻击卷轴，宝物门里只剩这件硬货。",
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
                                            "message": "前情：你持续倒卖梦境并扩大交易规模。你越卖越熟练，梦税征收官的追缴也越逼越近。",
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
        self.description = "你与梦井相关的交易已被回声法庭正式立案。法庭认定你既是当事人也是收益者，要求你立刻表态并承担后果：赎回被卖掉的梦境记忆、补缴拖欠的梦税，或公开宣布继续交易。"
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
                        "message": "前情：你在回声法庭选择赎回梦境记忆。被赎回的梦凝成一张免疫卷轴，安静地躺在宝箱里。",
                        "chain_followups": [
                            {
                                "consequence_id": "echo_redeem_recovery",
                                "effect_key": "guard_reward",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "payload": {
                                    "gold": 18,
                                    "heal": 10,
                                    "message": "前情：你已在法庭完成赎回并接受补救。法庭认定你有修复意愿，后续旅途获得额外补给。",
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
                        "message": "前情：你在回声法庭选择上缴梦境税。税官先一步清点了宝物门，只给你留了 5G 手续费找零。",
                        "chain_followups": [
                            {
                                "consequence_id": "echo_tax_discount",
                                "effect_key": "black_market_discount",
                                "chance": 1.0,
                                "trigger_door_types": ["SHOP"],
                                "payload": {
                                    "ratio": 0.88,
                                    "message": "前情：你已按法庭裁定补齐梦税。部分商人把你从黑名单边缘挪回了普通档位。",
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
        self.add_message(f"你先补交了 {paid}G 梦税，审判席上的法槌声终于暂时停下。")
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
                        "message": "前情：你当庭决定继续倒卖梦境。交易链继续转动，宝物门里只剩一张攻击卷轴和一张赊账单。",
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
                                    "message": "前情：你无视法庭警告继续交易梦境。负责追缴的人自然不会停手。",
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
        self.add_message("你选择继续把梦当货币流通，当场多赚 20G；但回声反噬同步加深，让你受了 8 点伤害。")
        return "Event Completed"


ELF_THIEF_NAME = "莱希娅"


ELF_CHAIN_EVENT_ORDER = [
    "elf_shadow_mark_event",
    "elf_rooftop_duel_event",
    "elf_fake_map_event",
    "elf_monster_stage_event",
    "elf_night_camp_event",
    "elf_trap_rescue_event",
    "elf_hunter_gate_event",
    "elf_final_heist_event",
    "elf_epilogue_event",
]


def _get_elf_chain_state(controller):
    story = getattr(controller, "story", None)
    if story is None:
        return None
    if not hasattr(story, "elf_relation"):
        story.elf_relation = 0
    if not hasattr(story, "elf_chain_started"):
        story.elf_chain_started = False
    if not hasattr(story, "elf_middle_queue"):
        story.elf_middle_queue = []
    if not hasattr(story, "elf_chain_ended"):
        story.elf_chain_ended = False
    return story


def _adjust_elf_relation(controller, delta):
    story = _get_elf_chain_state(controller)
    if story is None:
        return 0
    story.elf_relation = max(-6, min(6, int(story.elf_relation) + int(delta)))
    return story.elf_relation


def _elf_percent_gold(player, ratio, minimum=1):
    base = max(0, int(getattr(player, "gold", 0)))
    return max(minimum, int(round(base * max(0.0, float(ratio)))))


def _elf_percent_hp(player, ratio, minimum=1):
    base = max(1, int(getattr(player, "hp", 1)))
    return max(minimum, int(round(base * max(0.0, float(ratio)))))


def _elf_percent_atk(player, ratio, minimum=1):
    base = max(1, int(getattr(player, "_atk", getattr(player, "atk", 1))))
    return max(minimum, int(round(base * max(0.0, float(ratio)))))


def _elf_grant_dynamic_boon(controller):
    """飞贼正向奖励池：不再总是加攻击，改为加血/加攻/给道具三选一。"""
    p = getattr(controller, "player", None)
    if p is None:
        return "她本想给你点东西，却只剩一句'下次。'"

    roll = random.random()
    if roll < 0.34:
        atk_up = _elf_percent_atk(p, 0.08)
        p.change_base_atk(atk_up)
        return f"她用短刃在墙上划出三道受力线，纠正了你的发力节奏（基础攻击 +{atk_up}）。"

    if roll < 0.68:
        heal = _elf_percent_hp(p, 0.14)
        p.hp = min(100, p.hp + heal)
        return f"她把止血粉和绑带塞给你，顺手重新缠好护腕（+{heal}HP）。"

    item = create_reward_door_item()
    item.acquire(player=p)
    return f"她从斗篷夹层摸出一件战利品塞进你怀里：{item.name}。'别问哪来的，能用就行。'"


def _schedule_next_elf_event(controller, completed_key):
    story = _get_elf_chain_state(controller)
    if story is None:
        return

    if completed_key == "elf_shadow_mark_event" and not story.elf_middle_queue:
        story.elf_middle_queue = [
            "elf_rooftop_duel_event",
            "elf_fake_map_event",
            "elf_monster_stage_event",
        ]
        random.shuffle(story.elf_middle_queue)

    if completed_key == "elf_intro":
        next_key = "elf_shadow_mark_event"
    elif completed_key == "elf_shadow_mark_event":
        next_key = story.elf_middle_queue.pop(0)
    elif completed_key in {
        "elf_rooftop_duel_event",
        "elf_fake_map_event",
        "elf_monster_stage_event",
    }:
        next_key = story.elf_middle_queue.pop(0) if story.elf_middle_queue else "elf_night_camp_event"
    else:
        try:
            idx = ELF_CHAIN_EVENT_ORDER.index(completed_key)
            next_key = ELF_CHAIN_EVENT_ORDER[idx + 1]
        except (ValueError, IndexError):
            return

    current_round = max(0, int(getattr(controller, "round_count", 0)))
    min_round = current_round + 5
    # 不设 max_round，避免因未在窗口内选到事件门而永久失效（事件门每轮不保证出现）
    consequence_id = f"elf_chain_force_{next_key}_{current_round}_{random.randint(1, 9999)}"
    story.register_consequence(
        choice_flag=f"elf_chain:{completed_key}",
        consequence_id=consequence_id,
        effect_key="force_story_event",
        chance=1.0,
        min_round=min_round,
        max_round=None,
        priority=99,
        trigger_door_types=["EVENT"],
        payload={
            "event_key": next_key,
            "hint": "门框上有新刻的银羽记号，正是她约好的那一扇。",
            "message": "眼前这扇门的门框上，有那道银羽刻痕，你意识到莱希亚在这里",
        },
    )


class ElfThiefIntroEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.32  # 4× 原 0.08，便于尽早触发
    MIN_TRIGGER_ROUND = 6

    @classmethod
    def is_trigger_condition_met(cls, controller):
        story = _get_elf_chain_state(controller)
        if story is not None and bool(getattr(story, "elf_chain_started", False)):
            return False
        return super().is_trigger_condition_met(controller)

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "银羽飞贼"
        self.description = (
            f"你推开事件门，门后不是寻常的奇遇或考验，而是一条烛火摇曳的暗巷。"
            f"一名精灵飞贼背靠砖墙，指尖转着匕首，抬眼打量你，自称{ELF_THIEF_NAME}。"
            f"她笑了笑：'要不要做个长期交易？'"
        )
        self.choices = [
            EventChoice("递上口粮，表示愿意合作", self.offer_food),
            EventChoice("拔刀试探，先打一场再说", self.challenge_duel),
            EventChoice("谎称你是守卫，逼她交赃", self.fake_guard),
        ]

    def _start_chain(self):
        story = _get_elf_chain_state(self.controller)
        if story is None or story.elf_chain_started:
            return
        story.elf_chain_started = True
        if not getattr(story, "elf_chain_ended", False):
            story.story_tags.add("elf_met")
            _register_elf_side_events(self.controller)
        _schedule_next_elf_event(self.controller, "elf_intro")

    def offer_food(self):
        p = self.get_player()
        cost = _elf_percent_gold(p, 0.12)
        lost = min(p.gold, cost)
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"{ELF_THIEF_NAME}毫不客气地抢走干粮与盘缠，你少了 {lost} 金币；她抛来一枚银羽徽记：'别死太早。'")
        self._start_chain()
        return "Event Completed"

    def challenge_duel(self):
        dmg = _elf_percent_hp(self.get_player(), 0.08)
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"你们点到为止地过了几招，你吃了 {dmg} 点伤害，她却笑得更开心。")
        self._start_chain()
        return "Event Completed"

    def fake_guard(self):
        p = self.get_player()
        lost = min(p.gold, _elf_percent_gold(p, 0.1))
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, -2)
        self.add_message(f"她反手把你的钱袋顺走 {lost}G：'冒充守卫前，先把靴子擦亮。'")
        self._start_chain()
        return "Event Completed"


class ElfShadowMarkEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "银羽暗号"
        self.description = (
            "你正要选一扇事件门时，发现门框背面有熟悉的银羽刻痕——那是她上次分别时约好的记号，意思是「今晚不偷你，聊聊」。"
            "你推开门，她果然在门后的阴影里等着，没动你身上的东西，只冲你抬了抬下巴。"
        )
        self.choices = [
            EventChoice("交换情报", self.share_info),
            EventChoice("追问她真实目的", self.ask_intent),
            EventChoice("放冷话：再见就算账", self.threaten),
        ]

    def share_info(self):
        gain = _elf_percent_gold(self.get_player(), 0.1)
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"你们互通了怪物巢穴路线，她提醒你绕开最毒的陷阱层；你按图摸到遗漏的财宝（+{gain}G）。")
        _schedule_next_elf_event(self.controller, "elf_shadow_mark_event")
        return "Event Completed"

    def ask_intent(self):
        heal = _elf_percent_hp(self.get_player(), 0.12)
        self.get_player().hp = min(100, self.get_player().hp + heal)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"她丢来药包：'目的？先活下来，才配知道目的。'（+{heal}HP）")
        _schedule_next_elf_event(self.controller, "elf_shadow_mark_event")
        return "Event Completed"

    def threaten(self):
        p = self.get_player()
        lost = min(p.gold, _elf_percent_gold(p, 0.08))
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, -2)
        self.add_message(f"她耸耸肩顺手摸走你钱袋一角：'那就看谁账本记得久。'（-{lost}G）转身消失在火把后。")
        _schedule_next_elf_event(self.controller, "elf_shadow_mark_event")
        return "Event Completed"


class ElfRooftopDuelEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "屋脊切磋"
        self.description = (
            "你穿过走廊时，发现她蹲在某扇门前的屋脊上，朝你招手。"
            "她跳下来，指了指身后那扇怪物门：'真怪物还没出来，趁这空档过过招，谁掉下屋脊谁请客。'"
            "你意识到她是在邀你切磋，顺便试试你的身手。"
        )
        self.choices = [
            EventChoice("认真比试", self.train_hard),
            EventChoice("故意放水", self.go_easy),
            EventChoice("趁机偷袭", self.cheap_shot),
        ]

    def train_hard(self):
        boon_text = _elf_grant_dynamic_boon(self.controller)
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"你们在屋脊上连拆七招，落地时她难得认真夸了你一句。{boon_text}")
        _schedule_next_elf_event(self.controller, "elf_rooftop_duel_event")
        return "Event Completed"

    def go_easy(self):
        heal = _elf_percent_hp(self.get_player(), 0.1)
        self.get_player().hp = min(100, self.get_player().hp + heal)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"她看穿你在放水，却还是把跌打药塞进你怀里（+{heal}HP）。")
        _schedule_next_elf_event(self.controller, "elf_rooftop_duel_event")
        return "Event Completed"

    def cheap_shot(self):
        dmg = _elf_percent_hp(self.get_player(), 0.1)
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -3)
        self.add_message(f"偷袭差点得手，但她反手把你按进瓦片里（-{dmg}HP）。")
        _schedule_next_elf_event(self.controller, "elf_rooftop_duel_event")
        return "Event Completed"


class ElfFakeMapEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "假地图与真考验"
        self.description = (
            "门后她靠在墙边，手里捏着份皱巴巴的地图，冲你晃了晃。"
            "她说：'这是这条走廊的地图，我标注过的，对你有用。'"
        )
        self.choices = [
            EventChoice("信她的标注", self.trust_map),
            EventChoice("自己重新标记路径", self.remap),
            EventChoice("把两份都卖了给商人", self.sell_both),
        ]

    def trust_map(self):
        gain = _elf_percent_gold(self.get_player(), 0.12)
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"根据她的标注，顺路摸到一处被忽视的补给箱（+{gain}G）。")
        _schedule_next_elf_event(self.controller, "elf_fake_map_event")
        return "Event Completed"

    def remap(self):
        boon_text = _elf_grant_dynamic_boon(self.controller)
        _adjust_elf_relation(self.controller, 0)
        self.add_message(f"你把她的假标注全改成自己的记号，路线更稳更实用。{boon_text}")
        _schedule_next_elf_event(self.controller, "elf_fake_map_event")
        return "Event Completed"

    def sell_both(self):
        gain = _elf_percent_gold(self.get_player(), 0.18)
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, -2)
        self.add_message(f"你把两份图都卖给商人，赚了 {gain}G，也让她记下你这笔坏账。")
        _schedule_next_elf_event(self.controller, "elf_fake_map_event")
        return "Event Completed"


class ElfMonsterStageEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "怪物门前的演武"
        self.description = (
            "你赶到时，她正从一扇怪物门里拖出一具木制假人，丢在走廊中央。"
            "'门后的真家伙还没醒，'她说，'先来练一套拆招。练完再进去不迟。'"
        )
        self.choices = [
            EventChoice("专注练闪避", self.train_dodge),
            EventChoice("专注练反击", self.train_counter),
            EventChoice("嫌麻烦直接走", self.refuse),
        ]

    def train_dodge(self):
        heal = _elf_percent_hp(self.get_player(), 0.1)
        self.get_player().hp = min(100, self.get_player().hp + heal)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"你学会了借门框卸力，体力恢复了 {heal} 点。")
        _schedule_next_elf_event(self.controller, "elf_monster_stage_event")
        return "Event Completed"

    def train_counter(self):
        boon_text = _elf_grant_dynamic_boon(self.controller)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"她让你盯着假人肩线连练十次，不再只凭蛮劲出手。{boon_text}")
        _schedule_next_elf_event(self.controller, "elf_monster_stage_event")
        return "Event Completed"

    def refuse(self):
        dmg = _elf_percent_hp(self.get_player(), 0.07)
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -1)
        self.add_message(f"她把假人踢回门后，你躲闪不及被门板刮到。'行，别怪我以后不救场。'（-{dmg}HP）")
        _schedule_next_elf_event(self.controller, "elf_monster_stage_event")
        return "Event Completed"


class ElfNightCampEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "夜营火谈"
        self.description = (
            "门后是一处坍塌神像的背风面，她生了堆小火，正在烤一只蘑菇鸡。"
            "她示意你坐下，沉默了很久才开口：追她的不是普通赏金客，而是同一个组织里被她反咬过的人。"
            "她当年偷走了他们用来买命的账册，里面记着谁给怪物门送祭品、谁拿平民换通行。"
            "现在那群人放话：要么拿回账册，要么把见过账册的人全埋进地底。"
            "火光映着她的侧脸，她把一半烤肉推给你：'所以你今晚要选，跟我一起扛，拿钱只做一单，还是听完就当没见过我。'"
        )
        self.choices = [
            EventChoice("站她这边：一起对付追兵", self.promise_help),
            EventChoice("谈价接单：先收钱再帮忙", self.ask_payment),
            EventChoice("只拿情报：记路线，之后各走各路", self.prepare_solo),
        ]

    def promise_help(self):
        heal = _elf_percent_hp(self.get_player(), 0.14)
        self.get_player().hp = min(100, self.get_player().hp + heal)
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"她难得正经地点头，把多烤的肉递给你：'好，我也记你一份人情。'（+{heal}HP）")
        _schedule_next_elf_event(self.controller, "elf_night_camp_event")
        return "Event Completed"

    def ask_payment(self):
        gain = _elf_percent_gold(self.get_player(), 0.15)
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, -1)
        self.add_message(f"她扔来 {gain}G：'佣兵价，童叟无欺。'语气却冷了半分。")
        _schedule_next_elf_event(self.controller, "elf_night_camp_event")
        return "Event Completed"

    def prepare_solo(self):
        boon_text = _elf_grant_dynamic_boon(self.controller)
        _adjust_elf_relation(self.controller, -2)
        self.add_message(f"你决定单干，她没拦你，只把一份'不欠人情'的补给甩了过来。{boon_text}")
        _schedule_next_elf_event(self.controller, "elf_night_camp_event")
        return "Event Completed"


class ElfTrapRescueEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "陷阱回廊"
        self.description = (
            "你刚踏进这条走廊就触发了连环机关，绞索从梁上落下，正往你身上收紧，把你一只脚吊了起来，机关正在靠近你，形势危急。"
            "她从梁上倒挂下来，手里捏着匕首，似笑非笑：'关系好坏，决定我救不救你。'"
        )
        self.choices = [
            EventChoice("好言相劝，求求放人", self.apologize),
            EventChoice("命令她立刻救人", self.order_her),
            EventChoice("自己挣脱，不求她", self.break_free),
        ]

    def _rescue_outcome(self):
        rel = getattr(_get_elf_chain_state(self.controller), "elf_relation", 0)
        if rel >= 2:
            heal = _elf_percent_hp(self.get_player(), 0.16)
            self.get_player().hp = min(100, self.get_player().hp + heal)
            self.add_message(f"她精准切断绞索，还顺手包扎了你的手腕（+{heal}HP）。")
        elif rel <= -2:
            dmg = _elf_percent_hp(self.get_player(), 0.14)
            self.get_player().take_damage(dmg)
            self.add_message(f"她慢了半拍才出手，你被机关刮得遍体鳞伤（-{dmg}HP）。")
        else:
            dmg = _elf_percent_hp(self.get_player(), 0.08)
            self.get_player().take_damage(dmg)
            self.add_message(f"她把你拉出陷阱，但你还是被铁刺擦伤（-{dmg}HP）。")

    def apologize(self):
        _adjust_elf_relation(self.controller, 2)
        self._rescue_outcome()
        _schedule_next_elf_event(self.controller, "elf_trap_rescue_event")
        return "Event Completed"

    def order_her(self):
        _adjust_elf_relation(self.controller, -2)
        self._rescue_outcome()
        _schedule_next_elf_event(self.controller, "elf_trap_rescue_event")
        return "Event Completed"

    def break_free(self):
        dmg = _elf_percent_hp(self.get_player(), 0.12)
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -1)
        self.add_message(f"你硬扯绞索脱身，肩膀脱臼般剧痛（-{dmg}HP）。")
        _schedule_next_elf_event(self.controller, "elf_trap_rescue_event")
        return "Event Completed"


class ElfHunterGateEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "猎门同调"
        self.description = (
            "你刚把手按上怪物门，门板就被一股巨力从里侧撞开。"
            f"{ELF_THIEF_NAME}翻身落地，肩后还插着半截断箭，三头怪物和两名披甲追兵紧咬着她不放。"
            "她一把拽住你的手腕把你拖进战圈：'别发愣，和我并线！先把最前面那头放倒！'"
        )
        self.choices = [
            EventChoice("顺着她的节奏并肩作战", self.team_up),
            EventChoice("抢击杀和战利品，不管她死活", self.selfish_fight),
            EventChoice("趁乱脱离战圈，留她断后", self.run_away),
        ]

    def team_up(self):
        boon_text = _elf_grant_dynamic_boon(self.controller)
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"你们背靠背清掉前排追兵，她在喘息间把战利品往你怀里一塞。{boon_text}")
        _schedule_next_elf_event(self.controller, "elf_hunter_gate_event")
        return "Event Completed"

    def selfish_fight(self):
        gain = _elf_percent_gold(self.get_player(), 0.14)
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, -1)
        self.add_message(f"你抢下战利品 {gain}G，她虽然没说什么，但眼神变冷。")
        _schedule_next_elf_event(self.controller, "elf_hunter_gate_event")
        return "Event Completed"

    def run_away(self):
        dmg = _elf_percent_hp(self.get_player(), 0.15)
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -3)
        self.add_message(f"你撤得太急，背后中箭（-{dmg}HP）。她在远处骂你胆小鬼。")
        _schedule_next_elf_event(self.controller, "elf_hunter_gate_event")
        return "Event Completed"


class ElfFinalHeistEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "双人盗案"
        self.description = (
            "她留下的最后一次暗号把你引到钟塔下的旧金库。"
            "你刚到，就看见莱希娅把三把钥匙摊在地上：外圈巡逻表、内层机关图、以及守卫换岗钟点。"
            "她快速说明：正门有重甲和弩手；侧井能绕进账册室但会触发毒针；但你在想，如果你此刻出卖她，守卫或许也会给你悬赏。"
            "她盯着你：'你来定，按我的线稳进稳出，赌一把高风险快线？'"
        )
        self.choices = [
            EventChoice("按她的路线走：低风险潜入并平分赃款", self.follow_plan),
            EventChoice("改走侧井快线：多拿一票但硬吃反噬", self.change_plan),
            EventChoice("敲警铃卖掉她：拿悬赏", self.betray),
        ]

    def follow_plan(self):
        gain = _elf_percent_gold(self.get_player(), 0.18)
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"你们按巡逻空窗潜入，避开正门火力，平稳带出账册与金币；你分到 {gain}G。她笑说：'这次你真像搭档。'")
        _schedule_next_elf_event(self.controller, "elf_final_heist_event")
        return "Event Completed"

    def change_plan(self):
        gain = _elf_percent_gold(self.get_player(), 0.14)
        dmg = _elf_percent_hp(self.get_player(), 0.1)
        self.get_player().gold += gain
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, 0)
        self.add_message(f"你强行改走侧井快线，确实多抄到一批现银，但触发了毒针与弩机（+{gain}G，-{dmg}HP）。")
        _schedule_next_elf_event(self.controller, "elf_final_heist_event")
        return "Event Completed"

    def betray(self):
        gain = _elf_percent_gold(self.get_player(), 0.2)
        backlash = _elf_percent_hp(self.get_player(), 0.06)
        self.get_player().gold += gain
        self.get_player().take_damage(backlash)
        _adjust_elf_relation(self.controller, -4)
        self.add_message(f"你敲响警铃换来悬赏 {gain}G，但混战中也被流矢划伤（-{backlash}HP）。她被押走前只留下一句：'你最好永远别落单。'")
        _schedule_next_elf_event(self.controller, "elf_final_heist_event")
        return "Event Completed"


class ElfEpilogueEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "银羽余响"
        rel = getattr(_get_elf_chain_state(controller), "elf_relation", 0)
        if rel >= 2:
            self.description = (
                "门后是晨雾中的一处岔路。她在雾里现身，向你抛来半枚徽章："
                "'以后你喊一声，我就来。'"
            )
        elif rel <= -2:
            self.description = (
                "门后墙上有一幅新涂鸦：一支折断的银羽，旁边写着你名字。"
                "她没有露面，但你清楚这是她留下的句号。"
            )
        else:
            self.description = (
                "门后她并没有现身，只在地上留了一袋补给和一张字条："
                "'下次见面，再分胜负。'"
            )
        self.choices = [
            EventChoice("把徽记收好：以后互相照应", self.accept_bond),
            EventChoice("只收补给：这段关系到此为止", self.close_clean),
            EventChoice("烧掉她的记号：彻底划清界线", self.burn_bridge),
        ]

    def _mark_elf_global_outcome(self, outcome_key, extra_tags=None):
        story = _get_elf_chain_state(self.controller)
        if story is None:
            return None
        story.elf_chain_ended = True
        story.story_tags.add("elf_chain_ended")
        story.story_tags.add(f"elf_outcome:{outcome_key}")
        story.choice_flags.add(f"elf_outcome_{outcome_key}")
        story.elf_final_outcome = outcome_key
        if extra_tags:
            for tag in extra_tags:
                story.story_tags.add(tag)
        return story

    def accept_bond(self):
        story = self._mark_elf_global_outcome(
            "alliance",
            extra_tags={"ending_hook:elf_alliance", "ending_hook:ally_network"},
        )
        rel = getattr(story, "elf_relation", 0) if story else 0
        boon_text = _elf_grant_dynamic_boon(self.controller)
        extra_heal = _elf_percent_hp(self.get_player(), 0.08 if rel >= 2 else 0.05)
        self.get_player().hp = min(100, self.get_player().hp + extra_heal)
        self.add_message(
            f"你把银羽徽记系在护腕上。她把手按在你肩上：'以后见暗号，算自己人。'"
            f" 临别前她又补了一手急救（+{extra_heal}HP）。{boon_text}"
        )
        return "Event Completed"

    def close_clean(self):
        story = self._mark_elf_global_outcome(
            "neutral",
            extra_tags={"ending_hook:elf_neutral", "ending_hook:lone_path"},
        )
        rel = getattr(story, "elf_relation", 0) if story else 0
        gain = _elf_percent_gold(self.get_player(), 0.12 if rel >= 0 else 0.08)
        self.get_player().gold += gain
        self.add_message(f"你把这段同行留在身后，只收下她留的路费与补给（+{gain}G）。")
        return "Event Completed"

    def burn_bridge(self):
        story = self._mark_elf_global_outcome(
            "hostile",
            extra_tags={"ending_hook:elf_hostile", "ending_hook:hunted"},
        )
        rel = getattr(story, "elf_relation", 0) if story else 0
        dmg = _elf_percent_hp(self.get_player(), 0.12 if rel > -2 else 0.16)
        self.get_player().take_damage(dmg)
        self.add_message(f"火光吞掉银羽记号，也点燃了她最后的敌意。你在撤离时被暗箭擦伤（-{dmg}HP）。")
        return "Event Completed"

    def finish(self):
        # 兼容旧存档或旧按钮文案：默认走中立收尾
        return self.close_clean()


def _register_elf_side_events(controller):
    """精灵飞贼支线：已遇见她且未终局时，登记怪物门/商店门内随机触发的独立事件（各仅一次）。"""
    story = _get_elf_chain_state(controller)
    if story is None or "elf_met" not in story.story_tags:
        return
    # 怪物门：标记为银羽与利爪（保持怪物门，进门后打怪或逃跑，根据结果不同提示）
    story.register_consequence(
        choice_flag="elf_side_reg",
        consequence_id="elf_side_monster_once",
        effect_key="elf_side_monster_mark",
        chance=1.0,
        trigger_door_types=["MONSTER"],
        required_flags={"elf_met"},
        forbidden_flags={"elf_chain_ended"},
        priority=90,
        payload={
            "chance": 0.22,
            "message": f"门后先是一阵兵器撞击声，接着有人大喊你的名字。你推门的瞬间，{ELF_THIEF_NAME}正把一头怪物踹向你：'来得正好，跟我并肩！'",
            "hint": "她被怪物和追兵缠住，正强拉你入战。",
        },
    )
    # 商店门（未认出）：门样式与购买流程像商店，实为她伪装，仅一次
    story.register_consequence(
        choice_flag="elf_side_reg",
        consequence_id="elf_side_merchant_disguised_once",
        effect_key="replace_with_elf_side_event",
        chance=1.0,
        trigger_door_types=["SHOP"],
        required_flags={"elf_met"},
        forbidden_flags={"elf_chain_ended"},
        priority=90,
        payload={
            "event_key": "elf_side_merchant_disguised_event",
            "chance": 0.18,
            "message": "你进入了杂货铺，老板热情的招呼你",
            "hint": "商人的吆喝声传来……",
        },
    )
    # 商店门（认出她）：直接揭穿，事件门对话，仅一次
    story.register_consequence(
        choice_flag="elf_side_reg",
        consequence_id="elf_side_merchant_once",
        effect_key="replace_with_elf_side_event",
        chance=1.0,
        trigger_door_types=["SHOP"],
        required_flags={"elf_met"},
        forbidden_flags={"elf_chain_ended"},
        priority=90,
        payload={
            "event_key": "elf_side_merchant_event",
            "chance": 0.18,
            "message": f"柜台后的商人懒洋洋的看着你——那眼神你认得，这是{ELF_THIEF_NAME}。",
            "hint": "某个事件在等你上钩。",
        },
    )
    # 宝物门：无选项，根据与她的关系决定是拿到宝物还是被她抢走
    story.register_consequence(
        choice_flag="elf_side_reg",
        consequence_id="elf_side_reward_once",
        effect_key="elf_side_reward_mark",
        chance=1.0,
        trigger_door_types=["REWARD"],
        required_flags={"elf_met"},
        forbidden_flags={"elf_chain_ended"},
        priority=90,
        payload={
            "chance": 0.2,
            "message": "门缝里闪过一抹银光……",
            "hint": "宝光与银羽，不知谁先到。",
        },
    )


class ElfSideMonsterEvent(Event):
    """支线：怪物门内发现飞贼在打怪，与主链独立，仅触发一次。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "银羽与利爪"
        monster = getattr(controller, "_elf_side_monster", None)
        name = getattr(monster, "name", "怪物") if monster else "怪物"
        self.description = (
            f"你跨进门槛时，{ELF_THIEF_NAME}正和一头{name}打成一团。"
            "她借力翻到你身侧，抬手就把你推向怪物侧翼："
            "'我牵制正面，你切它后腿——现在就上！'"
        )
        self.choices = [
            EventChoice("加入，一起干掉怪物", self.help_kill),
            EventChoice("趁机逃跑", self.flee),
        ]

    def help_kill(self):
        monster = getattr(self.controller, "_elf_side_monster", None)
        if monster is not None:
            self.controller.current_monster = monster
            if hasattr(self.controller, "_elf_side_monster"):
                delattr(self.controller, "_elf_side_monster")
            _adjust_elf_relation(self.controller, 1)
            self.add_message(f"{ELF_THIEF_NAME}让出破绽，你们联手解决了敌人。战后她丢给你一句：'谢了，下次还你。'")
            self.controller.scene_manager.go_to("battle_scene")
        else:
            self.add_message("幻象消散，门后只剩空荡。")
        return "Event Completed"

    def flee(self):
        if hasattr(self.controller, "_elf_side_monster"):
            delattr(self.controller, "_elf_side_monster")
        dmg = _elf_percent_hp(self.get_player(), 0.1)
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -1)
        self.add_message(f"你转身就跑，背后传来她的骂声与怪物追来的风声；你挨了一下（-{dmg}HP）。")
        return "Event Completed"


class ElfSideMerchantDisguisedEvent(Event):
    """支线：商店门内未认出她，门样式与购买流程像商店，实为她伪装，仅触发一次。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "杂货铺"
        self._items = []
        for _ in range(3):
            item = create_random_item()
            cost = max(8, int(item.cost * (0.9 + random.random() * 0.3)))
            self._items.append((item, cost))
        # 与真正商店门一致：进入后仅一句招呼，货物只在选项按钮中展示
        self.description = "神秘商人的店铺"
        # 与真正商店门一致：三个选项即三件货物及其价格，格式 "名称 (价格G)"
        self.choices = [
            EventChoice(f"{item.name} ({cost}G)", self._make_buy(i))
            for i, (item, cost) in enumerate(self._items)
        ]

    def _make_buy(self, index):
        return lambda idx=index: self._do_buy(idx)

    def _do_buy(self, index):
        if index < 0 or index >= len(self._items):
            return "Event Completed"
        item, cost = self._items[index]
        p = self.get_player()
        if p.gold >= cost:
            p.gold -= cost
            self.add_message(f"你付了 {cost} 金币，对方把货塞进你手里，懒洋洋的看着你。")
            self.add_message(f"走出几步才发现是假货-——你被骗了，刚刚那个商人是{ELF_THIEF_NAME}假扮的。")
        else:
            self.add_message("你的金币不足, 无法购买!")
        return "Event Completed"


class ElfSideMerchantEvent(Event):
    """支线：商店门内认出她，直接揭穿/对话，与主链独立，仅触发一次。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "柜台后的银羽"
        self.description = f"「伪装的商人」{ELF_THIEF_NAME}，继续热情的说到：'看看我的商品吧！你要点啥？'"
        self.choices = [
            EventChoice("识破并揭穿她", self.expose),
            EventChoice("假装上当，付钱转身就走", self.pretend_pay),
            EventChoice("不买账，转身就走", self.walk_away),
        ]

    def expose(self):
        gain = _elf_percent_gold(self.get_player(), 0.08)
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 0)
        self.add_message(f"你当众戳穿把戏，她悻悻退了你一点'封口费'（+{gain}G）。'算你狠。'")
        return "Event Completed"

    def pretend_pay(self):
        p = self.get_player()
        lost = min(p.gold, _elf_percent_gold(p, 0.12))
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"你故意付了钱，拿了假货就走，她收下 {lost}G 时眼神复杂：'谢谢惠顾。'")
        return "Event Completed"

    def walk_away(self):
        _adjust_elf_relation(self.controller, -1)
        self.add_message("你扭头离开，她在背后嘀咕：'没劲。'")
        return "Event Completed"


def get_story_event_by_key(event_key, controller):
    event_map = {
        "moon_verdict_event": MoonVerdictEvent,
        "cog_audit_event": CogAuditEvent,
        "echo_court_event": EchoCourtEvent,
        "elf_shadow_mark_event": ElfShadowMarkEvent,
        "elf_rooftop_duel_event": ElfRooftopDuelEvent,
        "elf_fake_map_event": ElfFakeMapEvent,
        "elf_monster_stage_event": ElfMonsterStageEvent,
        "elf_night_camp_event": ElfNightCampEvent,
        "elf_trap_rescue_event": ElfTrapRescueEvent,
        "elf_hunter_gate_event": ElfHunterGateEvent,
        "elf_final_heist_event": ElfFinalHeistEvent,
        "elf_epilogue_event": ElfEpilogueEvent,
        "elf_side_monster_event": ElfSideMonsterEvent,
        "elf_side_merchant_disguised_event": ElfSideMerchantDisguisedEvent,
        "elf_side_merchant_event": ElfSideMerchantEvent,
    }
    event_cls = event_map.get(event_key)
    if not event_cls or not _is_event_available(controller, event_cls):
        return None
    return event_cls(controller)


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
    ElfThiefIntroEvent,
    ClockworkBazaarEvent,
    DreamWellEvent,
]


LONG_EVENT_STARTER_CLASSES = {
    TimePawnshopEvent,
    MirrorTheaterEvent,
    MoonBountyEvent,
    ClockworkBazaarEvent,
    DreamWellEvent,
    ElfThiefIntroEvent,
}

LONG_EVENT_STARTER_FIRST_TIME_BONUS = 1.8


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


def _get_event_trigger_counts(controller):
    counts = getattr(controller, "event_trigger_counts", None)
    if counts is None:
        counts = {}
        setattr(controller, "event_trigger_counts", counts)
    return counts


def _get_event_trigger_count(controller, event_cls):
    return int(_get_event_trigger_counts(controller).get(event_cls.__name__, 0))


def _mark_event_triggered(controller, event_cls):
    counts = _get_event_trigger_counts(controller)
    name = event_cls.__name__
    counts[name] = int(counts.get(name, 0)) + 1


def _is_event_available(controller, event_cls):
    if not getattr(event_cls, "ONLY_TRIGGER_ONCE", False):
        return True
    return _get_event_trigger_count(controller, event_cls) <= 0


def _build_event_weight(controller, event_cls):
    base = _clamp_probability(event_cls.get_trigger_probability(controller))
    trigger_count = _get_event_trigger_count(controller, event_cls)
    weight = base

    # 还未触发过的长线起始事件优先级更高。
    if event_cls in LONG_EVENT_STARTER_CLASSES and trigger_count <= 0:
        weight *= LONG_EVENT_STARTER_FIRST_TIME_BONUS

    # 可重复事件按触发次数衰减：weight / (1 + 次数)
    if not getattr(event_cls, "ONLY_TRIGGER_ONCE", False):
        weight /= (1 + max(0, trigger_count))

    return max(0.0, weight)


def get_random_event(controller):
    candidates = [
        event_cls
        for event_cls in STARTER_EVENT_POOL
        if event_cls.is_trigger_condition_met(controller) and _is_event_available(controller, event_cls)
    ]
    if not candidates:
        candidates = [event_cls for event_cls in STARTER_EVENT_POOL if _is_event_available(controller, event_cls)]

    if not candidates:
        candidates = list(STARTER_EVENT_POOL)

    random.shuffle(candidates)

    # 非后续事件门：优先排除最近出现过的类型
    recent = set(getattr(controller, "recent_event_classes", []))
    fresh = [c for c in candidates if c.__name__ not in recent]
    if fresh:
        candidates = fresh

    candidate_weights = [_build_event_weight(controller, event_cls) for event_cls in candidates]
    event_cls = _weighted_pick(candidates, candidate_weights)
    if event_cls is None:
        event_cls = random.choice(candidates)
    _mark_event_triggered(controller, event_cls)
    return event_cls(controller)


LONG_EVENT_CLASSES = (
    TimePawnshopEvent,
    MirrorTheaterEvent,
    MoonBountyEvent,
    MoonVerdictEvent,
    ClockworkBazaarEvent,
    CogAuditEvent,
    DreamWellEvent,
    EchoCourtEvent,
    ElfThiefIntroEvent,
    ElfShadowMarkEvent,
    ElfRooftopDuelEvent,
    ElfFakeMapEvent,
    ElfMonsterStageEvent,
    ElfNightCampEvent,
    ElfTrapRescueEvent,
    ElfHunterGateEvent,
    ElfFinalHeistEvent,
    ElfEpilogueEvent,
)

for _event_cls in LONG_EVENT_CLASSES:
    _event_cls.ONLY_TRIGGER_ONCE = True
