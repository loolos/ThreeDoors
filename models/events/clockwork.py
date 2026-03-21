"""见 models.events 包说明。"""
from models.status import StatusName
from models.story_gates import (
    ALL_PRE_FINAL_DOOR_TYPES,
    ELF_THIEF_NAME,
    ENDING_EVENT_GATE_KEYS,
    PRE_FINAL_DISPATCH_ORDER,
    PRE_FINAL_GATE_STORY_CONFIG,
)
from models.events.base import Event, EventChoice
from models.events._pkg import rng, mk_random_item, mk_reward_item

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
        self.title = "齿轮售票亭"
        self.description = "一列会自行换轨的列车停在岔路口，这是自动售票摊位，但系统已经故障：修好它可换取正规入场券，偷看优惠码能白嫖漏票，砸掉它则立刻树敌，但可能抢到材料。你需要马上选一种做法。"
        self.choices = [
            EventChoice("校准售票机关，换取正规入场券", self.calibrate),
            EventChoice("偷看优惠码，白嫖入场票", self.hack_coupon),
            EventChoice("破坏摊位，抢走材料", self.sabotage),
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
                shop_message="你修好的售票参数通过了总账验证，后续终端把你标记为合法购票者。",
            ),
        )
        tip = 12
        self.get_player().gold += tip
        self.add_message(f"你把卡死的售票机关修好并重新校到同频，系统认可后为你印上合法进入的徽章，并给了你 {tip}G 调校费。")
        return "Event Completed"

    def hack_coupon(self):
        self.register_story_choice(
            choice_flag="clockwork_hacked",
            moral_delta=-6,
            consequences=self._build_clockwork_chain(
                route="hack",
                shop_effect="black_market_discount",
                ratio=0.8,
                hunter_name="精灵法师",
                shop_message="第一家售票终端没识破你伪造的优惠码，你拿到了近乎免费的通行票。",
            ),
        )
        gain = 16
        self.get_player().gold += gain
        self.add_message(f"你偷看了优惠码，在短窗口内白嫖到 {gain}G；但系统回滚的倒计时已经亮起，查票迟早会来。")
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
                shop_message="你砸摊的画面被系统广播循环播放，几乎所有售票终端都把你列进清算名单并拒绝服务。",
            ),
        )
        p = self.get_player()
        gain = 20
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        p.take_damage(8)
        self.add_message(f"你踢翻竞品摊位后抢走 {gain}G 材料费，但飞溅齿片反弹划开护甲，让你受到 8 点伤害。")
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
                "chance": 0.65,
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
                                "message": "前情：你先前改坏了摊位机关。故障反馈反向干扰你的动作节奏，让你出手变得迟滞。",
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
        self.title = "查票清算"
        self.description = "你在售票终端留下的每一步操作都被总账追踪，如今正式触发查票清算。计价员把票务记录摊到你面前：要么补款认账、要么伪造通行证硬闯、要么贿赂计价员买断风声。你必须当场给出结算方案。"
        self.choices = [
            EventChoice("补款结清票务", self.pay_tax),
            EventChoice("伪造通行证硬闯", self.fake_ledger),
            EventChoice("贿赂计价员买断风声", self.buy_silence),
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
        self.add_message(f"你先按章补缴了 {paid}G。审计员在你通行证上盖了一个'已付款'。")
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
                        "message": "前情：你在审计环节选择做假。假通行证生效了，但你的宝物门也被系统判定为'异常库存'并清空。",
                        "chain_followups": [
                            {
                                "consequence_id": "cog_audit_fake_fine",
                                "effect_key": "lose_gold",
                                "chance": 1.0,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "payload": {
                                    "amount": 35,
                                    "message": "前情：你的假通行证被系统标记并进入追缴。延迟罚款追到了你，金币被直接划扣。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        gain = 24
        self.get_player().gold += gain
        self.add_message(f"你在通行证里里塞进了假数据。你因此获利了 {gain}G。")
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
                        "message": "前情：你在计价员那里选择贿赂买断风声。对方收了封口费，回赠你一些赠品。",
                        "chain_followups": [
                            {
                                "consequence_id": "cog_audit_silence_hunt",
                                "effect_key": "revenge_ambush",
                                "chance": 0.65,
                                "trigger_door_types": ["EVENT", "MONSTER"],
                                "payload": {
                                    "force_hunter": True,
                                    "hunter_name": "暗影刺客",
                                    "hp_ratio": 1.14,
                                    "atk_ratio": 1.15,
                                    "message": "前情：你用封口费压住了明面上的审计计价。买断风声只挡住台面，补丁猎手从后台追上来了。",
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

