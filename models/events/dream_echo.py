"""见 models.events 包说明。"""
from models.status import StatusName
from models.story_flags import (
    DREAM_WELL_DRANK,
    DREAM_WELL_SEALED,
    DREAM_WELL_SOLD,
    ECHO_COURT_REDEEMED,
    ECHO_COURT_TAXED,
    ECHO_COURT_TRADING,
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
        self.title = "梦境井"
        self.description = "梦境井的水面映出的不是你的脸，而是历代梦境的谢幕回放。传闻井水会让你看到过去的梦：喝下它看到过去的梦，封住它，或把回放折价卖给无法进入梦境的人。你得现在决定要把哪条线继续下去。"
        self.choices = [
            EventChoice("喝下井水，读取梦境回放", self.drink_dream),
            EventChoice("封住井口，拒绝回放", self.seal_well),
            EventChoice("把回放卖掉变现", self.sell_dream),
        ]

    def drink_dream(self):
        self.register_story_choice(
            choice_flag=DREAM_WELL_DRANK,
            moral_delta=-2,
            consequences=self._build_dream_chain(
                route="drink",
                shop_effect="black_market_discount",
                ratio=0.79,
                hunter_name="幽灵",
                shop_message="你复述的梦境回放细节精准到可交易，商人把你当成消息源，先给了试探性折扣。",
            ),
        )

        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        healed = rng().randint(min_heal, min_heal + 12)
        self.get_player().heal(healed)
        self.add_message(f"梦境井的水流入口冰冷，你的意识因为看到了无数种过去而变得异常清明，恢复了 {healed} 点生命。")
        return "Event Completed"

    def seal_well(self):
        self.register_story_choice(
            choice_flag=DREAM_WELL_SEALED,
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
        self.add_message(f"你用石板和封钉压死井口，历代梦境的回放低语终于减弱，恢复了 {healed} 点生命。")
        return "Event Completed"

    def sell_dream(self):
        self.register_story_choice(
            choice_flag=DREAM_WELL_SOLD,
            moral_delta=-5,
            consequences=self._build_dream_chain(
                route="sell",
                shop_effect="black_market_discount",
                ratio=0.7,
                hunter_name="冥界使者",
                shop_message="你把梦境回放直接折算成可流通凭证，黑市把你标为优先接待的高价值卖家。",
            ),
        )
        p = self.get_player()
        gain = 26
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        dmg = rng().randint(6, 12)
        p.take_damage(dmg)
        self.add_message(f"你把一段关于胜利的梦境回放打包卖出，立刻拿到 {gain}G；但精神像被抽走一层，受到 {dmg} 点伤害。")
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
                        "hint": "前情：你刚喝下梦井水，回声法庭正在点名要你出庭作证。",
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
                                        "chance": 0.65,
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
        self.title = "回声法庭"
        self.description = "你与梦境井相关的互动已被回声法庭正式立案。法庭认定你既是当事人也是收益者，要求你立刻表态并承担后果：支付赎回梦境的费用、补缴拖欠的回放罚款，或公开宣布继续交易。"
        self.choices = [
            EventChoice("赎回回放梦境", self.redeem_dream),
            EventChoice("上缴回放罚款", self.pay_dream_tax),
            EventChoice("继续倒卖回放", self.keep_trading),
        ]

    def redeem_dream(self):
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=ECHO_COURT_REDEEMED,
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
                                    "gold": max(18, min_gold),
                                    "heal": max(10, min_heal),
                                    "message": "前情：你已在法庭完成赎回并接受补救。法庭认定你有修复意愿，后续旅途获得额外补给。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        heal_amt = 10
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        heal_amt = max(heal_amt, min_heal)
        healed = self.get_player().heal(heal_amt)
        self.add_message(f"你把梦境回放赎了回来，耳边的回放低语终于安静了一瞬，恢复了 {healed} 点生命。")
        return "Event Completed"

    def pay_dream_tax(self):
        self.register_story_choice(
            choice_flag=ECHO_COURT_TAXED,
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
        self.add_message(f"你先补交了 {paid}G 梦境回放罚款，审判席上的法槌声终于暂时停下。")
        return "Event Completed"

    def keep_trading(self):
        self.register_story_choice(
            choice_flag=ECHO_COURT_TRADING,
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
                                "chance": 0.65,
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
        gain = 20
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        dmg=rng().randint(8 , 30)
        p.take_damage(dmg)
        self.add_message(f"你选择继续把梦境回放当货币流通，当场多赚 {gain}G；但回声反噬同步加深，让你受了 {dmg} 点伤害。")
        return "Event Completed"
