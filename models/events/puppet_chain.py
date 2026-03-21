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

PUPPET_KIND_PERSONA_NAME = "绒心"
PUPPET_DARK_PERSONA_NAME = "裂齿"


def _get_puppet_chain_state(controller):
    story = getattr(controller, "story", None)
    if story is None:
        return None
    if not hasattr(story, "puppet_evil_value"):
        story.puppet_evil_value = 55
    if not hasattr(story, "puppet_kind_persona_name"):
        story.puppet_kind_persona_name = PUPPET_KIND_PERSONA_NAME
    if not hasattr(story, "puppet_dark_persona_name"):
        story.puppet_dark_persona_name = PUPPET_DARK_PERSONA_NAME
    if not hasattr(story, "puppet_side_registered"):
        story.puppet_side_registered = False
    return story


def _adjust_puppet_evil_value(controller, delta):
    story = _get_puppet_chain_state(controller)
    if story is None:
        return 55
    current = int(getattr(story, "puppet_evil_value", 55))
    next_val = max(0, min(100, current + int(delta)))
    story.puppet_evil_value = next_val
    story.story_tags.add(f"puppet_evil_bucket:{(next_val // 10) * 10}")
    return next_val


def _get_puppet_persona_names(controller):
    story = _get_puppet_chain_state(controller)
    if story is None:
        return PUPPET_KIND_PERSONA_NAME, PUPPET_DARK_PERSONA_NAME
    return (
        getattr(story, "puppet_kind_persona_name", PUPPET_KIND_PERSONA_NAME),
        getattr(story, "puppet_dark_persona_name", PUPPET_DARK_PERSONA_NAME),
    )


def build_puppet_final_boss_payload(controller, phase2_burst_heal_ratio=None, **overrides):
    """构建木偶最终 Boss 的 effect payload，供正式流程与测试 gate 共用。
    phase2_burst_heal_ratio 若传入则覆盖默认 0.42；overrides 中键值会合并进 payload。"""
    story = _get_puppet_chain_state(controller)
    kind_name, dark_name = _get_puppet_persona_names(controller)
    evil_value = int(getattr(story, "puppet_evil_value", 55)) if story is not None else 55
    payload = {
        "boss_name": f"{dark_name}·堕暗机偶",
        "base_hp": 980,
        "base_atk": 96,
        "phase2_burst_heal_ratio": 0.42,
        "phase2_min_hp_ratio": 1.0,
        "tier": 6,
        "evil_value": evil_value,
        "kind_persona_name": kind_name,
        "dark_persona_name": dark_name,
        "kind_heal": 18,
        "no_side_event_message": "你几乎没碰到那些支线干预，它的核心参数按默认流程直接结算，战斗走势更加不可预测。",
        "kind_flags": [
            "puppet_intro_hide",
            "puppet_signal_soft",
            "puppet_kind_echo_trust",
            "puppet_kind_echo_comfort",
            "puppet_rift_kind",
            "puppet_descent_patch",
        ],
        "dark_flags": [
            "puppet_intro_blackout",
            "puppet_intro_decoy",
            "puppet_signal_resell",
            "puppet_kind_echo_exploit",
            "puppet_rift_dark",
            "puppet_descent_cut_emotion",
            "puppet_descent_dark_feed",
        ],
        "hint": "前情：核心下潜结束，最深处那扇门正在锁定。门后是木偶黑暗人格本体。",
        "message": "核心阀门一节节闭合，走廊尽头只剩一扇被红线封死的门。你知道，门后就是它的本体。",
        "log_trigger": "你打算要推开门，突然发现整条走廊被红色封锁线覆盖。正要推开的一刹那，整个走廊都开始震动，三扇门在黑暗中重组成了一个巨大的机械人偶。",
        "kind_awaken_message": f"你一路对蓝光侧的选择在最后一秒有了回响。{kind_name}短暂夺回控制，机偶眼中闪过一丝蓝光，替你压低了黑暗核心输出。",
        "dark_overload_message": f"你先前的选择不断喂养黑暗协议，{dark_name}彻底接管本体，气势瞬间暴涨。",
        "neutral_message": f"{kind_name}与{dark_name}仍在互相撕扯，但黑暗侧握着主导权。机偶缓缓抬头，战斗不可避免。",
    }
    if phase2_burst_heal_ratio is not None:
        payload["phase2_burst_heal_ratio"] = phase2_burst_heal_ratio
    payload.update(overrides)
    return payload


def _schedule_puppet_mainline_event(controller, from_stage, next_event_key, hint, message):
    story = _get_puppet_chain_state(controller)
    if story is None:
        return
    current_round = max(0, int(getattr(controller, "round_count", 0)))
    cid = f"puppet_mainline_{from_stage}_to_{next_event_key}"
    story.register_consequence(
        choice_flag=f"puppet_mainline:{from_stage}",
        consequence_id=cid,
        effect_key="force_story_event",
        chance=1.0,
        priority=120,
        trigger_door_types=["EVENT"],
        min_round=current_round + 20,
        max_round=current_round + 30,
        force_on_expire=True,
        force_door_type="EVENT",
        required_flags={"puppet_arc_active"},
        forbidden_flags={"consumed:puppet_mainline_final_boss_gate"},
        payload={
            "event_key": next_event_key,
            "hint": hint,
            "message": message,
            "log_trigger": "你刚要按原计划开门，墙内警报突然改写路线，门框上的编号突然消失不见，变成了一段乱码。",
        },
    )


def _emit_puppet_audio_cue(controller, cue="event"):
    if controller is None or not hasattr(controller, "add_message"):
        return
    cue_map = {
        "event": "远处传来发条轻响与失真童谣。",
        "rift": "双声道人格在耳边重叠回响。",
        "core": "核心井深处传来低频轰鸣。",
    }
    controller.add_message(cue_map.get(cue, cue_map["event"]))


def _register_puppet_side_consequences(controller):
    story = _get_puppet_chain_state(controller)
    if story is None:
        return
    if bool(getattr(story, "puppet_side_registered", False)):
        return
    story.puppet_side_registered = True

    common_required = {"puppet_arc_active"}
    common_forbidden = {"consumed:puppet_mainline_final_boss_gate"}

    story.register_consequence(
        choice_flag="puppet_side_reg",
        consequence_id="puppet_side_minion_once",
        effect_key="puppet_side_minion",
        chance=0.32,
        priority=86,
        trigger_door_types=["MONSTER", "EVENT"],
        required_flags=common_required,
        forbidden_flags=common_forbidden,
        payload={
            "hunter_hint": "金属摩擦声忽远忽近，像有一台小型追猎体在你周围绕圈校准。",
            "message": "门缝刚开，一只锈迹斑斑的小木偶就扑了出来，逼得你当场应战。",
            "log_trigger": "你手刚碰到门把，门内先传来急促抓挠声，紧接着整道门被反锁，过了一段时间才缓缓打开。",
            "evil_value_delta": 8,
        },
    )

    story.register_consequence(
        choice_flag="puppet_side_reg",
        consequence_id="puppet_side_signal_once",
        effect_key="force_story_event",
        chance=0.26,
        priority=87,
        trigger_door_types=["EVENT"],
        required_flags={"puppet_arc_active", "consumed:puppet_side_minion_once"},
        forbidden_flags=common_forbidden,
        payload={
            "event_key": "puppet_signal_event",
            "hint": "前情：你此前拆掉了锈迹斑斑的小木偶，墙缝里开始回放失真童谣。",
            "message": "你之前摆脱的追猎偶，导致失真信号占据了门系统，下一扇门被强制改写成信号室。",
            "log_trigger": "你按下门把，忽然听到墙里的童谣倒放，门牌号被篡改成信号室编号。原路线被系统强制覆盖，你被拖进了木偶留下的信号节点。",
            "evil_value_delta": -5,
        },
    )

    story.register_consequence(
        choice_flag="puppet_side_reg",
        consequence_id="puppet_side_shop_once",
        effect_key="black_market_markup",
        chance=0.24,
        priority=80,
        trigger_door_types=["SHOP"],
        required_flags=common_required,
        forbidden_flags=common_forbidden,
        payload={
            "ratio": 1.18,
            "message": "你之前和木偶的交互使得被黑市识别为高风险污染样本，商人当场给你上调了风险价。",
            "log_trigger": "你本想走普通商店，但门后柜台亮起红灯，显示“污染样本处理费”。",
            "evil_value_delta": 6,
        },
    )

    story.register_consequence(
        choice_flag="puppet_side_reg",
        consequence_id="puppet_side_trap_once",
        effect_key="shrine_curse",
        chance=0.24,
        priority=81,
        trigger_door_types=["TRAP", "EVENT"],
        required_flags=common_required,
        forbidden_flags=common_forbidden,
        payload={
            "duration": 1,
            "message": "木偶病毒噪声短暂劫持了你的节拍，陷阱区里你的动作慢了半拍。",
            "log_trigger": "你脚下地砖突然翻转，原门被机关吞没，新的出口只剩陷阱回廊。选门失效，你被强行送进了机关线。",
            "evil_value_delta": 7,
        },
    )

    story.register_consequence(
        choice_flag="puppet_side_reg",
        consequence_id="puppet_side_reward_once",
        effect_key="treasure_marked_item",
        chance=0.22,
        priority=79,
        trigger_door_types=["REWARD"],
        required_flags=common_required,
        forbidden_flags=common_forbidden,
        payload={
            "item_key": "barrier",
            "gold_bonus": 14,
            "message": "因为和木偶的相遇，一段蓝光子程序提前改写了宝物内容。",
            "log_trigger": "你选中的门被机械臂贴上“样本回收”标签。路线被木偶链路短暂劫持，你被迫先处理这一处事件。",
            "evil_value_delta": -8,
        },
    )

    story.register_consequence(
        choice_flag="puppet_side_reg",
        consequence_id="puppet_side_kind_echo_once",
        effect_key="force_story_event",
        chance=0.24,
        priority=88,
        trigger_door_types=["EVENT"],
        required_flags=common_required,
        forbidden_flags=common_forbidden,
        payload={
            "event_key": "puppet_kind_echo_event",
            "hint": "前情：一束细蓝光正在门后等你回应。",
            "message": "你伸手推门时，耳边忽然响起一句轻轻的“别怕”，门牌同步重写成蓝眼回声节点。",
            "log_trigger": "你原本想开别的门，门框却渗出蓝线，把你拉进了善良人格的求援频道。你选的门在蓝光照射下变成了一扇传送门。",
            "evil_value_delta": -4,
        },
    )


class PuppetAbandonmentEvent(Event):
    """木偶主线起始：仅能规避冲突。"""
    TRIGGER_BASE_PROBABILITY = 0.065

    @classmethod
    def is_trigger_condition_met(cls, controller):
        story = getattr(controller, "story", None)
        if story is not None:
            outcome = str(getattr(story, "puppet_final_outcome", "")).strip()
            if outcome in ("defeated", "escaped"):
                return False
            tags = getattr(story, "story_tags", set())
            if "ending:puppet_final_defeated" in tags or "ending:puppet_final_escape_recorded" in tags:
                return False
        return cls.is_unlocked(controller, min_round=10, min_stage=1)

    @classmethod
    def get_trigger_probability(cls, controller):
        round_count = max(0, int(getattr(controller, "round_count", 0)))
        return min(0.2, cls.TRIGGER_BASE_PROBABILITY + min(0.1, round_count * 0.004))

    def __init__(self, controller):
        super().__init__(controller)
        kind_name, dark_name = _get_puppet_persona_names(controller)
        self.title = "弃线木偶"
        self.description = (
            "你在昏暗走廊尽头看见一具被丢弃的木偶——它曾是的戏剧原定的主演，但他现在并不知道自己是谁以及该做什么，只是一味游荡。"
            f"胸口还挂着半截编号牌，屏幕闪烁着两行人格标签：蓝光侧【{kind_name}】、红噪侧【{dark_name}】。"
            "它在黑暗中游荡，碰到障碍物就一拳砸裂，你确认现在绝不能正面和它对抗。"
        )
        self.choices = [
            EventChoice("钻进井盖，潜行躲避", self.hide_in_shaft),
            EventChoice("拉闸熄灯，趁黑撤离", self.cut_power_and_escape),
            EventChoice("丢出诱饵芯片，反向引开它", self.throw_decoy),
        ]

    def _start_arc(self, route, evil_delta, moral_delta, msg):
        story = _get_puppet_chain_state(self.controller)
        if story is not None:
            story.story_tags.add("puppet_arc_active")
            story.choice_flags.add(f"puppet_intro_{route}")
        _adjust_puppet_evil_value(self.controller, evil_delta)
        self.register_story_choice(choice_flag=f"puppet_intro_{route}", moral_delta=moral_delta)
        _register_puppet_side_consequences(self.controller)
        _schedule_puppet_mainline_event(
            self.controller,
            from_stage="intro",
            next_event_key="puppet_persona_rift_event",
            hint="前情：你侥幸甩开了弃线木偶，但墙后仍回荡着蓝红交替的心跳。",
            message="前情提要：你此前从弃线木偶手下脱身了，然而木偶那黑暗的人格裂隙并未消失。",
        )
        self.add_message(msg)
        return "Event Completed"

    def hide_in_shaft(self):
        _emit_puppet_audio_cue(self.controller, "event")
        p = self.get_player()
        if rng().random() < 0.55:
            heal_amt = rng().randint(4, 8)
            heal = p.heal(heal_amt)
            evil_delta, moral_delta = rng().randint(-5, -3), 2
            msg = f"你缩进检修井，踩着木偶巡逻节拍躲开追猎（+{heal}HP）。"
        else:
            dmg = rng().randint(3, 5)
            p.take_damage(dmg)
            evil_delta, moral_delta = rng().randint(2, 4), -1
            msg = f"你本想安静潜行，却误触到旧警报线，慌乱中擦伤（-{dmg}HP）。"
        return self._start_arc(route="hide", evil_delta=evil_delta, moral_delta=moral_delta, msg=msg)
    def cut_power_and_escape(self):
        _emit_puppet_audio_cue(self.controller, "event")
        dmg = rng().randint(4, 6)
        self.get_player().take_damage(dmg)
        return self._start_arc(
            route="blackout",
            evil_delta=rng().randint(3, 5),
            moral_delta=-1,
            msg=f"你猛拉总闸让整段走廊断电，借黑暗甩开木偶；但被飞散零件擦伤（-{dmg}HP）。",
        )

    def throw_decoy(self):
        _emit_puppet_audio_cue(self.controller, "event")
        p = self.get_player()
        cost = rng().randint(10, 18)
        spent = min(p.gold, cost)
        p.gold -= spent
        return self._start_arc(
            route="decoy",
            evil_delta=rng().randint(6, 8),
            moral_delta=-2,
            msg=f"你把值钱芯片当诱饵抛向岔路，成功骗过木偶扫描，但也烧掉了 {spent}G 物资。",
        )


class PuppetSignalEvent(Event):
    """支线：失真信号室（需先发生小弟战）。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        kind_name, dark_name = _get_puppet_persona_names(controller)
        self.title = "失真童谣"
        self.description = (
            "门后是一间报废监控室，满墙屏幕循环播放同一个画面：木偶的全息图坐在雨里，像被人遗弃的玩具。"
            f"日志交替显示以下两个信息：'{kind_name} 请求退出' / '{dark_name} 继续循环'。旁边有一个老式录音机和几卷录音带。"
        )
        self.choices = [
            EventChoice("重放温和语音样本", self.replay_soft_sample),
            EventChoice("播放战术日志做分析", self.extract_tactical_log),
            EventChoice("将所有的设备打包转卖，换取物资", self.resell_corrupted_fragment),
        ]

    def replay_soft_sample(self):
        _emit_puppet_audio_cue(self.controller, "event")
        p = self.get_player()
        if rng().random() < 0.6:
            heal_amt = rng().randint(5, 15)
            healed = p.heal(heal_amt)
            _adjust_puppet_evil_value(self.controller, rng().randint(-10, -6))
            self.register_story_choice(choice_flag="puppet_signal_soft", moral_delta=2)
            self.add_message(f"你把旧录音接回主线，总线噪声明显下降（+{healed}HP）。")
        else:
            dmg = rng().randint(12, 24)
            p.take_damage(dmg)
            _adjust_puppet_evil_value(self.controller, rng().randint(4, 6))
            self.register_story_choice(choice_flag="puppet_signal_soft", moral_delta=-1)
            self.add_message(f"录音在关键段落失真，木偶误判了你的节拍，冲击电流反噬（-{dmg}HP）。")
        return "Event Completed"
    def extract_tactical_log(self):
        _emit_puppet_audio_cue(self.controller, "event")
        atk_bonus = rng().randint(5, 15)
        self.get_player().change_base_atk(atk_bonus)
        _adjust_puppet_evil_value(self.controller, rng().randint(-5, -3))
        self.register_story_choice(choice_flag="puppet_signal_log", moral_delta=1)
        self.add_message(f"你掌握到了到关键的动作并补齐了反制参数（基础攻击 +{atk_bonus}）。")
        return "Event Completed"
    def resell_corrupted_fragment(self):
        _emit_puppet_audio_cue(self.controller, "event")
        p = self.get_player()
        gold_gain = rng().randint(14, 22)
        dmg = rng().randint(13, 25)
        p.gold += gold_gain
        p.take_damage(dmg)
        _adjust_puppet_evil_value(self.controller, rng().randint(8, 12))
        self.register_story_choice(choice_flag="puppet_signal_resell", moral_delta=-4)
        self.add_message(f"你把污染片段转卖赚了 {gold_gain}G，但反冲电流灼伤手臂（-{dmg}HP）。")
        return "Event Completed"


class PuppetKindEchoEvent(Event):
    """支线：与善良人格互动。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        kind_name, dark_name = _get_puppet_persona_names(controller)
        self.title = "蓝眼回声"
        self.description = (
            f"一束细蓝光从坏掉的喇叭里投影成小小木偶轮廓，它自称{kind_name}。"
            f"它压低声音说：'我中了病毒，{dark_name}快接管我了，快，走这条路，我在这边。'"
            "你能感觉到这不是幻觉，而是它善良人格在求援。"
        )
        self.choices = [
            EventChoice(f"相信{kind_name}，按它给的隐蔽路线前进", self.follow_kind_voice),
            EventChoice("追问它被抛弃的过去，尝试稳定它的情绪", self.ask_abandoned_past),
            EventChoice("记录它的情感弱点，无视它的求援，准备决战压制", self.extract_weakness),
        ]

    def follow_kind_voice(self):
        _emit_puppet_audio_cue(self.controller, "event")
        heal_amt = rng().randint(5, 10)
        heal = self.get_player().heal(heal_amt)
        _adjust_puppet_evil_value(self.controller, rng().randint(-16, -12))
        self.register_story_choice(choice_flag="puppet_kind_echo_trust", moral_delta=5)
        self.add_message(f"你照着它给的节拍穿过回廊，顺路捡到了一些补给（+{heal}HP）。")
        return "Event Completed"
    def ask_abandoned_past(self):
        _emit_puppet_audio_cue(self.controller, "event")
        p = self.get_player()
        gold_gain = rng().randint(6, 11)
        p.gold += gold_gain
        if rng().random() < 0.5:
            _adjust_puppet_evil_value(self.controller, rng().randint(-9, -5))
            self.register_story_choice(choice_flag="puppet_kind_echo_comfort", moral_delta=3)
            self.add_message(f"你听完它被遗弃那晚的记录，蓝光短暂稳定，并交给你旧维修密钥（+{gold_gain}G）。")
        else:
            dmg = rng().randint(3, 5)
            p.take_damage(dmg)
            _adjust_puppet_evil_value(self.controller, rng().randint(3, 5))
            self.register_story_choice(choice_flag="puppet_kind_echo_comfort", moral_delta=-2)
            self.add_message(f"你触碰到过深记忆，情绪回路反咬你，胸口像被电弧掠过（-{dmg}HP，仍拿到 {gold_gain}G）。")
        return "Event Completed"
    def extract_weakness(self):
        _emit_puppet_audio_cue(self.controller, "event")
        atk_bonus = rng().randint(1, 2)
        self.get_player().change_base_atk(atk_bonus)
        _adjust_puppet_evil_value(self.controller, rng().randint(5, 7))
        self.register_story_choice(choice_flag="puppet_kind_echo_exploit", moral_delta=-1)
        self.add_message(f"你强行提取情感弱点表，战术上更有把握（基础攻击 +{atk_bonus}），但它眼里的红噪更浓了。")
        return "Event Completed"


class PuppetPersonaRiftEvent(Event):
    """主线二：人格裂隙（由初始事件后 20~30 回合强推）。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        kind_name, dark_name = _get_puppet_persona_names(controller)
        self.title = "人格裂隙"
        self.description = (
            "你踏入门后空间，眼前出现同一具木偶的两层投影：蓝光与红噪不断覆盖彼此。"
            f"蓝色投影{kind_name}在求你别放弃它，红色投影{dark_name}则不断诱导你走最快的路径，面前是一个指令发送器。"
        )
        self.choices = [
            EventChoice(f"护住{kind_name}的信号通道", self.shield_kind_signal),
            EventChoice("维持两种信号平衡", self.keep_pragmatic_balance),
            EventChoice(f"向{dark_name}发送毁灭指令", self.fuel_dark_side),
        ]

    def _after_rift(self, route_flag, moral_delta, message):
        self.register_story_choice(choice_flag=f"puppet_rift_{route_flag}", moral_delta=moral_delta)
        _schedule_puppet_mainline_event(
            self.controller,
            from_stage="rift",
            next_event_key="puppet_core_descent_event",
            hint="前情：裂隙暂时闭合，但更深处的核心井已经开始重启。",
            message="前情提要：你在裂隙里的抉择已写入核心。。",
        )
        self.add_message(message)
        return "Event Completed"

    def shield_kind_signal(self):
        _emit_puppet_audio_cue(self.controller, "rift")
        heal_amt = rng().randint(7, 11)
        heal = self.get_player().heal(heal_amt)
        _adjust_puppet_evil_value(self.controller, rng().randint(-17, -13))
        return self._after_rift(
            route_flag="kind",
            moral_delta=6,
            message=f"你把护盾接到蓝光信号上，蓝光短暂稳住主导权，向你照来一束暖光（+{heal}HP）。",
        )
    def keep_pragmatic_balance(self):
        _emit_puppet_audio_cue(self.controller, "rift")
        p = self.get_player()
        if rng().random() < 0.5:
            atk_bonus = rng().randint(5, 10)
            p.change_base_atk(atk_bonus)
            _adjust_puppet_evil_value(self.controller, rng().randint(-3, -1))
            moral_delta = 1
            message = f"你维持双侧输出平衡，战术窗口扩大了一瞬，你感觉到了一丝平衡的力量（基础攻击 +{atk_bonus}）。"
        else:
            dmg = rng().randint(3, 5)
            p.take_damage(dmg)
            _adjust_puppet_evil_value(self.controller, rng().randint(2, 4))
            moral_delta = -1
            message = f"你试图两边都压住，却被裂隙反向共振震伤（-{dmg}HP）。"
        return self._after_rift(route_flag="balance", moral_delta=moral_delta, message=message)
    def fuel_dark_side(self):
        _emit_puppet_audio_cue(self.controller, "rift")
        p = self.get_player()
        gold_gain = rng().randint(22, 78)
        dmg = rng().randint(4, 6)
        p.gold += gold_gain
        p.take_damage(dmg)
        _adjust_puppet_evil_value(self.controller, rng().randint(14, 18))
        return self._after_rift(
            route_flag="dark",
            moral_delta=-6,
            message=f"你把自毁协议喂给红色回路，红色幻影立刻吐出了 {gold_gain}G，但反冲灼伤你的神经（-{dmg}HP）。",
        )


class PuppetCoreDescentEvent(Event):
    """主线三：核心下潜（由人格裂隙后 20~30 回合强推）。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        kind_name, dark_name = _get_puppet_persona_names(controller)
        self.title = "核心下潜"
        self.description = (
            "你走进核心井，看到木偶本体被铁索吊在半空，黑红电弧在它周身游走。"
            f"监控写着：[{kind_name}]，[{dark_name}]，两者不可共存。面前是一个老式麦克风和操作手册。"
        )
        self.choices = [
            EventChoice("按照手册写入修复补丁", self.patch_kind_persona),
            EventChoice("按照手册切断情感模块", self.cut_emotion_module),
            EventChoice("随机录入指令，试图控制木偶本体", self.feed_dark_protocol),
        ]

    def _queue_final_boss(self, route, moral_delta):
        current_round = max(0, int(getattr(self.controller, "round_count", 0)))
        payload = build_puppet_final_boss_payload(self.controller)
        self.register_story_choice(
            choice_flag=f"puppet_descent_{route}",
            moral_delta=moral_delta,
            consequences=[
                {
                    "consequence_id": "puppet_mainline_final_boss_gate",
                    "effect_key": "puppet_dark_boss",
                    "chance": 1.0,
                    "priority": 130,
                    "trigger_door_types": ["MONSTER", "EVENT", "TRAP", "SHOP", "REWARD"],
                    "min_round": current_round + 20,
                    "max_round": current_round + 30,
                    "force_on_expire": True,
                    "force_door_type": "MONSTER",
                    "required_flags": {"puppet_arc_active"},
                    "payload": payload,
                }
            ],
        )

    def patch_kind_persona(self):
        _emit_puppet_audio_cue(self.controller, "core")
        _adjust_puppet_evil_value(self.controller, rng().randint(-20, -16))
        self._queue_final_boss(route="patch", moral_delta=7)
        p = self.get_player()
        cost_base = rng().randint(14, 22)
        cost = min(p.gold, cost_base)
        p.gold -= cost
        heal_amt = rng().randint(8, 12)
        healed = p.heal(heal_amt)
        self.add_message(f"你把修复补丁烧进核心，总计消耗 {cost}G 维修件；蓝光重新亮了半秒（+{healed}HP）。")
        return "Event Completed"
    def cut_emotion_module(self):
        _emit_puppet_audio_cue(self.controller, "core")
        p = self.get_player()
        self._queue_final_boss(route="cut_emotion", moral_delta=-2)
        if rng().random() < 0.55:
            _adjust_puppet_evil_value(self.controller, rng().randint(5, 7))
            atk_bonus = rng().randint(1, 3)
            p.change_base_atk(atk_bonus)
            self.add_message(f"你切断情感模块，木偶的光芒熄灭了，但让你更专注于战斗（基础攻击 +{atk_bonus}）。")
        else:
            _adjust_puppet_evil_value(self.controller, rng().randint(-5, -3))
            dmg = rng().randint(5, 8)
            p.take_damage(dmg)
            self.add_message(f"你切模块时被残留的善良侧牵制，动作迟疑反被灼伤（-{dmg}HP）。")
        return "Event Completed"
    def feed_dark_protocol(self):
        _emit_puppet_audio_cue(self.controller, "core")
        _adjust_puppet_evil_value(self.controller, rng().randint(18, 22))
        self._queue_final_boss(route="dark_feed", moral_delta=-7)
        p = self.get_player()
        gold_gain = rng().randint(18, 26)
        dmg = rng().randint(6, 10)
        p.gold += gold_gain
        p.take_damage(dmg)
        self.add_message(f"你乱输入的指令让本体掉落了一部分金色身体，让你捡到了，增加 {gold_gain}G；回灌污染流反咬你（-{dmg}HP）。")
        return "Event Completed"

