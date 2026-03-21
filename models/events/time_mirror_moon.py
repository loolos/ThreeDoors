"""见 models.events 包说明。"""
from models.status import StatusName
from models.story_flags import (
    MIRROR_PLAYED_HERO,
    MIRROR_PLAYED_VILLAIN,
    MIRROR_TORE_SCRIPT,
    TIME_BROKE_HOURGLASS,
    TIME_PAWNED_FUTURE,
    TIME_REDEEMED_DEBT,
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
        self.title = "时光当铺"
        self.description = "后台的巷口出现一家只在黄昏开门的当铺，掌柜说：'我们这可以抵押明天，赎回昨天——这里没有白拿的东西。'"
        self.choices = [
            EventChoice("抵押明天，立刻拿钱", self.pawn_tomorrow),
            EventChoice("赎回旧债，清掉利息", self.redeem_debt),
            EventChoice("砸碎柜台，抢走材料", self.break_hourglass),
        ]

    def pawn_tomorrow(self):
        p = self.get_player()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=TIME_PAWNED_FUTURE,
            moral_delta=-3,
            consequences=[
                {
                    "consequence_id": "time_pawn_quick_cash",
                    "effect_key": "guard_reward",
                    "chance": 1.0,
                    "priority": 9,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {
                        "gold": max(30, min_gold),
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
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        self.add_message(f"你在契约上按下手印，先拿到 {gain}G。掌柜提醒你：'到期我们自己来取。'")
        return "Event Completed"

    def redeem_debt(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=TIME_REDEEMED_DEBT,
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
            heal_amt = 10
            round_count = max(0, int(getattr(self.controller, "round_count", 0)))
            min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
            heal_amt = max(heal_amt, min_heal)
            healed = p.heal(heal_amt)
            self.add_message(f"你付了 {fee}G 利息，账本上你的名字被划掉，老板给你一包糖果，恢复了 {healed} 点生命。")
        else:
            self.add_message("你想赎债，但钱不够。掌柜把账页翻到下一行，笑而不语。")
        return "Event Completed"

    def break_hourglass(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=TIME_BROKE_HOURGLASS,
            moral_delta=-7,
            consequences=[
                {
                    "consequence_id": "time_break_hunter",
                    "effect_key": "revenge_ambush",
                    "chance": 0.65,
                    "priority": 10,
                    "trigger_door_types": ["EVENT", "MONSTER"],
                    "payload": {
                        "force_hunter": True,
                        "hunter_name": "暗影刺客",
                        "consume_on_defeat": True,
                        "message": "前情：你砸了当铺的柜台。清算人沿着碎砂的痕迹追了上来。",
                        "hunter_hint": "前情：你破坏了当铺的柜台。门后有清算人在等你。",
                    },
                },
                {
                    "consequence_id": "time_break_reward_confiscated",
                    "effect_key": "treasure_vanish",
                    "chance": 0.45,
                    "trigger_door_types": ["REWARD"],
                    "payload": {
                        "fake_gold": 8,
                        "message": "前情：你砸了当铺的柜台后被录像记名。宝物门已被提前冻结，只剩手续找零。",
                    },
                },
            ],
        )
        loot = rng().randint(18, 35)
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        loot = max(loot, min_gold)
        p.gold += loot
        self.add_message(f"你砸烂柜台后抢出 {loot}G。墙上的钟同时停了五秒。")
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
        self.title = "镜面剧场"
        self.description = "四周都是镜子的假面剧场的预演厅在走廊尽头亮起。传闻镜面剧场会把过路人的抉择写进下一段命运：演得像谁，世界就按谁来回应你。导演不问姓名，只催你立刻选一张面具——英雄、恶徒，或直接撕本离场。"
        self.choices = [
            EventChoice("戴上英雄面具", self.play_hero),
            EventChoice("戴上恶徒面具", self.play_villain),
            EventChoice("撕掉剧本离场", self.tear_script),
        ]

    def play_hero(self):
        p = self.get_player()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=MIRROR_PLAYED_HERO,
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "mirror_hero_support",
                    "effect_key": "guard_reward",
                    "chance": 0.34,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {
                        "gold": max(rng().randint(18, 36), min_gold),
                        "heal": max(8, min_heal),
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
        heal_amt = 12
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        heal_amt = max(heal_amt, min_heal)
        healed = p.heal(heal_amt)
        self.add_message(f"谢幕时空席间竟有掌声回荡。你摘下面具后像卸下一层重负，恢复了 {healed} 点生命。")
        return "Event Completed"

    def play_villain(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=MIRROR_PLAYED_VILLAIN,
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
        gain = rng().randint(22, 42)
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        self.add_message(f"导演把反派分成塞进你手里，你拿到 {gain}G。退场时你注意到观众席有人在素描本上勾勒你的脸。")
        return "Event Completed"

    def tear_script(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag=MIRROR_TORE_SCRIPT,
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
        if rng().random() < 0.6:
            item = mk_random_item()
            item.acquire(player=p)
            self.add_message(f"你把剧本撕成纸雨，幕后人沉默片刻后反而鼓掌离席，你走近一看，他留下了 {item.name}。")
        else:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"你撕剧本的一瞬间镜幕反噬，碎光像刀一样回卷，令你受到 {dmg} 点伤害。")
        return "Event Completed"

