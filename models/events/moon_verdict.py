"""见 models.events 包说明。"""
from models.status import StatusName
from models.story_flags import (
    MOON_BOUNTY_ACCEPT,
    MOON_BOUNTY_DOUBLE,
    MOON_BOUNTY_PROTECT,
    MOON_VERDICT_BURNED,
    MOON_VERDICT_CLEAN,
    MOON_VERDICT_EXTORTED,
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

class MoonBountyEvent(Event):
    """长链1：月蚀通缉令"""
    TRIGGER_BASE_PROBABILITY = 0.07

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return cls.is_unlocked(controller, min_round=12, min_stage=1)

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "月蚀通缉令"
        self.description = (
            "剧场走廊的墙上贴着一张会发光的通缉令，落款是安保回收系统："
            "'月蚀前带回命运乐谱大盗，生死不论；命运乐章必须追回。' "
            "但角落里有被反复涂抹的批注：'目标身份待复核'。"
        )
        self.choices = [
            EventChoice("接单追猎，准备当场拿下「命运乐谱大盗」", self.accept_contract),
            EventChoice("撕毁通缉令并暗中护送目标", self.protect_target),
            EventChoice("两边伪造线索，等他们互咬后再收网", self.double_cross),
        ]

    def accept_contract(self):
        self.register_story_choice(
            choice_flag=MOON_BOUNTY_ACCEPT,
            moral_delta=-4,
            consequences=self._build_moon_chain(
                route="accept",
                battle_mode="thief",
                chain_message=(
                    "前情：你在通缉令上按了指印，等于把自己挂进安保回收系统的任务队列。"
                    "走廊灯管忽明忽暗，像有人在远处核对编号；你知道下一扇门后不会再有中立的路人，"
                    "只有被系统标记为「目标」的影子——他怀里紧抱着什么，轮廓像乐谱，又像一本磨破的册子。"
                ),
                chain_hint=(
                    "前情：追猎令已生效，你的袖口里还留着线人塞来的半张草图。"
                    "门缝里渗出旧纸与铁锈的气味；里面的人没有先开口，只是用目光量过你腰侧的武器与指节——"
                    "他在判断你是来交货的猎手，还是另一批想抢功的人。"
                ),
                verdict_hint=(
                    "前情：追猎战后，你从对方身上只摸到一本私人日记，纸页里写满日期与街名，却没有任何乐章标题。"
                    "案卷接口却仍在推送红色提醒：审判庭已把你的编号与证物栏绑定，不出庭就会被视为拒执。"
                ),
            ),
        )
        p = self.get_player()
        prep_cost = min(p.gold, 14)
        p.gold -= prep_cost
        if prep_cost > 0:
            self.add_message(
                f"你掏出 {prep_cost}G，换到几行写得歪歪扭扭的线报：哪个转角有人盯梢、哪扇门后曾传出孩子的哭声。"
                "线人把钱数了两遍，末了把通缉令往你袖里一塞，声音压得很低："
                "「安保要的是结案率，不是真相。你真要动手，至少别在第一眼就把人钉死成贼。」"
                "你折好令纸，指腹还能摸到角落里那行被反复涂改的批注——「目标身份待复核」，像一句没说完的警告。"
            )
        else:
            self.add_message(
                "你掏遍口袋也凑不出买情报的钱，只能把通缉令硬折进袖口，当作唯一的凭证。"
                "走廊里有人与你擦肩而过，目光在你和墙上的发光告示之间扫了一个来回，什么也没说。"
                "你忽然意识到：在系统眼里，穷猎手与富猎手没有区别，都会在同一条追猎链上被推着走；"
                "你只是比旁人更赤裸地面对下一扇门——门后是谁、怀里抱着什么，你只能用自己的眼睛去认。"
            )
        return "Event Completed"

    def protect_target(self):
        self.register_story_choice(
            choice_flag=MOON_BOUNTY_PROTECT,
            moral_delta=6,
            consequences=self._build_moon_chain(
                route="protect",
                battle_mode="guardian",
                chain_message=(
                    "前情：你把发光告示从墙上撕下，纸缘割过指腹，像一道细小的誓约。"
                    "被通缉者愣了一瞬，下意识把胸前的旧册子抱得更紧；你没有追问那里面是不是「命运乐章」，"
                    "只侧身挡住走廊尽头探来的视线。远处传来金属靴底敲击地面的节奏——不是观众散场的脚步，"
                    "而是安保编制里那种从不慌乱的逼近。"
                ),
                chain_hint=(
                    "前情：你站在通缉对象与门之间，等于在系统日志里把自己刷成「协助逃逸」的可疑条目。"
                    "门后甲胄摩擦声骤起，盾面反光里同时映出你与对方的轮廓；守护者不报姓名，只宣读条款般的短句——"
                    "证物优先、现场优先、任何阻拦者一并登记。"
                ),
                verdict_hint=(
                    "前情：混战中，被通缉者把一本磨破的日记塞进你手里，指尖抖得厉害。"
                    "「我没偷那份乐谱。」他喘着气重复，像怕这句话在空气里蒸发。"
                    "可审判席的传唤并不在乎喘息：书记官把你的编号与证物栏对齐，要求你带着这本册子当庭出现——"
                    "否则协逃与共犯的界限，会在纸面上自动滑向更糟的那一格。"
                ),
            ),
        )
        healed = self.get_player().heal(17)
        self.add_message(
            f"碎纸从你指缝落下，像一场很小的雪。你深吸一口气，肩背松弛下来，生命回复了 {healed} 点。"
            "被通缉者低声说了句谢谢，声音哑得像很久没睡；你没有回答，只示意他别停步。"
            "风从通风口倒灌进来，带着消毒水与旧布景的味道；你听见不知何处有人笑了一声，又像是管道共鸣。"
            "那句低语贴着你耳廓擦过：「那你就替他付账。」——你分不清是威胁、预言，还是剧场本身在念旁白。"
        )
        return "Event Completed"

    def double_cross(self):
        self.register_story_choice(
            choice_flag=MOON_BOUNTY_DOUBLE,
            moral_delta=-1,
            consequences=self._build_moon_chain(
                route="double",
                battle_mode="random",
                chain_message=(
                    "前情：你给猎手一份「向东」的便条，又给安保一份「向西」的密报，把两边的耐心都换成金币落袋。"
                    "可剧场从不只养一套眼睛：当你以为自己在暗处拨弄线索时，走廊的镜面与监控孔也在回传你的倒影。"
                    "通缉令上的光纹闪了一下，像系统把某个标签从你身上扫过去——合作者、线人、搅局者，或者下一个目标。"
                ),
                chain_hint=(
                    "前情：假线索的尾款还没花完，你就发现自己被夹在两股怒气之间："
                    "一方骂你浪费追猎窗口，另一方怀疑你吞了真正的证物下落。"
                    "这扇门后没有谈判桌，只有先来后到的清算顺序；你唯一能确定的，是没人再愿意听你讲第三套故事。"
                ),
                verdict_hint=(
                    "前情：无论你让谁扑了空，审判庭的传唤都像迟到的收据——上面写着你曾接触过的每一方、每一笔交易痕迹。"
                    "他们不要听你辩解「我只是想让真相浮出来」；他们要你在席上把话说圆，"
                    "否则纸面会把你的位置从线人滑向共犯，再从共犯滑向替罪。"
                ),
            ),
        )
        p = self.get_player()
        gain = 48
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        p.take_damage(26)
        self.add_message(
            f"你把半真半假的路线、半新半旧的门牌号分别卖给猎手与安保，口袋一下子沉了 {gain}G。"
            "金币碰在一起的声音好听极了，却也像在给某个看不见的账本记页码。"
            "离场的路上，有人从暗处掷来一枚铁片擦过你肩胛——不是致命一击，却足够让你明白："
            "两边都开始把你当作可以牺牲的中间人。你翻滚卸力，仍被划出裂口，受到 26 点伤害。"
            "血腥味和剧场的灰尘混在一起；你舔了舔裂开的嘴角，忽然笑了一下——不是得意，是承认自己终于骑上了刀背。"
        )
        return "Event Completed"

    def _build_moon_chain(self, route, battle_mode, chain_message, chain_hint, verdict_hint):
        return [
            {
                "consequence_id": f"moon_chain_{route}_mid_battle",
                "effect_key": "moon_bounty_mid_battle",
                "chance": 1.0,
                "priority": 10,
                "trigger_door_types": ["EVENT", "MONSTER", "SHOP", "REWARD", "TRAP"],
                "payload": {
                    "route": route,
                    "battle_mode": battle_mode,
                    "consume_on_defeat": True,
                    "message": chain_message,
                    "hunter_hint": chain_hint,
                    "chain_followups": [
                        {
                            "consequence_id": f"moon_chain_{route}_force_verdict",
                            "effect_key": "force_story_event",
                            "chance": 1.0,
                            "trigger_door_types": ["EVENT"],
                            "payload": {
                                "event_key": "moon_verdict_event",
                                "hint": verdict_hint,
                                "message": "前情：中间战斗结束后，案卷被强制推送至审判庭。你必须先出庭，才有资格继续后续任务。",
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
        self.title = "月蚀审判"
        self.description = (
            "你一路追着月蚀通缉链来到剧场安保的审判席。书记官推来三份结案文书——"
            "每一份都关乎命运剧本回收案的最终定论，要你签名。"
        )
        diary_prelude = self._compose_diary_prelude()
        if diary_prelude:
            self.description = f"{self.description} {diary_prelude}"
        self.choices = [
            EventChoice("按规矩结案", self.file_clean),
            EventChoice("销毁证物", self.burn_records),
            EventChoice("反向勒索审判庭", self.extort_court),
        ]

    def _compose_diary_prelude(self):
        story = getattr(self.controller, "story", None)
        if not story or "moon_bounty_diary_obtained" not in getattr(story, "story_tags", set()):
            return ""
        source = getattr(story, "moon_bounty_diary_source", "")
        if source == "thief_body":
            return "你把战后搜出的旧日记本放在证物盘里：里面只记着一个父亲寻找走失女儿的日期与路线。"
        if source == "thief_testimony":
            return "你把被通缉者托付的旧日记本放在证物盘里：里面是他寻找走失女儿的记录，以及他反复写下的「我没偷那份命运的乐谱」。"
        return "你把一册磨损的旧日记本放在证物盘里，准备在审判中作为补充证词。"

    def _add_diary_court_remark(self):
        story = getattr(self.controller, "story", None)
        if not story or "moon_bounty_diary_obtained" not in getattr(story, "story_tags", set()):
            return
        source = getattr(story, "moon_bounty_diary_source", "")
        if source == "thief_body":
            self.add_message("你递上日记本。主审官快速翻阅后皱眉：'这只是一位父亲寻找女儿的私人记录。'")
        elif source == "thief_testimony":
            self.add_message("你递上日记本并转述大盗的自述。书记官记下笔录，却没有抬眼。")
        else:
            self.add_message("你递上日记本。书记官把它放进证物盘，翻了两页就合上。")
        self.add_message("主审官冷声宣布：'这本日记不能证明命运乐章失窃案的真伪，只能作为背景材料。'")
        self.add_message("旁听席有人低声提到其他证据仍在复核，但很快被法槌压了下去。")

    def file_clean(self):
        self._add_diary_court_remark()
        round_count = max(0, int(getattr(self.controller, "round_count", 0)))
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        self.register_story_choice(
            choice_flag=MOON_VERDICT_CLEAN,
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
                                    "gold": max(25, min_gold),
                                    "heal": max(12, min_heal),
                                    "message": "前情：你选择了规范结案并留档。审判庭没有再追责，甚至给了你一笔办案补贴。",
                                },
                            }
                        ],
                    },
                }
            ],
        )
        p = self.get_player()
        gain = 12
        min_gold = int((round_count / 3) * rng().uniform(0.5, 1.0))
        gain = max(gain, min_gold)
        p.gold += gain
        heal_amt = 6
        min_heal = int((round_count / 3) * rng().uniform(0.5, 1.0))
        heal_amt = max(heal_amt, min_heal)
        healed = p.heal(heal_amt)
        self.add_message(f"你签了字。书记官把印泥按在卷轴边缘，先发了 {gain}G 办案费，你也恢复了 {healed} 点生命。")
        return "Event Completed"

    def burn_records(self):
        self._add_diary_court_remark()
        self.register_story_choice(
            choice_flag=MOON_VERDICT_BURNED,
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
                                "chance": 0.65,
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
        self._add_diary_court_remark()
        self.register_story_choice(
            choice_flag=MOON_VERDICT_EXTORTED,
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

