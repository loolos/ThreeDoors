"""见 models.events 包说明。"""
from models.status import StatusName
from models.story_flags import (
    ELF_GRUDGE_CAMP_MERCENARY,
    ELF_GRUDGE_CAMP_REFUSED_HELP,
    ELF_GRUDGE_EPILOGUE_BURNED,
    ELF_GRUDGE_HEIST_BETRAYED,
    ELF_GRUDGE_HEIST_SIDE_ROUTE,
    ELF_GRUDGE_HUNTER_FLED,
    ELF_GRUDGE_HUNTER_LOOT_GRAB,
    ELF_GRUDGE_INTRO_FAKE_GUARD,
    ELF_GRUDGE_MAP_SOLD_OUT,
    ELF_GRUDGE_ROOFTOP_SNEAK,
    ELF_GRUDGE_SHADOW_THREATEN,
    ELF_GRUDGE_STAGE_REFUSED,
    ELF_GRUDGE_TRAP_ORDERED,
    ELF_HUNTER_GATE_TEAM_UP,
    ELF_SIDE_REG,
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
    if not hasattr(story, "elf_key_obtained"):
        story.elf_key_obtained = False
    return story


def _record_elf_grudge(controller, flag: str) -> None:
    """记录玩家在飞贼支线上的具体选择，供终局清算战台词引用。"""
    story = _get_elf_chain_state(controller)
    if story is not None and hasattr(story, "choice_flags"):
        story.choice_flags.add(flag)


def _adjust_elf_relation(controller, delta):
    story = _get_elf_chain_state(controller)
    if story is None:
        return 0
    story.elf_relation = max(-6, min(6, int(story.elf_relation) + int(delta)))
    return story.elf_relation


def _set_elf_key_obtained(controller, obtained):
    story = _get_elf_chain_state(controller)
    if story is None:
        return None
    value = bool(obtained)
    story.elf_key_obtained = value
    if value:
        story.story_tags.add("elf_key_obtained")
    else:
        story.story_tags.discard("elf_key_obtained")
    return story


def _elf_ratio(player, ratio, source="hp", minimum=1):
    if source == "gold":
        base = max(0, int(getattr(player, "gold", 0)))
    elif source == "atk":
        base = max(1, int(getattr(player, "_atk", getattr(player, "atk", 1))))
    else:
        base = max(1, int(getattr(player, "hp", 1)))
    return max(minimum, int(round(base * max(0.0, float(ratio)))))


def _elf_grant_dynamic_boon(controller):
    """飞贼正向奖励池：不再总是加攻击，改为加血/加攻/给道具三选一。"""
    p = getattr(controller, "player", None)
    if p is None:
        return "她本想给你点东西，却只剩一句'下次。'"

    roll = rng().random()
    if roll < 0.34:
        atk_up = _elf_ratio(p, 0.08, "atk")
        p.change_base_atk(atk_up)
        return f"她把短刃磨得锋利之后丢给你道：'这把刀能帮你更快地砍死怪物。'（基础攻击 +{atk_up}）。"

    if roll < 0.68:
        heal = _elf_ratio(p, 0.14, "hp")
        p.hp = p.hp + heal
        return f"她把止血粉和绑带塞给你，顺手重新缠好护腕，然后道：'你受伤了，先包扎一下。'（+{heal}HP）。"

    item = mk_reward_item()
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
        rng().shuffle(story.elf_middle_queue)

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
    consequence_id = f"elf_chain_force_{next_key}_{current_round}_{rng().randint(1, 9999)}"
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
    TRIGGER_BASE_PROBABILITY = 0.08  # 在随机池权重层统一做 3× 提升
    MIN_TRIGGER_ROUND = 6

    @classmethod
    def is_trigger_condition_met(cls, controller):
        story = _get_elf_chain_state(controller)
        if story is not None:
            if bool(getattr(story, "elf_chain_started", False)):
                return False
            if bool(getattr(story, "elf_chain_ended", False)):
                return False
        return super().is_trigger_condition_met(controller)

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "银羽飞贼"
        self.description = (
            f"你推开门，门后是一条烛火摇曳的暗巷。"
            f"一名精灵背靠砖墙，指尖转着匕首，抬眼打量你。"
            f"她笑了笑：'我叫{ELF_THIEF_NAME}，这个地方到处都是财宝，但也到处都是机关和怪物。'"
            f"'但我以后可以教你两手，想学的话就拿点学费来？'"
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
        cost = _elf_ratio(p, 0.12, "gold")
        lost = min(p.gold, cost)
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"{ELF_THIEF_NAME}毫不客气地拿走干粮与盘缠，你少了 {lost} 金币；她抛来一枚银羽徽记：'这是我的标志，别死太早。'")
        self._start_chain()
        return "Event Completed"

    def challenge_duel(self):
        dmg = _elf_ratio(self.get_player(), 0.08, "hp")
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"你们点到为止地过了几招，你吃了 {dmg} 点伤害，她却笑得更开心。")
        self._start_chain()
        return "Event Completed"

    def fake_guard(self):
        p = self.get_player()
        lost = min(p.gold, _elf_ratio(p, 0.1, "gold"))
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, -2)
        _record_elf_grudge(self.controller, ELF_GRUDGE_INTRO_FAKE_GUARD)
        self.add_message(f"她反手把你的钱袋顺走 {lost}G：'冒充守卫前，先把靴子擦亮。'")
        self._start_chain()
        return "Event Completed"


class ElfShadowMarkEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "银羽暗号"
        self.description = (
            "你正要选一扇事件门时，发现门框背面有熟悉的银羽刻痕——那是她的记号，下面有一行小字：「今天不偷你，聊聊」。"
            "你推开门，等了一会，她从门后的阴影里走出来，没动你身上的东西，只冲你抬了抬下巴。"
            f"{ELF_THIEF_NAME}:'在这个迷宫里也看到不少有趣的东西吧？讲讲？'"
        )
        self.choices = [
            EventChoice("和她深入交换目前所知情报", self.share_info),
            EventChoice("追问她真实目的", self.ask_intent),
            EventChoice("放冷话：再见就算账", self.threaten),
        ]

    def share_info(self):
        gain = _elf_ratio(self.get_player(), 0.1, "gold")
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"你们互通了冒险路线的情报，她提醒你绕开最毒的陷阱层；你按图摸到遗漏的财宝（+{gain}G）。")
        _schedule_next_elf_event(self.controller, "elf_shadow_mark_event")
        return "Event Completed"

    def ask_intent(self):
        heal = _elf_ratio(self.get_player(), 0.12, "hp")
        self.get_player().hp = self.get_player().hp + heal
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"她丢来药包：'目的？你得先活下来，才配知道目的。'（+{heal}HP）")
        _schedule_next_elf_event(self.controller, "elf_shadow_mark_event")
        return "Event Completed"

    def threaten(self):
        p = self.get_player()
        lost = min(p.gold, _elf_ratio(p, 0.08, "gold"))
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, -2)
        _record_elf_grudge(self.controller, ELF_GRUDGE_SHADOW_THREATEN)
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
        heal = _elf_ratio(self.get_player(), 0.1, "hp")
        self.get_player().hp = self.get_player().hp + heal
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"她看穿你在放水，却还是把跌打药塞进你怀里（+{heal}HP）。")
        _schedule_next_elf_event(self.controller, "elf_rooftop_duel_event")
        return "Event Completed"

    def cheap_shot(self):
        dmg = _elf_ratio(self.get_player(), 0.1, "hp")
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -3)
        _record_elf_grudge(self.controller, ELF_GRUDGE_ROOFTOP_SNEAK)
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
            EventChoice("把地图卖了给商人", self.sell_both),
        ]

    def trust_map(self):
        gain = _elf_ratio(self.get_player(), 0.12, "gold")
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"根据她的标注，顺路摸到一处被忽视的补给箱（+{gain}G）。")
        _schedule_next_elf_event(self.controller, "elf_fake_map_event")
        return "Event Completed"

    def remap(self):
        boon_text = _elf_grant_dynamic_boon(self.controller)
        _adjust_elf_relation(self.controller, 0)
        self.add_message(f"你把她的标注全改成自己的记号，路线更稳更实用。{boon_text}")
        _schedule_next_elf_event(self.controller, "elf_fake_map_event")
        return "Event Completed"

    def sell_both(self):
        gain = _elf_ratio(self.get_player(), 0.18, "gold")
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, -2)
        _record_elf_grudge(self.controller, ELF_GRUDGE_MAP_SOLD_OUT)
        self.add_message(f"你把图卖给商人，赚了 {gain}G，也让她记下你这笔账。")
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
        heal = _elf_ratio(self.get_player(), 0.1, "hp")
        self.get_player().hp = self.get_player().hp + heal
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
        dmg = _elf_ratio(self.get_player(), 0.07, "hp")
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -1)
        _record_elf_grudge(self.controller, ELF_GRUDGE_STAGE_REFUSED)
        self.add_message(f"她把假人踢回门后，你躲闪不及被门板刮到。'行，别怪我以后不救场。'（-{dmg}HP）")
        _schedule_next_elf_event(self.controller, "elf_monster_stage_event")
        return "Event Completed"


class ElfNightCampEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "夜营火谈"
        self.description = (
            "门后是一处坍塌神像的背风面，她生了堆小火，正在烤一只火鸡。"
            "她示意你坐下，沉默了很久才开口：追她的不是普通赏金客，而是同一个组织里被她反咬过的人。"
            "她当年偷走了他们的暗账，里面记着谁给怪物送祭品，以及整个世界的各种秘密。"
            "现在那群人放话：要么拿回账册，要么把见过账册的人全埋进地底。"
            "火光映着她的侧脸，她把一半烤肉推给你：'所以你今晚要选，跟我一起扛下这些秘密对付这些坏事的家伙，我会付你钱的，以后你可以当没见过我。'"
        )
        self.choices = [
            EventChoice("站她这边：一起对付追捕她的人", self.promise_help),
            EventChoice("谈价接单：先收钱再帮忙", self.ask_payment),
            EventChoice("拒绝帮忙：之后各走各路", self.prepare_solo),
        ]

    def promise_help(self):
        heal = _elf_ratio(self.get_player(), 0.14, "hp")
        self.get_player().hp = self.get_player().hp + heal
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"她难得正经地点头，把多烤的肉递给你：'好，我也记你一份人情。'（+{heal}HP）")
        _schedule_next_elf_event(self.controller, "elf_night_camp_event")
        return "Event Completed"

    def ask_payment(self):
        gain = _elf_ratio(self.get_player(), 0.15, "gold")
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, -1)
        _record_elf_grudge(self.controller, ELF_GRUDGE_CAMP_MERCENARY)
        self.add_message(f"她扔来 {gain}G：'佣兵价，童叟无欺。'语气却冷了半分。")
        _schedule_next_elf_event(self.controller, "elf_night_camp_event")
        return "Event Completed"

    def prepare_solo(self):
        boon_text = _elf_grant_dynamic_boon(self.controller)
        _adjust_elf_relation(self.controller, -2)
        _record_elf_grudge(self.controller, ELF_GRUDGE_CAMP_REFUSED_HELP)
        self.add_message(f"你决定单干，她没拦你，只把一份'不欠人情'的补给甩了过来。{boon_text}")
        _schedule_next_elf_event(self.controller, "elf_night_camp_event")
        return "Event Completed"


class ElfTrapRescueEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "陷阱回廊"
        self.description = (
            "你刚踏进这条走廊就触发了连环机关，绞索从梁上落下，正往你身上收紧，把你一只脚吊了起来，尖刺机关正在靠近你，形势危急。"
            "她从梁上倒挂下来，手里捏着匕首，似笑非笑：'我救不救你啊？'"
        )
        self.choices = [
            EventChoice("好言相劝，求求放人", self.apologize),
            EventChoice("命令她立刻救人", self.order_her),
            EventChoice("自己挣脱，不求她", self.break_free),
        ]

    def _rescue_outcome(self):
        rel = getattr(_get_elf_chain_state(self.controller), "elf_relation", 0)
        if rel >= 2:
            heal = _elf_ratio(self.get_player(), 0.16, "hp")
            self.get_player().hp = self.get_player().hp + heal
            self.add_message(f"她精准切断绞索，还顺手包扎了你的手腕（+{heal}HP）。")
        elif rel <= -2:
            dmg = _elf_ratio(self.get_player(), 0.14, "hp")
            self.get_player().take_damage(dmg)
            self.add_message(f"她慢了半拍才出手，你被机关刮得遍体鳞伤（-{dmg}HP）。")
        else:
            dmg = _elf_ratio(self.get_player(), 0.08, "hp")
            self.get_player().take_damage(dmg)
            self.add_message(f"她把你拉出陷阱，但你还是被铁刺擦伤（-{dmg}HP）。")

    def apologize(self):
        _adjust_elf_relation(self.controller, 2)
        self._rescue_outcome()
        _schedule_next_elf_event(self.controller, "elf_trap_rescue_event")
        return "Event Completed"

    def order_her(self):
        _adjust_elf_relation(self.controller, -2)
        _record_elf_grudge(self.controller, ELF_GRUDGE_TRAP_ORDERED)
        self._rescue_outcome()
        _schedule_next_elf_event(self.controller, "elf_trap_rescue_event")
        return "Event Completed"

    def break_free(self):
        dmg = _elf_ratio(self.get_player(), 0.12, "hp")
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
        self.add_message(f"你们背靠背清掉前排追兵，她在喘息间把战利品丢给你，道：'你的那份。'{boon_text}")
        # 你选择并肩作战后，会引来“来复仇的追兵”追猎者，作为后续伏击战（revenge_ambush）。
        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        self.register_story_choice(
            choice_flag=ELF_HUNTER_GATE_TEAM_UP,
            consequences=[
                {
                    "consequence_id": "elf_hunter_gate_team_up_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.7,
                    "trigger_door_types": ["MONSTER"],
                    "min_round": current_round + 1,
                    "max_round": current_round + 7,
                    "force_on_expire": True,
                    "force_door_type": "MONSTER",
                    "payload": {
                        "force_hunter": True,
                        "hunter_hint": "门后更紧的呼吸声贴上来了，追兵已改写了你下一步的去路。",
                        "message": "你刚收起战利品，之前追捕银羽的追兵的复仇已经堵在门缝里：这一次，他们不打算放过你。",
                        "log_trigger": "她不再只是被拖拽进战圈的影子——你选了帮忙，复仇者也把你算进账本里。",
                    },
                }
            ],
        )
        _schedule_next_elf_event(self.controller, "elf_hunter_gate_event")
        return "Event Completed"

    def selfish_fight(self):
        gain = _elf_ratio(self.get_player(), 0.14, "gold")
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, -1)
        _record_elf_grudge(self.controller, ELF_GRUDGE_HUNTER_LOOT_GRAB)
        self.add_message(f"你抢下战利品 {gain}G，她虽然没说什么，但眼神变冷。")
        _schedule_next_elf_event(self.controller, "elf_hunter_gate_event")
        return "Event Completed"

    def run_away(self):
        dmg = _elf_ratio(self.get_player(), 0.15, "hp")
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, -3)
        _record_elf_grudge(self.controller, ELF_GRUDGE_HUNTER_FLED)
        self.add_message(f"你撤得太急，背后中箭（-{dmg}HP）。她在远处骂你胆小鬼。")
        _schedule_next_elf_event(self.controller, "elf_hunter_gate_event")
        return "Event Completed"


class ElfFinalHeistEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "双人盗案"
        self.description = (
            f"她留下的最后一次暗号把你引到钟塔下的旧档案库，这大概就是追她的人的大本营了。"
            f"你刚到，就看见{ELF_THIEF_NAME}把几张纸摊在地上：外圈巡逻表、内层机关图、以及守卫换岗钟点。"
            f"她快速说明：正门有重甲兵和弩手；侧井能绕进宝藏室但会触发毒针机关；但你在想，如果你此刻出卖她，安保或许也会给你悬赏。"
            f"她盯着你：'你来定，按我的线稳进稳出，赌一把高风险快线？'"
        )
        self.choices = [
            EventChoice("按她的路线走：低风险潜入并平分赃款", self.follow_plan),
            EventChoice("改走侧井快线：多拿一票但硬吃反噬", self.change_plan),
            EventChoice("敲警铃卖掉她：拿悬赏", self.betray),
        ]

    def follow_plan(self):
        gain = _elf_ratio(self.get_player(), 0.18, "gold")
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 2)
        self.add_message(f"你们按巡逻空窗潜入，避开正门火力，平稳带出不少金子和宝物；你分到 {gain}G。她笑说：'这次你真像搭档。'")
        _schedule_next_elf_event(self.controller, "elf_final_heist_event")
        return "Event Completed"

    def change_plan(self):
        gain = _elf_ratio(self.get_player(), 0.14, "gold")
        dmg = _elf_ratio(self.get_player(), 0.1, "hp")
        self.get_player().gold += gain
        self.get_player().take_damage(dmg)
        _adjust_elf_relation(self.controller, 1)
        _record_elf_grudge(self.controller, ELF_GRUDGE_HEIST_SIDE_ROUTE)
        self.add_message(f"你强行改走侧井快线，确实多抄到一批现银，但触发了毒针与弩机（+{gain}G，-{dmg}HP）。")
        _schedule_next_elf_event(self.controller, "elf_final_heist_event")
        return "Event Completed"

    def betray(self):
        gain = _elf_ratio(self.get_player(), 0.2, "gold")
        backlash = _elf_ratio(self.get_player(), 0.06, "hp")
        self.get_player().gold += gain
        self.get_player().take_damage(backlash)
        _adjust_elf_relation(self.controller, -4)
        _record_elf_grudge(self.controller, ELF_GRUDGE_HEIST_BETRAYED)
        self.add_message(f"你敲响警铃换来安保悬赏 {gain}G，但混战中也被流矢划伤（-{backlash}HP）。她被押走前只留下一句：'你最好永远别落单。'")
        _schedule_next_elf_event(self.controller, "elf_final_heist_event")
        return "Event Completed"


class ElfEpilogueEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "银羽余响"
        self.rel = getattr(_get_elf_chain_state(controller), "elf_relation", 0)
        if self.rel >= 2:
            self.description = (
                "门后她倚在一扇暗门旁，把一把旧钥匙稳稳递到你手里："
                "'这是我之前偷来的宝物藏匿点。等你看到一扇带着我徽记的门，就用它打开。'"
            )
            self.choices = [
                EventChoice("接过钥匙并记下位置", self.accept_bond),
                EventChoice("礼貌道别：各走各路", self.close_clean),
                EventChoice("怀疑有诈，当场拒绝", self.burn_bridge),
            ]
        elif self.rel <= -2:
            self.description = (
                "门后只有她冷冷的笑声从阴影里传来："
                "'好好看看你自己吧。你的一举一动，到底是你在选，还是一直被谁牵着走？'"
                "'又或者，你只是照着某个早就写好的剧本在演。'"
            )
            self.choices = [
                EventChoice("压下火气，追问她话里的线索", self.accept_bond),
                EventChoice("不再纠缠，沉默离开", self.close_clean),
                EventChoice("正面回呛，彻底决裂", self.burn_bridge),
            ]
        else:
            self.description = (
                "门后她礼貌地向你点头道别：'这一路多谢照应。'"
                "临走前她压低声音提醒你：'这个世界有些地方不太对劲，像是在一遍又一遍地重复。'"
            )
            self.choices = [
                EventChoice("认真记下提醒，与她友好作别", self.close_clean),
                EventChoice("收下补给，平静分开", self.close_clean),
                EventChoice("不信她的提醒，冷淡转身", self.burn_bridge),
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
        rel = getattr(story, "elf_relation", 0) if story else self.rel
        _set_elf_key_obtained(self.controller, rel >= 2)
        boon_text = _elf_grant_dynamic_boon(self.controller)
        extra_heal = _elf_ratio(self.get_player(), 0.08 if rel >= 2 else 0.05, "hp")
        self.get_player().hp = self.get_player().hp + extra_heal
        if rel >= 2:
            msg = "你收好钥匙，她点头：'门会认得你。'"
        elif rel <= -2:
            msg = "你没有回嘴，只把她话里的每个字都记住。阴影里传来一声轻笑：'至少你终于开始自己想了。'"
        else:
            msg = "你向她颔首致意，把那句'重复'牢牢记下。她回了你一个克制却真诚的眼神。"
        self.add_message(f"{msg} 临别前她还是给你留了点照应（+{extra_heal}HP）。{boon_text}")
        return "Event Completed"

    def close_clean(self):
        story = self._mark_elf_global_outcome(
            "neutral",
            extra_tags={"ending_hook:elf_neutral", "ending_hook:lone_path"},
        )
        rel = getattr(story, "elf_relation", 0) if story else self.rel
        _set_elf_key_obtained(self.controller, rel >= 2)
        gain = _elf_ratio(self.get_player(), 0.12 if rel >= 0 else 0.08, "gold")
        self.get_player().gold += gain
        if rel >= 2:
            msg = "你把钥匙小心收起，却没有再多问。你们在岔路口各自转身。"
        elif rel <= -2:
            msg = "你没有再回应她的嘲讽，只把这场对话留在身后。"
        else:
            msg = "你们礼貌告别，谁都没有再多说一句。"
        self.add_message(f"{msg} 你收下路费与补给（+{gain}G）。")
        return "Event Completed"

    def burn_bridge(self):
        story = self._mark_elf_global_outcome(
            "hostile",
            extra_tags={"ending_hook:elf_hostile", "ending_hook:hunted"},
        )
        _record_elf_grudge(self.controller, ELF_GRUDGE_EPILOGUE_BURNED)
        rel = getattr(story, "elf_relation", 0) if story else self.rel
        _set_elf_key_obtained(self.controller, False)
        dmg = _elf_ratio(self.get_player(), 0.12 if rel > -2 else 0.16, "hp")
        self.get_player().take_damage(dmg)
        if rel >= 2:
            msg = "你当场推开她递来的钥匙，空气瞬间冷了下去。"
        elif rel <= -2:
            msg = "你被她的嘲讽彻底激怒，冲着阴影回敬了最狠的话。"
        else:
            msg = "你不信她关于'重复'的提醒，转身就走。"
        self.add_message(f"{msg} 这份敌意很快化作追击，你在撤离时被暗箭擦伤（-{dmg}HP）。")
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
        choice_flag=ELF_SIDE_REG,
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
        choice_flag=ELF_SIDE_REG,
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
        choice_flag=ELF_SIDE_REG,
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
        choice_flag=ELF_SIDE_REG,
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
        dmg = _elf_ratio(self.get_player(), 0.1, "hp")
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
            item = mk_random_item()
            cost = max(8, int(item.cost * (0.9 + rng().random() * 0.3)))
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
        gain = _elf_ratio(self.get_player(), 0.08, "gold")
        self.get_player().gold += gain
        _adjust_elf_relation(self.controller, 0)
        self.add_message(f"你当众戳穿把戏，她悻悻退了你一点'封口费'（+{gain}G）。'算你狠。'")
        return "Event Completed"

    def pretend_pay(self):
        p = self.get_player()
        lost = min(p.gold, _elf_ratio(p, 0.12, "gold"))
        p.gold = max(0, p.gold - lost)
        _adjust_elf_relation(self.controller, 1)
        self.add_message(f"你故意付了钱，拿了假货就走，她收下 {lost}G 时眼神复杂：'谢谢惠顾。'")
        return "Event Completed"

    def walk_away(self):
        _adjust_elf_relation(self.controller, -1)
        self.add_message("你扭头离开，她在背后嘀咕：'没劲。'")
        return "Event Completed"

