"""见 models.events 包说明。"""
from models.status import StatusName
from models.story_flags import (
    CARAVAN_DONATED,
    CARAVAN_EXTORTED,
    CARAVAN_IGNORED,
    choice_tag,
    CURSED_CHEST_LEFT,
    CURSED_CHEST_OPENED,
    CURSED_CHEST_PURIFIED,
    GAMBLER_DECLINED,
    GAMBLER_HIGH_STAKES,
    GAMBLER_LOW_STAKES,
    KNIGHT_AIDED,
    KNIGHT_LEFT,
    KNIGHT_LOOTED,
    LOST_CHILD_GAVE_GOLD,
    LOST_CHILD_GUIDED_HOME,
    LOST_CHILD_IGNORED,
    SAGE_HEALTH_CHOICE,
    SAGE_POWER_CHOICE,
    SAGE_WEALTH_CHOICE,
    SHRINE_DESECRATED,
    SHRINE_INSPECTED,
    SHRINE_PRAYED,
    SMUGGLER_BOUGHT_GOODS,
    SMUGGLER_LEFT,
    SMUGGLER_REPORTED,
    STRANGER_HELPED,
    STRANGER_IGNORED,
    STRANGER_ROBBED,
)
from models.story_gates import (
    ALL_PRE_FINAL_DOOR_TYPES,
    ELF_THIEF_NAME,
    ENDING_EVENT_GATE_KEYS,
    PRE_FINAL_DISPATCH_ORDER,
    PRE_FINAL_GATE_STORY_CONFIG,
)
from models.events.base import Event, EventChoice
from models.events._pkg import rng, mk_random_item, mk_reward_item

# 1. Injured Stranger
class StrangerEvent(Event):
    TRIGGER_BASE_PROBABILITY = 0.12

    def __init__(self, controller):
        super().__init__(controller)
        self.help_cost = rng().randint(10, 15)
        self.title = "受伤的陌生人"
        self.description = "走廊中，你看到一个满身是血的陌生人倒在路边，看起来非常虚弱。"
        self.choices = [
            EventChoice(f"救助他 (失去{self.help_cost}金币)", self.help_stranger),
            EventChoice("抢劫他", self.rob_stranger),
            EventChoice("无视离开", self.ignore_stranger)
        ]

    def help_stranger(self):
        p = self.get_player()
        help_cost = self.help_cost
        self.register_story_choice(
            choice_flag=STRANGER_HELPED,
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
            if rng().random() < 0.7:
                self.add_message(f"你花费{help_cost}金币为陌生人包扎。")
                item = mk_random_item()
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
            choice_flag=STRANGER_ROBBED,
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
        if rng().random() < 0.6:
            gold = self.scale_value(rng().randint(5, 20), positive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            gold = max(gold, min_gold)
            p.gold += gold
            self.add_message(f"你抢走了陌生人仅剩的 {gold} 金币。你的良心受到了一点谴责。")
        else:
            dmg = self.scale_value(10, positive=False)
            p.take_damage(dmg)
            self.add_message(f"陌生人突然暴起反击！你受到 {dmg} 点伤害，狼狈逃跑。")
        return "Event Completed"

    def ignore_stranger(self):
        self.register_story_choice(
            choice_flag=STRANGER_IGNORED,
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
        self.title = "走私犯"
        self.description = "走廊里，一个鬼鬼祟祟的人拦住你，兜售据说能绕过安保的和货物。"
        self.item = mk_random_item()
        self.cost = max(10, int(self.item.cost * 0.7)) # 30% off usually
        
        self.choices = [
            EventChoice(f"购买 {self.item.name} ({self.cost}G)", self.buy_item),
            EventChoice("举报他", self.report_smuggler),
            EventChoice("离开", self.leave)
        ]

    def buy_item(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=SMUGGLER_BOUGHT_GOODS,
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
                                "required_flags": [choice_tag(SMUGGLER_BOUGHT_GOODS)],
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
            if rng().random() < 0.8:
                self.item.acquire(player=p)
                self.add_message(f"你以 {self.cost}G 的低价买到了 {self.item.name}！")
            else:
                self.add_message("你付了钱，打开包裹一看——里面是一块石头！走私犯早就没影了。")
        else:
            self.add_message("走私犯翻了个白眼：'没钱就滚！'")
        return "Event Completed"

    def report_smuggler(self):
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=SMUGGLER_REPORTED,
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "smuggler_report_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.35,
                    "priority": 7,
                    "trigger_door_types": ["SHOP", "EVENT", "REWARD"],
                    "payload": {
                        "gold": max(rng().randint(25, 55), min_gold),
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
        if rng().random() < 0.5:
            reward = rng().randint(30, 60)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            reward = max(reward, min_gold)
            self.get_player().gold += reward
            self.add_message(f"卫兵抓住了走私犯，并奖励你 {reward} 金币！")
        else:
            dmg = rng().randint(5, 15)
            self.get_player().take_damage(dmg)
            self.add_message(f"走私犯发现了你的意图，把你揍了一顿后跑了！受到 {dmg} 点伤害。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag=SMUGGLER_LEFT, moral_delta=0)
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
        self.title = "古老祭坛"
        self.description = "侧厅深处，一座刻满神秘符文的祭坛矗立着——据说是旧时代表演的仪式台。"
        self.choices = [
            EventChoice("虔诚祈祷 (恢复生命)", self.pray),
            EventChoice("破坏祭坛", self.desecrate),
            EventChoice("仔细调查", self.inspect)
        ]

    def pray(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=SHRINE_PRAYED,
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
        if rng().random() < 0.7:
            heal_amt = self.scale_value(50, positive=True, aggressive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
            heal_amt = max(heal_amt, min_heal)
            healed = p.heal(heal_amt)
            self.add_message(f"一道温暖的光芒笼罩着你，你的伤势恢复了 {healed} 点！")
        else:
            duration = 3
            p.apply_status(StatusName.WEAK.create_instance(duration=duration, target=p))
            self.add_message(f"祭坛突然喷出一股黑气！你被诅咒了，进入虚弱状态 {duration} 回合。")
        return "Event Completed"

    def desecrate(self):
        p = self.get_player()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=SHRINE_DESECRATED,
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
                    "payload": {"gold": max(rng().randint(20, 40), min_gold), "message": "你记住了祭坛藏宝手法，顺手又捞到一笔。"},
                },
            ],
        )
        gold = self.scale_value(rng().randint(50, 100), positive=True, aggressive=True)
        p.gold += gold
        self.add_message(f"你在祭坛下挖出了 {gold} 金币！")
        if rng().random() < 0.5:
            dmg = self.scale_value(10, positive=False, aggressive=True)
            p.take_damage(dmg)
            self.add_message(f"但这触怒了神灵，一道闪电劈中了你！受到 {dmg} 点伤害。")
        return "Event Completed"

    def inspect(self):
        self.register_story_choice(
            choice_flag=SHRINE_INSPECTED,
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
        if rng().random() < 0.7:
             self.add_message("你在祭坛后面发现了一个遗落的包裹...")
             item = mk_random_item()
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
        self.title = "走廊赌档"
        self.description = "走廊间隙，一个流浪赌徒在走廊拦住你：'想不想玩把大的？赌注是金币。'"
        high_bet = self.scale_value(50, positive=False, aggressive=True)
        low_bet = self.scale_value(10, positive=False)
        self.choices = [
            EventChoice(f"玩把大的 (赌{high_bet}G)", self.high_stakes),
            EventChoice(f"小玩一把 (赌{low_bet}G)", self.low_stakes),
            EventChoice("拒绝", self.decline)
        ]

    def high_stakes(self):
        p = self.get_player()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=GAMBLER_HIGH_STAKES,
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
                    "payload": {"gold": max(rng().randint(25, 55), min_gold), "message": "因你之前在赌局上手气正旺，后续交易也有额外进账。"},
                },
            ],
        )
        bet = self.scale_value(50, positive=False, aggressive=True)
        if p.gold < bet:
            self.add_message("你没有足够的金币！赌徒嘲笑了你一番。")
            return "Event Completed"
        
        p.gold -= bet
        if rng().random() < 0.4: # 40% win rate
            win = self.scale_value(bet * 3, positive=True, aggressive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            win = max(win, min_gold)
            p.gold += win
            self.add_message(f"你运气爆棚！赢了 {win} 金币！")
        else:
            self.add_message(f"你输了！{bet}金币打水漂了。")
        return "Event Completed"

    def low_stakes(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=GAMBLER_LOW_STAKES,
            moral_delta=-1,
            consequences=[
                {
                    "consequence_id": "gambler_low_small_revenge",
                    "effect_key": "lose_gold",
                    "chance": 0.2,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": rng().randint(10, 20), "message": "因你之前小玩了一把，被赌徒顺走了点钱，事后才发现。"},
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
        if rng().random() < 0.5: # 50% win rate
            win = self.scale_value(bet * 2, positive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            win = max(win, min_gold)
            p.gold += win
            self.add_message(f"不错，赢了 {win} 金币。")
        else:
            self.add_message(f"哎呀，运气不好，输了{bet}金币。")
        return "Event Completed"

    def decline(self):
        self.register_story_choice(
            choice_flag=GAMBLER_DECLINED,
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
        self.title = "迷路孩童"
        self.description = "走廊深处，一个小女孩在哭泣，看起来在迷宫般的走廊中迷路了。"
        donation = self.scale_value(20, positive=False)
        self.choices = [
            EventChoice("护送回家", self.guide_home),
            EventChoice(f"给点金币路费 ({donation}G)", self.give_gold),
            EventChoice("无视", self.ignore)
        ]

    def guide_home(self):
        self.register_story_choice(
            choice_flag=LOST_CHILD_GUIDED_HOME,
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
                                "required_flags": [choice_tag(LOST_CHILD_GUIDED_HOME)],
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
        if rng().random() < 0.3:
            # Encounter monster logic could be complex, for now simple damage from "exhaustion"
            dmg = self.scale_value(15, positive=False)
            self.get_player().take_damage(dmg)
            self.add_message(f"送回家的路上遭遇了野兽袭击，你为了保护孩子受了伤 ({dmg}点伤害)，但最终把她安全送达。")
            # Reward
            reward = self.scale_value(100, positive=True, aggressive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            reward = max(reward, min_gold)
            self.get_player().gold += reward
            self.add_message(f"孩子的父母感激涕零，给了你 {reward} 金币作为谢礼！")
        else:
            reward = self.scale_value(50, positive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            reward = max(reward, min_gold)
            self.get_player().gold += reward
            self.add_message(f"你顺利把孩子送回了家。她父母给了你 {reward} 金币。")
        return "Event Completed"

    def give_gold(self):
        p = self.get_player()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=LOST_CHILD_GAVE_GOLD,
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "lost_child_give_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.3,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"gold": max(rng().randint(15, 35), min_gold), "heal": max(5, min_heal), "message": "因你之前资助了迷路的孩子，这事被传开后，路人对你伸出了援手。"},
                },
                {
                    "consequence_id": "lost_child_give_pickpocket",
                    "effect_key": "lose_gold",
                    "chance": 0.23,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": rng().randint(12, 28), "message": "因你之前资助孩子时出手阔绰，被人盯上后顺走了一笔钱。"},
                },
            ],
        )
        donation = self.scale_value(20, positive=False)
        if p.gold >= donation:
            p.gold -= donation
            self.add_message(f"你给了小女孩{donation}金币让她自己打车回家（虽然森林里没有出租车）。")
            # Karma reward (small heal)
            heal_amt = self.scale_value(10, positive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
            heal_amt = max(heal_amt, min_heal)
            healed = p.heal(heal_amt)
            self.add_message(f"做善事让你心情愉悦，恢复了 {healed} HP。")
        else:
            self.add_message("你想帮忙但没钱，只能尴尬地安慰了几句。")
        return "Event Completed"

    def ignore(self):
        self.register_story_choice(
            choice_flag=LOST_CHILD_IGNORED,
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
        self.title = "诅咒宝箱"
        self.description = "一个散发着诡异紫光的道具箱，上面刻着警告语：'贪婪者必受惩罚'——像是过去的时代的遗留物。"
        self.choices = [
            EventChoice("强行打开", self.open_chest),
            EventChoice("试图净化", self.purify),
            EventChoice("离开", self.leave)
        ]

    def open_chest(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=CURSED_CHEST_OPENED,
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
        if rng().random() < 0.6: # 60% bad
            dmg = self.scale_value(20, positive=False, aggressive=True)
            p.take_damage(dmg)
            self.add_message(f"宝箱突然咬了你一口！受到 {dmg} 点巨大伤害。里面什么也没有。")
        else:
            item = mk_random_item()
            item.acquire(player=p)
            gold = self.scale_value(100, positive=True, aggressive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            gold = max(gold, min_gold)
            p.gold += gold
            self.add_message(f"你忍受着诅咒的侵蚀打开了箱子，获得了 {item.name} 和 {gold} 金币！")
        return "Event Completed"

    def purify(self):
        self.register_story_choice(
            choice_flag=CURSED_CHEST_PURIFIED,
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
        if rng().random() < 0.5:
            gold = 50
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            gold = max(gold, min_gold)
            self.get_player().gold += gold
            self.add_message(f"你成功净化了诅咒，箱子里只剩下一些普通的财宝 ({gold}G)。")
        else:
            self.add_message("你的净化失败了，箱子消失在虚空中。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag=CURSED_CHEST_LEFT, moral_delta=1)
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
        self.title = "智者"
        self.description = "一位白胡子老者在走廊拦住了去路：'年轻的旅人，为了什么而踏上这舞台？'"
        heal_hint = self.scale_value(50, positive=True)
        self.choices = [
            EventChoice("为了力量 (加攻击)", self.power),
            EventChoice("为了财富 (加金币)", self.wealth),
            EventChoice(f"为了生存 (恢复{heal_hint}HP)", self.health)
        ]

    def power(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=SAGE_POWER_CHOICE,
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
        if rng().random() < 0.7:
            self.add_message("老者点了点头：'力量是双刃剑。'")
            p.change_base_atk(self.scale_value(3, positive=True))
        else:
            duration = 3
            p.apply_status(StatusName.WEAK.create_instance(duration=duration, target=p))
            self.add_message(f"老者摇头：'你渴望力量，却被力量吞噬。' 你变得虚弱了 ({duration}回合)。")
        return "Event Completed"

    def wealth(self):
        p = self.get_player()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=SAGE_WEALTH_CHOICE,
            moral_delta=-3,
            consequences=[
                {
                    "consequence_id": "sage_wealth_windfall",
                    "effect_key": "guard_reward",
                    "chance": 0.28,
                    "trigger_door_types": ["SHOP", "REWARD", "EVENT"],
                    "payload": {"gold": max(rng().randint(30, 70), min_gold), "message": "因你在老者处选了财富，嗅到机会后顺手又赚了一笔。"},
                },
                {
                    "consequence_id": "sage_wealth_fine",
                    "effect_key": "lose_gold",
                    "chance": 0.3,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": rng().randint(20, 50), "message": "因你在老者处选了财富，逐利行为引来盘查，被罚了一笔钱。"},
                },
            ],
        )
        if rng().random() < 0.7:
            gold = self.scale_value(200, positive=True, aggressive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
            gold = max(gold, min_gold)
            p.gold += gold
            self.add_message(f"老者叹了口气：'身外之物。' 他丢给你 {gold} 金币后消失了。")
        else:
            lost = min(p.gold, self.scale_value(50, positive=False, aggressive=True))
            p.gold -= lost
            self.add_message(f"老者手一挥，你口袋里的 {lost} 金币变成了石头。'贪婪是原罪。'")
        return "Event Completed"

    def health(self):
        p = self.get_player()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=SAGE_HEALTH_CHOICE,
            moral_delta=4,
            consequences=[
                {
                    "consequence_id": "sage_health_guard_help",
                    "effect_key": "guard_reward",
                    "chance": 0.27,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"gold": max(rng().randint(10, 30), min_gold), "heal": max(8, min_heal), "message": "因你在老者处选了生存，重视生存的态度感染了路人，获得援助。"},
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
        if rng().random() < 0.7:
            heal_amt = self.scale_value(50, positive=True, aggressive=True)
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
            heal_amt = max(heal_amt, min_heal)
            healed = p.heal(heal_amt)
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
        self.title = "逃难队伍"
        self.description = "你发现了一支混乱的人马似乎不是这里的人，他们似乎是偷跑进来的难民，他们请求你不要声张，最好还能赞助点食物与路费，好让他们继续隐藏在这里。"
        self.choices = [
            EventChoice("捐助 25G", self.donate),
            EventChoice("索要保护费", self.extort),
            EventChoice("假装没看见", self.walk_away),
        ]

    def donate(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=CARAVAN_DONATED,
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
        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        revenge_deadline_round = current_round + 10
        self.register_story_choice(
            choice_flag=CARAVAN_EXTORTED,
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
                                "required_flags": [choice_tag(CARAVAN_EXTORTED)],
                                "payload": {
                                    "hp_ratio": 1.18,
                                    "atk_ratio": 1.15,
                                    "message": "地下行会想“试试你够不够狠”，于是派人来探底。",
                                },
                            }
                        ],
                    },
                },
                {
                    "consequence_id": "caravan_extort_deadline_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.24,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "max_round": revenge_deadline_round,
                    "force_on_expire": True,
                    "force_door_type": "MONSTER",
                    "payload": {
                        "force_hunter": True,
                        "hunter_name": "复仇执行者",
                        "hunter_hint": "车队残破的旗帜挂在门后，追债的人已经等了你很久。",
                        "message": [
                            "你抢劫车队的旧账被翻了出来，复仇者堵住了去路。",
                            "被你洗劫的车队雇来了追猎者，这次他们不打算谈判。",
                        ],
                        "log_trigger": "你忽然看见地上那面破旗，意识到车队的复仇追上来了。期限已到，复仇者破门而入，你被强行拖进了清算战。",
                    },
                },
            ],
        )
        gain = rng().randint(20, 45)
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        self.add_message(f"你恐吓了车队，抢到 {gain} 金币。")
        return "Event Completed"

    def walk_away(self):
        self.register_story_choice(choice_flag=CARAVAN_IGNORED, moral_delta=-2)
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
        self.title = "落难骑士"
        self.description = "一名重伤的骑士倒在走廊路边，他眼神空洞，六神无主，不知道接下来该如何行动。似乎已经放弃了希望。"
        self.choices = [
            EventChoice("帮助骑士", self.aid_knight),
            EventChoice("搜刮装备", self.loot_knight),
            EventChoice("谨慎离开", self.leave),
        ]

    def aid_knight(self):
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=KNIGHT_AIDED,
            moral_delta=8,
            consequences=[
                {
                    "consequence_id": "knight_aid_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.36,
                    "trigger_door_types": ["EVENT", "SHOP", "REWARD"],
                    "payload": {
                        "gold": max(rng().randint(20, 50), min_gold),
                        "heal": max(10, min_heal),
                        "message": "因你之前救治了骑士，王国巡逻队认出你的善举，给予补给：获得 {gold} 金币，恢复 {healed} 生命。",
                    },
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
        heal_amt = 15
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        heal_amt = max(heal_amt, min_heal)
        healed = self.get_player().heal(heal_amt)
        self.add_message(f"你为骑士包扎，自己也振作起来，恢复了 {healed} 生命。")
        return "Event Completed"

    def loot_knight(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=KNIGHT_LOOTED,
            moral_delta=-10,
            consequences=[
                {
                    "consequence_id": "knight_loot_bounty",
                    "effect_key": "lose_gold",
                    "chance": 0.34,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"amount": rng().randint(20, 40), "message": "你洗劫骑士的事被追责，花钱才摆平。"},
                },
                {
                    "consequence_id": "knight_loot_underworld_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.29,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.74,
                        "message": [
                            "你拿出的骑士徽记还带着血渍，黑市商人却只问了一句：'整套还是散卖？'",
                            "对方认出那是军械制式，压低声音说：'这种货，今天我给你高价低税。'",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "knight_loot_witness",
                                "effect_key": "lose_gold",
                                "chance": 0.26,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "required_flags": [choice_tag(KNIGHT_LOOTED)],
                                "payload": {
                                    "amount": rng().randint(15, 35),
                                    "message": "有人认出了那套装备，你花钱才堵住了对方的嘴。",
                                },
                            }
                        ],
                    },
                },
            ],
        )
        gain = rng().randint(25, 55)
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        self.add_message(f"你扒下骑士身上的值钱物件，获得 {gain} 金币。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag=KNIGHT_LEFT, moral_delta=0)
        self.add_message("你不确定这是陷阱，选择绕开。")
        return "Event Completed"

