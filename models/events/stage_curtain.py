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
from models.events._pkg import rng
from models.events.puppet_chain import _get_puppet_persona_names
from models.narrative.stage_curtain_epilogue import build_stage_epilogue_lines as _build_stage_epilogue_lines

def _get_pre_final_gate_config(gate_key):
    cfg = PRE_FINAL_GATE_STORY_CONFIG.get(gate_key, {})
    return dict(cfg) if isinstance(cfg, dict) else {}


def _schedule_pre_final_gate(
    controller,
    gate_key,
    *,
    min_round=None,
    max_round=None,
    min_round_offset=1,
    max_round_offset=1,
    trigger_door_types=None,
    extra_payload=None,
):
    story = getattr(controller, "story", None)
    if story is None:
        return False
    cfg = _get_pre_final_gate_config(gate_key)
    if not cfg:
        return False
    base_payload = cfg.get("payload", {})
    payload = dict(base_payload) if isinstance(base_payload, dict) else {}
    if isinstance(extra_payload, dict):
        payload.update(extra_payload)
    current_round = max(0, int(getattr(controller, "round_count", 0)))
    if min_round is None:
        min_round = current_round + max(0, int(min_round_offset))
    else:
        min_round = max(0, int(min_round))
    if max_round is None:
        max_round = current_round + max(0, int(max_round_offset))
    else:
        max_round = max(0, int(max_round))
    if max_round < min_round:
        max_round = min_round
    # 结局事件：仅到结局回合（200）才可触发，强制 min/max_round >= ending_round
    try:
        ending_round = int(getattr(story, "DEFAULT_ENDING_FORCE_ROUND", 200))
    except (TypeError, ValueError):
        ending_round = 200
    if gate_key in ENDING_EVENT_GATE_KEYS:
        min_round = max(min_round, ending_round)
        max_round = max(max_round, ending_round)
    # 结局前事件不做 max_round 强制替换，由「保证对应门型出现」按序触发
    blocking_no_force = ("puppet_rematch_gate", "elf_rival_final_gate", "dream_mirror_prelude_gate")
    # 终局链（第二门、Boss门）在挂载后下一选门立即强制触发，无论选哪扇门
    ending_chain_force = ("default_second_gate_event", "default_final_boss_gate")
    if gate_key in blocking_no_force:
        force_on_expire = False
        try:
            ending_round = int(getattr(story, "DEFAULT_ENDING_FORCE_ROUND", 200))
            max_round = max(max_round, ending_round)
        except (TypeError, ValueError):
            pass
    elif gate_key in ending_chain_force:
        force_on_expire = True
        min_round = current_round
        max_round = current_round
    else:
        force_on_expire = True
    configured_trigger_door_types = cfg.get("trigger_door_types", list(ALL_PRE_FINAL_DOOR_TYPES))
    chosen_trigger_door_types = trigger_door_types if trigger_door_types is not None else configured_trigger_door_types
    return story.register_consequence(
        choice_flag=str(cfg.get("choice_flag", "ending_default_normal_route")),
        consequence_id=str(cfg.get("consequence_id", f"pre_final:{gate_key}")),
        effect_key=str(cfg.get("effect_key", "force_story_event")),
        chance=1.0,
        trigger_door_types=list(chosen_trigger_door_types),
        min_round=min_round,
        max_round=max_round,
        force_on_expire=force_on_expire,
        force_door_type=str(cfg.get("force_door_type", "EVENT")),
        priority=int(cfg.get("priority", 1200)),
        payload=payload,
    )


def _schedule_default_ending_forced_event(controller, gate_key):
    return _schedule_pre_final_gate(controller=controller, gate_key=gate_key)


def _schedule_default_ending_final_boss(controller):
    return _schedule_pre_final_gate(controller=controller, gate_key="default_final_boss_gate")


def _schedule_default_first_gate_for_curtain_choice(controller):
    """谢幕相关事件中选「选择困难症」时挂载普通结局主线；结局事件仅到第 200 回合才可触发，故由 _schedule_pre_final_gate 内 ENDING_EVENT_GATE_KEYS 约束为 200 回合。"""
    current_round = max(0, int(getattr(controller, "round_count", 0)))
    story = getattr(controller, "story", None)
    ending_round = int(getattr(story, "DEFAULT_ENDING_FORCE_ROUND", 200)) if story else 200
    min_round = max(current_round + 1, ending_round)
    return _schedule_pre_final_gate(
        controller=controller,
        gate_key="round200_default_first_gate",
        min_round=min_round,
        max_round=ending_round + 20,
    )


def _schedule_stage_curtain_gate_event(controller):
    # 与善良人格约定后，下一回合紧接着进入「舞台谢幕·终幕门廊」，
    # 不再等待结局回合或特定门型窗口。
    current_round = max(0, int(getattr(controller, "round_count", 0)))
    schedule_round = current_round + 1
    return _schedule_pre_final_gate(
        controller=controller,
        gate_key="stage_curtain_gate_event",
        min_round=schedule_round,
        max_round=schedule_round,
    )


def _should_schedule_kind_puppet_dialogue(controller):
    """是否在取回剧本后插入“与善良木偶对话”事件：已拿剧本、已击败木偶终战且邪恶值偏低。"""
    story = getattr(controller, "story", None)
    if story is None:
        return False
    tags = set(getattr(story, "story_tags", set()))
    flags = set(getattr(story, "choice_flags", set()))
    script_recovered = "curtain_call_script_recovered" in tags or "curtain_call_script_recovered" in flags
    if not script_recovered:
        return False
    puppet_defeated = "ending:puppet_final_defeated" in tags or getattr(story, "puppet_final_outcome", "") == "defeated"
    if not puppet_defeated:
        return False
    try:
        evil = max(0, min(100, int(getattr(story, "puppet_evil_value", 55))))
    except (TypeError, ValueError):
        evil = 55
    return evil <= 45


def _schedule_kind_puppet_dialogue_event(controller):
    """秘藏取回剧本后，若木偶善良侧归位则挂载与善良人格对话门；下一扇门起即可触发，不强制到第 200 回合。"""
    story = getattr(controller, "story", None)
    if story is None:
        return False
    current_round = max(0, int(getattr(controller, "round_count", 0)))
    ending_round = int(getattr(story, "DEFAULT_ENDING_FORCE_ROUND", 200))
    min_round = current_round + 1
    max_round = ending_round
    return _schedule_pre_final_gate(
        controller=controller,
        gate_key="stage_curtain_kind_puppet_dialogue",
        min_round=min_round,
        max_round=max_round,
    )


def _collect_stage_curtain_scores(story):
    flags = set(getattr(story, "choice_flags", set()))
    tags = set(getattr(story, "story_tags", set()))
    order = 0
    freedom = 0
    power = 0
    risk = 0
    notes = []
    elf_outcome = ""
    moon_verdict = ""
    ticket_outcome = ""
    dream_outcome = ""
    mirror_outcome = ""
    elf_rival_outcome = ""

    if "elf_outcome:alliance" in tags or "elf_outcome_alliance" in flags:
        order += 1
        freedom += 2
        elf_outcome = "alliance"
        notes.append("银羽飞贼愿意把关键证词交给你。")
    elif "elf_outcome:neutral" in tags or "elf_outcome_neutral" in flags:
        order += 1
        elf_outcome = "neutral"
        notes.append("银羽飞贼只留下了有限线索。")
    elif "elf_outcome:hostile" in tags or "elf_outcome_hostile" in flags:
        power += 1
        risk += 3
        elf_outcome = "hostile"
        notes.append("银羽飞贼与你决裂，终幕信任链被撕开。")

    if "ending_elf_rival_final_victory" in flags:
        elf_rival_outcome = "victory"
    elif "ending_elf_rival_parted" in flags:
        elf_rival_outcome = "parted"

    diary_source = str(getattr(story, "moon_bounty_diary_source", "")).strip()
    if diary_source == "thief_testimony":
        freedom += 2
        notes.append("大盗证词与旧日记互相印证，冤案被翻出。")
    elif diary_source == "thief_body":
        order += 1
        notes.append("你掌握了来自案发现场的旧日记证据。")

    if "moon_verdict_clean" in flags:
        order += 2
        moon_verdict = "clean"
    if "moon_verdict_burned" in flags:
        power += 1
        risk += 2
        moon_verdict = "burned"
    if "moon_verdict_extorted" in flags:
        power += 2
        risk += 1
        moon_verdict = "extorted"

    if "clockwork_calibrated" in flags or "cog_audit_tax_paid" in flags:
        order += 1
        if not ticket_outcome:
            ticket_outcome = "calibrated"
    if "clockwork_hacked" in flags or "cog_audit_faked" in flags or "cog_audit_silenced" in flags:
        power += 1
        risk += 1
        ticket_outcome = "hacked"
    if "clockwork_sabotaged" in flags:
        power += 1
        risk += 2
        ticket_outcome = "sabotaged"

    if "dream_well_sealed" in flags or "echo_court_redeemed" in flags:
        order += 1
        if not dream_outcome:
            dream_outcome = "stabilized"
    if "dream_well_drank" in flags or "mirror_tore_script" in flags:
        freedom += 1
        if dream_outcome != "traded":
            dream_outcome = "improv"
    if "dream_well_sold" in flags or "echo_court_trading" in flags:
        power += 2
        risk += 1
        dream_outcome = "traded"
    if "echo_court_taxed" in flags:
        order += 1
        if not dream_outcome:
            dream_outcome = "taxed"

    if "mirror_played_hero" in flags:
        order += 1
        if not mirror_outcome:
            mirror_outcome = "hero"
    if "mirror_played_villain" in flags:
        power += 1
        mirror_outcome = "villain"
    if "mirror_tore_script" in flags:
        mirror_outcome = "tore_script"

    kind_flags = {
        "puppet_signal_soft",
        "puppet_kind_echo_trust",
        "puppet_kind_echo_comfort",
        "puppet_rift_kind",
        "puppet_descent_patch",
    }
    dark_flags = {
        "puppet_signal_resell",
        "puppet_kind_echo_exploit",
        "puppet_rift_dark",
        "puppet_descent_cut_emotion",
        "puppet_descent_dark_feed",
    }
    kind_hits = len(kind_flags.intersection(flags))
    dark_hits = len(dark_flags.intersection(flags))
    if kind_hits >= 2:
        freedom += 1
        order += 1
        notes.append("木偶善侧残响仍在，舞台暴走风险下降。")
    if dark_hits >= 2:
        power += 1
        risk += 1
        notes.append("木偶暗侧参数被你长期放大，终幕更偏强控。")

    key_obtained = bool(getattr(story, "elf_key_obtained", False)) or ("elf_key_obtained" in tags)
    script_recovered = "curtain_call_script_recovered" in tags or "curtain_call_script_recovered" in flags
    puppet_outcome = str(getattr(story, "puppet_final_outcome", "")).strip()
    puppet_final_defeated = "ending:puppet_final_defeated" in tags or puppet_outcome == "defeated"
    try:
        puppet_evil_value = max(0, min(100, int(getattr(story, "puppet_evil_value", 55))))
    except (TypeError, ValueError):
        puppet_evil_value = 55
    puppet_chain_concluded = puppet_final_defeated
    puppet_low_evil = puppet_evil_value <= 45
    puppet_kind_rescued = puppet_chain_concluded and puppet_low_evil
    stage_script_ready = key_obtained and script_recovered
    script_truth_revealed = "curtain_call_truth_revealed" in tags or "curtain_call_truth_revealed" in flags

    if puppet_kind_rescued:
        order += 2
        risk = max(0, risk - 1)
        notes.append("黑暗木偶的人格被你救回，补全谢幕有了可归位的原主演。")
    elif puppet_chain_concluded:
        risk += 1
        notes.append("木偶终战虽已结束，但善良人格未能归位，补全谢幕存在缺角。")
    else:
        notes.append("木偶主线仍未完成，补全谢幕缺少关键主演回归条件。")

    return {
        "order": order,
        "freedom": freedom,
        "power": power,
        "risk": risk,
        "notes": notes,
        "diary_source": diary_source,
        "elf_key_obtained": key_obtained,
        "script_recovered": script_recovered,
        "stage_script_ready": stage_script_ready,
        "puppet_chain_concluded": puppet_chain_concluded,
        "puppet_final_defeated": puppet_final_defeated,
        "puppet_low_evil": puppet_low_evil,
        "puppet_kind_rescued": puppet_kind_rescued,
        "puppet_evil_value": puppet_evil_value,
        "elf_outcome": elf_outcome,
        "elf_rival_outcome": elf_rival_outcome,
        "moon_verdict": moon_verdict,
        "ticket_outcome": ticket_outcome,
        "dream_outcome": dream_outcome,
        "mirror_outcome": mirror_outcome,
        "script_truth_revealed": script_truth_revealed,
    }


def _resolve_stage_curtain_outcome(route_key, score_payload):
    """根据玩家选择的谢幕路线（route_key）确定结局类型；order/freedom/power/risk 仅影响剧情文案差异。"""
    order = int(score_payload.get("order", 0))
    freedom = int(score_payload.get("freedom", 0))
    power = int(score_payload.get("power", 0))
    risk = int(score_payload.get("risk", 0))
    notes = list(score_payload.get("notes", []))
    puppet_kind_rescued = bool(score_payload.get("puppet_kind_rescued", False))
    stage_script_ready = bool(score_payload.get("stage_script_ready", False))
    puppet_final_defeated = bool(score_payload.get("puppet_final_defeated", False))
    script_recovered = bool(score_payload.get("script_recovered", False))
    suffix = ""

    def _compose_with_epilogue(base_text, current_route):
        epilogue = "".join(_build_stage_epilogue_lines(current_route, score_payload))
        if epilogue:
            return f"{base_text}{epilogue}{suffix}"
        return f"{base_text}{suffix}"

    # 无剧本且已击败黑暗木偶：终局事件读取参数时触发即兴谢幕（按邪恶值分支文案）
    if puppet_final_defeated and not script_recovered:
        evil = max(0, min(100, int(score_payload.get("puppet_evil_value", 55))))
        if evil <= 45:
            persona_line = (
                "残存的善良人格在消散前把最后一点信号传到你耳边："
                "「没有剧本也没关系……你早就比任何台词都更像主角。去吧，把最后一幕演完。」"
            )
        else:
            persona_line = (
                "黑暗侧在彻底静默前挤出最后一段失真音："
                "「你以为赢了？你连剧本都没见过，不过是顶替我的替身罢了……呵，那就看看你这即兴能撑到几时。」"
            )
        common_close = (
            "灯光打在你身上。没有原定的台词，没有写好的终章——"
            "你代替倒下的木偶站上舞台中央，即兴完成最后一幕，然后向虚空中的观众深深鞠躬，谢幕。"
        )
        return {
            "ending_key": "impromptu_curtain_call",
            "ending_title": "即兴谢幕",
            "ending_description": f"{persona_line} {common_close}",
            "outcome_tag": "impromptu",
            "notes": notes,
        }

    # 补全谢幕：结局类型固定为 stage_curtain_order，仅根据 puppet_kind_rescued / stage_script_ready 变化文案
    if route_key == "order":
        scene_lines = []
        if puppet_kind_rescued and stage_script_ready:
            scene_lines = [
                "你把银羽旧钥匙与终幕剧本并排压在台沿，灯桥一盏盏依序点亮。",
                "蓝眼睛的的木偶照着原剧本演完最后一幕，随后一路跑上前台，和你一起向观众谢幕。",
            ]
            ending_description = _compose_with_epilogue(
                "你按证词与秩序补齐终幕结构。被你救回的木偶善良人格依照原剧本完成了最后一幕，"
                "并亲自回到台前谢幕。散场后你没有立刻离开，而是把证词、票据与破碎台词一并归档，"
                "让这场险些失控的演出终于拥有可被复述的尾声。",
                "order",
            )
            curtain_speciale = "puppet_kind_script_curtain_call"
        elif puppet_kind_rescued:
            scene_lines = [
                "你修补了主要场次与灯位，木偶终于找回自己的台词与站位。",
                "它在最后一声钟鸣后回到台口，和你完成了迟到的谢幕。",
            ]
            ending_description = _compose_with_epilogue(
                "你按证词与秩序补齐终幕结构，木偶人格归位后与你一同完成谢幕。"
                "终幕并不完美，但你把缺失段落留成可追溯的注脚，让后来者知道这不是奇迹，"
                "而是一次次把失序拉回轨道的结果。",
                "order",
            )
            curtain_speciale = "puppet_kind_curtain_call"
        else:
            ending_description = _compose_with_epilogue(
                "你按证词与秩序补齐终幕结构。尽管善良人格尚未归位，你仍依剧本完成最后一幕并谢幕。"
                "灯暗下去时，你把空出来的角色名保留在终幕表上，提醒所有人：这场补全是完成，"
                "却不是遗忘。",
                "order",
            )
            curtain_speciale = ""
        return {
            "ending_key": "stage_curtain_order",
            "ending_title": "舞台谢幕·补全谢幕",
            "ending_description": ending_description,
            "outcome_tag": "order",
            "notes": notes,
            "scene_lines": scene_lines,
            "curtain_speciale": curtain_speciale,
        }

    # 即兴谢幕：结局类型固定为 stage_curtain_freedom，文案依分数差异
    if route_key == "freedom":
        ending_description = _compose_with_epilogue(
            "你承认剧本无法完整复刻，带着众人的证词即兴完成终演。"
            "你把走廊里每一次迟疑、每一次冒险和每一句没说完的话都揉进临场台词里，"
            "让终幕在失控边缘开出了自己的节拍。",
            "freedom",
        )
        return {
            "ending_key": "stage_curtain_freedom",
            "ending_title": "舞台谢幕·即兴谢幕",
            "ending_description": ending_description,
            "outcome_tag": "freedom",
            "notes": notes,
        }

    # 接管谢幕：结局类型固定为 stage_curtain_power，文案依分数差异
    if route_key == "power":
        ending_description = _compose_with_epilogue(
            "你以导演代理人身份接管门廊规则，强行完成谢幕。"
            "当所有灯位、闸机与通行口都被你重新编号后，剧场不再等待『正确剧情』，"
            "而是按照你的指令推进到最后一拍。",
            "power",
        )
        return {
            "ending_key": "stage_curtain_power",
            "ending_title": "舞台谢幕·接管谢幕",
            "ending_description": ending_description,
            "outcome_tag": "power",
            "notes": notes,
        }

    # 未知 route_key 时默认即兴
    ending_description = _compose_with_epilogue(
        "你承认剧本无法完整复刻，带着众人的证词即兴完成终演。"
        "你把那些没有答案的问题也带上了舞台，让终幕在观众的沉默和掌声之间自行落定。",
        "freedom",
    )
    return {
        "ending_key": "stage_curtain_freedom",
        "ending_title": "舞台谢幕·即兴谢幕",
        "ending_description": ending_description,
        "outcome_tag": "freedom",
        "notes": notes,
    }


def run_script_vault_recovery(controller):
    """宝物门进门时执行：仅剧情（得到剧本 + 飞贼遗留宝物金币），无事件选项。用于倒数窗口内银羽秘藏宝物门。"""
    story = getattr(controller, "story", None)
    if story is None:
        return
    tags = set(getattr(story, "story_tags", set()))
    diary_source = str(getattr(story, "moon_bounty_diary_source", "")).strip()
    description = (
        "你推开了那扇刻着银羽暗号的宝物门。"
        "旧钥匙刚进入锁孔，整面墙就像布景般滑开。"
        "秘藏室中央只有一只防尘匣，匣内并非金银，而看起来是一本破旧的笔记本，这是一本剧本。"
    )
    if "moon_bounty_diary_obtained" in tags:
        if diary_source == "thief_testimony":
            description = (
                f"{description} 你把此前拿到的大盗证词日记摊在旁边，字句一一对上："
                "通缉令里的『命运乐章』就是这本被银羽飞贼带走的“账本”，那名大盗被冤枉了。"
            )
        elif diary_source == "thief_body":
            description = (
                f"{description} 你把从大盗身上搜出的日记逐页对照，终于确认："
                "安保系统追错了人，所谓命运乐章正是这本失窃剧本。"
            )
        else:
            description = (
                f"{description} 你把旧日记本放在剧本旁边，残缺记录与正文相互咬合，"
                "通缉案的错位真相终于浮出水面。"
            )
    controller.add_message(description)
    # 飞贼在秘藏室还留了一些宝物，玩家获得金币
    player = getattr(controller, "player", None)
    if player is not None:
        bonus_gold = rng().randint(40, 70)
        player.gold += bonus_gold
        controller.add_message(f"角落里还有飞贼留下的一些零散宝物，你收了起来，获得 {bonus_gold} 金币。")
    story.register_choice(choice_flag="curtain_script_secured", moral_delta=1)
    story.story_tags.add("curtain_call_script_recovered")
    story.choice_flags.add("curtain_call_script_recovered")
    if "moon_bounty_diary_obtained" in tags:
        story.story_tags.add("curtain_call_truth_revealed")
        controller.add_message("你终于能确认：命运乐章正是银羽飞贼偷走的终幕剧本。")
    controller.add_message("你把整本剧本收进口袋，继续前进。")
    if _should_schedule_kind_puppet_dialogue(controller):
        _schedule_kind_puppet_dialogue_event(controller)


class EndingStageKindPuppetDialogueEvent(Event):
    """结局门：与善良木偶对话，三选一直接进入补全/即兴/选择困难症三种结局之一。补全与即兴选项有正面效果（加血/加攻），选择困难症无效果。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        kind_name, _ = _get_puppet_persona_names(controller)
        self.title = "与善良人格的约定"
        self.description = (
            f"你已从飞贼宝藏取回剧本，木偶终战已胜且善良侧尚存。"
            f"机偶胸腔里残存的蓝光——{kind_name}——主动与你联络："
            "可以按剧本补全谢幕，可以即兴收尾，也可以选择直面内心的迟疑、走向选择困难症候群把守的终局。"
            "若选补全或即兴，它愿在分别前给你一点馈赠。"
        )
        self.choices = [
            EventChoice("补全谢幕——让它把终章演完", self.pick_order),
            EventChoice("即兴谢幕——把最后一幕交给我", self.pick_freedom),
            EventChoice("选择困难症——我选不下去", self.pick_default),
        ]

    def pick_order(self):
        """补全谢幕 → stage_curtain_order，并给予加血。"""
        p = self.get_player()
        heal_amt = 14
        actual = p.heal(heal_amt)
        self.add_message("你选择按剧本补全谢幕。善良人格轻声回应：我会把原定的终章演完。")
        self.add_message(f"它把一丝余温渡给你，伤势稍缓，恢复了 {actual} 点生命。")
        return self._trigger_stage_ending(
            route_key="order",
            choice_flag="ending_stage_gate_order",
            line="你把剧本压平在掌心，推开了『补全谢幕』之门。",
        )

    def pick_freedom(self):
        """即兴谢幕 → stage_curtain_freedom，并给予加攻。"""
        p = self.get_player()
        atk_bonus = 2
        p.change_base_atk(atk_bonus)
        self.add_message("你选择即兴收尾。善良人格轻声回应：那就把舞台交给你。")
        self.add_message("它把一缕决意留在你掌心，你感到出手更有力。")
        return self._trigger_stage_ending(
            route_key="freedom",
            choice_flag="ending_stage_gate_freedom",
            line="你合上剧本只留一页索引，转身推开『即兴谢幕』之门。",
        )

    def pick_default(self):
        """选择困难症 → 进入普通结局主线（终局第一门 → 第二门 → 选择困难症候群 Boss → 击败后 default_normal）"""
        self.register_story_choice(choice_flag="ending_stage_gate_default", moral_delta=0)
        self.add_message("你选择直面内心的迟疑，难以决策。善良人格沉默片刻，未再说什么。")
        self.add_message("下一扇门将通往终局回廊的第一道门——你将在那里做出最后的抉择。")
        _schedule_default_first_gate_for_curtain_choice(self.controller)
        return "Event Completed"

    def _trigger_stage_ending(self, route_key, choice_flag, line):
        self.register_story_choice(choice_flag=choice_flag, moral_delta=0)
        self.add_message(line)
        story = getattr(self.controller, "story", None)
        if story is None:
            return "Event Completed"

        score_payload = _collect_stage_curtain_scores(story)
        ending_payload = _resolve_stage_curtain_outcome(route_key, score_payload)
        outcome_tag = ending_payload.get("outcome_tag", "freedom")
        story.story_tags.add("ending:stage_curtain_completed")
        story.story_tags.add(f"ending:stage_curtain:{outcome_tag}")
        story.choice_flags.add(f"ending_stage_curtain_{outcome_tag}")

        notes = ending_payload.get("notes", [])
        if notes:
            self.add_message(" ".join(notes[:2]))
        for scene_line in list(ending_payload.get("scene_lines", []) or []):
            line_str = str(scene_line).strip()
            if line_str:
                self.add_message(line_str)

        ending_meta = {
            "stage_route_choice": route_key,
            "stage_outcome": outcome_tag,
            "stage_scores": {
                "order": score_payload.get("order", 0),
                "freedom": score_payload.get("freedom", 0),
                "power": score_payload.get("power", 0),
                "risk": score_payload.get("risk", 0),
            },
            "puppet_kind_rescued": bool(score_payload.get("puppet_kind_rescued", False)),
            "stage_script_ready": bool(score_payload.get("stage_script_ready", False)),
            "curtain_speciale": str(ending_payload.get("curtain_speciale", "")).strip(),
            "script_truth_revealed": "curtain_call_truth_revealed" in story.story_tags,
        }

        trigger_clear = getattr(self.controller, "trigger_game_clear", None)
        if callable(trigger_clear):
            trigger_clear(
                ending_key=ending_payload.get("ending_key", "stage_curtain_freedom"),
                ending_title=ending_payload.get("ending_title", "舞台谢幕"),
                ending_description=ending_payload.get("ending_description", "终幕结束。"),
                ending_meta=ending_meta,
            )
        else:
            self.controller.scene_manager.go_to("game_over_scene")
        return "Event Completed"


class StageCurtainKindPuppetDialogueMidEvent(Event):
    """舞台谢幕链：秘藏取回剧本后与善良木偶对话，仅约定谢幕方式并挂载终幕门廊，不直接触发结局。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        kind_name, _ = _get_puppet_persona_names(controller)
        self.title = "与善良人格的约定"
        self.description = (
            "机偶胸腔里残存的蓝光人格一息尚存：'剧本在你这！我想把我的部分演完，可以吗？'。"
            f"你可以让它按剧本演完谢幕，或者代替它自己来一段即兴收尾，也可以选择直面内心的迟疑，不做任何选择。"
            "约定后，前方门廊将为你敞开终幕之门。"
        )
        self.choices = [
            EventChoice("补全谢幕——你来把终章演完", self.pick_order),
            EventChoice("即兴谢幕——把最后一幕交给我", self.pick_freedom),
            EventChoice("选择困难症——我选不下去", self.pick_default),
        ]

    def pick_order(self):
        """补全谢幕：仅设定路线并挂载终幕门廊，不触发结局。"""
        p = self.get_player()
        heal_amt = 14
        actual = p.heal(heal_amt)
        self.register_story_choice(choice_flag="ending_stage_gate_order", moral_delta=0)
        self.add_message("你选择按剧本补全谢幕。善良人格轻声回应：我会把原定的终章演完。")
        self.add_message(f"它把一丝余温渡给你，伤势稍缓，恢复了 {actual} 点生命。")
        self.add_message("约定已定，前方门廊将出现终幕之门——推开门即可完成谢幕。")
        story = getattr(self.controller, "story", None)
        if story is not None:
            setattr(story, "curtain_pre_choice", "order_puppet_curtain")
        _schedule_stage_curtain_gate_event(self.controller)
        return "Event Completed"

    def pick_freedom(self):
        """即兴谢幕：仅设定路线并挂载终幕门廊，不触发结局。"""
        p = self.get_player()
        atk_bonus = 2
        p.change_base_atk(atk_bonus)
        self.register_story_choice(choice_flag="ending_stage_gate_freedom", moral_delta=0)
        self.add_message("你选择即兴收尾。木偶轻声回应：那就把舞台交给你。")
        self.add_message("它把一缕决意留在你掌心，你感到出手更有力。")
        self.add_message("约定已定，前方门廊将出现终幕之门——推开门即可完成谢幕。")
        story = getattr(self.controller, "story", None)
        if story is not None:
            setattr(story, "curtain_pre_choice", "freedom")
        _schedule_stage_curtain_gate_event(self.controller)
        return "Event Completed"

    def pick_default(self):
        """选择困难症 → 进入普通结局主线（终局第一门 → 第二门 → 选择困难症候群 Boss → 击败后 default_normal）"""
        self.register_story_choice(choice_flag="ending_stage_gate_default", moral_delta=0)
        self.add_message("你选择直面内心的迟疑，难以决策。善良人格沉默片刻，未再说什么。")
        self.add_message("下一扇门将通往终局回廊的第一道门——你将在那里做出最后的抉择。")
        _schedule_default_first_gate_for_curtain_choice(self.controller)
        return "Event Completed"


def _get_curtain_prelude_echo_line(choice_key):
    """谢幕结局时对「梦中排练录像」前奏选择的呼应句（不改写结局，仅剧情呼应）。"""
    if choice_key == "order":
        return "你曾在梦中对着镜里的排练录像默想过：终幕应当按既定的剧本收尾——此刻，那份默想与你的选择一同落定。"
    if choice_key == "freedom":
        return "你曾在梦中对着镜里的排练录像默想过：终幕应当由当下的选择写就——此刻，那份默想与你的选择一同落定。"
    if choice_key == "power":
        return "你曾在梦中对着镜里的排练录像默想过：终幕应当由能掌控舞台的人收束——此刻，那份默想与你的选择一同落定。"
    return ""


def _build_dream_mirror_rehearsal_flashback(story):
    """梦中看到的「镜面剧场排练录像」：根据玩家在镜面剧场的选择，拼出梦中回放的内容。"""
    flags = set(getattr(story, "choice_flags", set()))
    parts = []
    if "mirror_played_hero" in flags:
        parts.append("你看见镜中的自己又一次接过英雄面具，戴好。")
    elif "mirror_played_villain" in flags:
        parts.append("你看见镜中的自己又一次攥紧恶徒的面具，退场时有人在素描本上勾勒你的脸。")
    elif "mirror_tore_script" in flags:
        parts.append("你看见镜中的自己又一次撕掉剧本，拒绝入戏，破碎的台词像回音钩在神经上。")
    return " ".join(parts) if parts else "镜面在梦中闪烁，你看见自己在预演厅里一次次做出选择。"


def _build_dream_mirror_well_echo(story):
    """这段梦从何而来：梦境井的选择让「排练录像」得以在梦中浮现。"""
    flags = set(getattr(story, "choice_flags", set()))
    if "dream_well_drank" in flags:
        if "echo_court_redeemed" in flags:
            return "井水的回响从未真正散去；你赎回了回放，它们便在此刻的梦里重播。"
        if "echo_court_taxed" in flags:
            return "你曾为回放上缴过代价，梦却仍把旧画面还给你。"
        if "echo_court_trading" in flags:
            return "你卖掉了不少梦境，可镜前的这一段，买主从未拿走。"
        return "喝下的井水让历代回放流入意识，此刻在梦中翻涌。"
    if "dream_well_sealed" in flags:
        return "你曾封住井口，把回放压进井底——它们却从裂缝里渗进这场梦。"
    if "dream_well_sold" in flags:
        return "你曾把梦境折价卖掉，唯独镜面剧场的那几帧，不知为何留在了梦的角落里。"
    return "梦不知从何处涌来，镜中的排练录像一帧一帧重放。"


def _get_prelude_choice_variants(story):
    """根据梦境井+镜面剧场组合返回三选一文案的变体（秩序/即兴/接管）。"""
    flags = set(getattr(story, "choice_flags", set()))
    order_leaning = "dream_well_sealed" in flags or "echo_court_redeemed" in flags or "mirror_played_hero" in flags
    power_leaning = "dream_well_sold" in flags or "echo_court_trading" in flags or "mirror_played_villain" in flags
    if order_leaning and not power_leaning:
        return (
            "默想：终幕应当按既定的剧本收尾",
            "默想：终幕也可以由当下的选择写就",
            "默想：终幕或可由能掌控舞台的人收束",
        )
    if power_leaning and not order_leaning:
        return (
            "默想：终幕或可按既定的剧本收尾",
            "默想：终幕也可以由当下的选择写就",
            "默想：终幕应当由能掌控舞台的人收束",
        )
    return (
        "默想：终幕应当按既定的剧本收尾",
        "默想：终幕应当由当下的选择写就",
        "默想：终幕应当由能掌控舞台的人收束",
    )


class DreamMirrorPreludeEvent(Event):
    """结局前事件：在一场梦境中看到自己在镜面剧场的一次次选择（排练录像），并做与终幕相关的默想。其中两种默想会带来正面效果（加血/加攻），第三种无效果。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        story = getattr(controller, "story", None)
        self.title = "梦中排练录像"
        rehearsal = _build_dream_mirror_rehearsal_flashback(story) if story else ""
        well_echo = _build_dream_mirror_well_echo(story) if story else ""
        self.description = (
            "你沉入一段梦境。\n\n"
            "镜面剧场的预演厅在眼前一帧一帧重放——你看见自己在镜前伸手、选下面具、或撕掉剧本，"
            "像是过去的自己在反复排练同一场戏。\n\n"
            f"{rehearsal}\n\n"
            f"{well_echo}\n\n"
            "录像播完，梦还未醒。你站在梦里的镜前，心中浮现的只有一个问题：终幕，应当如何收束？"
            "不同的默想会带来不同的回响。"
        )
        order_t, freedom_t, power_t = _get_prelude_choice_variants(story) if story else (
            "默想：终幕应当按既定的剧本收尾",
            "默想：终幕应当由当下的选择写就",
            "默想：终幕应当由能掌控舞台的人收束",
        )
        self.choices = [
            EventChoice(order_t, self._pick_order),
            EventChoice(freedom_t, self._pick_freedom),
            EventChoice(power_t, self._pick_power),
        ]

    def _pick_order(self):
        """按剧本收尾：记录选择并加血。"""
        self.register_story_choice(choice_flag="curtain_prelude_order", moral_delta=0)
        story = getattr(self.controller, "story", None)
        if story is not None:
            setattr(story, "curtain_prelude_choice", "order")
        self.add_message("梦中你默想：终幕应当按既定的剧本收尾。")
        p = self.get_player()
        heal_amt = 12
        actual = p.heal(heal_amt)
        self.add_message("一股安定感自镜中涌出，仿佛过去的排练有了归宿。醒来时，伤势略轻，恢复了 {} 点生命。".format(actual))
        return "Event Completed"

    def _pick_freedom(self):
        """由当下选择写就：记录选择并加攻。"""
        self.register_story_choice(choice_flag="curtain_prelude_freedom", moral_delta=0)
        story = getattr(self.controller, "story", None)
        if story is not None:
            setattr(story, "curtain_prelude_choice", "freedom")
        self.add_message("梦中你默想：终幕应当由当下的选择写就。")
        p = self.get_player()
        atk_bonus = 2
        p.change_base_atk(atk_bonus)
        self.add_message("镜中的你点了点头，决意凝聚在掌心。醒来时，出手更稳、更有力,基础攻击力增加了 {} 点。".format(atk_bonus))
        return "Event Completed"

    def _pick_power(self):
        """由掌控者收束：仅记录选择，无馈赠。"""
        self.register_story_choice(choice_flag="curtain_prelude_power", moral_delta=0)
        story = getattr(self.controller, "story", None)
        if story is not None:
            setattr(story, "curtain_prelude_choice", "power")
        self.add_message("梦中你默想：终幕应当由能掌控舞台的人收束。镜面暗了下去，梦中未得馈赠。")
        return "Event Completed"


class EndingStageCurtainGateEvent(Event):
    """舞台谢幕链终局门：补全/即兴/接管三选一；若已与善良木偶约定则直接执行约定。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        story = getattr(controller, "story", None)
        pre_choice = getattr(story, "curtain_pre_choice", None) if story else None
        if pre_choice in ("freedom", "order_puppet_curtain"):
            self.title = "舞台谢幕·终幕门廊"
            self.description = (
                "你依照与善良人格的约定抵达门廊。"
                "之前已选定的谢幕方式将在此兑现——只需推开门完成最后一幕。"
            )
            self.choices = [
                EventChoice("依照约定，完成谢幕", self._trigger_pre_chosen_route),
            ]
        else:
            self.title = "舞台谢幕·终幕门廊"
            self.description = (
                "你抱着刚取回的终幕剧本抵达门廊，三道门牌像舞台吊牌一样降下："
                "『补全谢幕』『即兴谢幕』『接管谢幕』。"
                "门框上的刻痕同时亮起，催你用自己的选择写下最终落幕。"
            )
            self.choices = [
                EventChoice("走『补全谢幕』之门", self.pick_order),
                EventChoice("走『即兴谢幕』之门", self.pick_freedom),
                EventChoice("走『接管谢幕』之门", self.pick_power),
            ]

    def _trigger_pre_chosen_route(self):
        """执行与善良木偶约定好的谢幕路线：order_puppet_curtain→补全且木偶谢幕，freedom→即兴。"""
        story = getattr(self.controller, "story", None)
        pre_choice = getattr(story, "curtain_pre_choice", None) if story else None
        if story is not None:
            story.curtain_pre_choice = None
        if pre_choice == "order_puppet_curtain":
            return self._trigger_stage_ending(
                route_key="order",
                choice_flag="ending_stage_gate_order_pre_chosen",
                line="你依照与善良人格的约定，推开补全谢幕之门，由它演完最后一幕并谢幕。",
            )
        return self._trigger_stage_ending(
            route_key="freedom",
            choice_flag="ending_stage_gate_freedom_pre_chosen",
            line="你依照与善良人格的约定，以即兴方式完成最后一幕并谢幕。",
        )

    def _trigger_stage_ending(self, route_key, choice_flag, line):
        self.register_story_choice(choice_flag=choice_flag, moral_delta=0)
        self.add_message(line)
        story = getattr(self.controller, "story", None)
        if story is None:
            return "Event Completed"

        score_payload = _collect_stage_curtain_scores(story)
        ending_payload = _resolve_stage_curtain_outcome(route_key, score_payload)
        outcome_tag = ending_payload.get("outcome_tag", "freedom")
        story.story_tags.add("ending:stage_curtain_completed")
        story.story_tags.add(f"ending:stage_curtain:{outcome_tag}")
        story.choice_flags.add(f"ending_stage_curtain_{outcome_tag}")

        notes = ending_payload.get("notes", [])
        if notes:
            self.add_message(" ".join(notes[:2]))
        prelude_choice = getattr(story, "curtain_prelude_choice", None)
        if prelude_choice:
            prelude_line = _get_curtain_prelude_echo_line(prelude_choice)
            if prelude_line:
                self.add_message(prelude_line)
        for scene_line in list(ending_payload.get("scene_lines", []) or []):
            line = str(scene_line).strip()
            if line:
                self.add_message(line)

        ending_meta = {
            "stage_route_choice": route_key,
            "stage_outcome": outcome_tag,
            "stage_scores": {
                "order": score_payload.get("order", 0),
                "freedom": score_payload.get("freedom", 0),
                "power": score_payload.get("power", 0),
                "risk": score_payload.get("risk", 0),
            },
            "puppet_kind_rescued": bool(score_payload.get("puppet_kind_rescued", False)),
            "stage_script_ready": bool(score_payload.get("stage_script_ready", False)),
            "curtain_speciale": str(ending_payload.get("curtain_speciale", "")).strip(),
            "script_truth_revealed": "curtain_call_truth_revealed" in story.story_tags,
        }
        if prelude_choice:
            ending_meta["curtain_prelude_choice"] = prelude_choice

        trigger_clear = getattr(self.controller, "trigger_game_clear", None)
        if callable(trigger_clear):
            trigger_clear(
                ending_key=ending_payload.get("ending_key", "stage_curtain_freedom"),
                ending_title=ending_payload.get("ending_title", "舞台谢幕"),
                ending_description=ending_payload.get("ending_description", "终幕结束。"),
                ending_meta=ending_meta,
            )
        else:
            self.controller.scene_manager.go_to("game_over_scene")
        return "Event Completed"

    def pick_order(self):
        return self._trigger_stage_ending(
            route_key="order",
            choice_flag="ending_stage_gate_order",
            line="你把剧本压平在掌心，推开了『补全谢幕』之门。",
        )

    def pick_freedom(self):
        return self._trigger_stage_ending(
            route_key="freedom",
            choice_flag="ending_stage_gate_freedom",
            line="你合上剧本只留一页索引，转身推开『即兴谢幕』之门。",
        )

    def pick_power(self):
        return self._trigger_stage_ending(
            route_key="power",
            choice_flag="ending_stage_gate_power",
            line="你把剧本卷成指挥棒，径直推开『接管谢幕』之门。",
        )


class EndingPowerCurtainDirectEvent(Event):
    """接管谢幕直通结局：飞贼未完结或关系普通/恶劣、已击败黑暗木偶、邪恶值中高时，终局门直接导向接管谢幕。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "接管谢幕"
        self.description = (
            "你没有拿到终幕剧本，与银羽飞贼也未曾结下信任；"
            "但黑暗木偶已被你击败，走廊尽头只剩一扇门——以你的方式接管终幕，强行收束演出。"
        )
        self.choices = [
            EventChoice("完成接管谢幕", self._complete_power_curtain),
        ]

    def _complete_power_curtain(self):
        self.register_story_choice(choice_flag="ending_power_curtain_direct", moral_delta=0)
        self.add_message("你以导演代理人身份推开终幕之门，强行接管门廊规则，完成谢幕。")
        story = getattr(self.controller, "story", None)
        # 直通路径使用满足 power>=4、risk<=4 的 payload，确保解析为接管谢幕结局
        score_payload = {
            "power": 4,
            "risk": 0,
            "order": 0,
            "freedom": 0,
            "notes": [],
        }
        ending_payload = _resolve_stage_curtain_outcome("power", score_payload)
        outcome_tag = ending_payload.get("outcome_tag", "power")
        if story is not None:
            story.story_tags.add("ending:stage_curtain_completed")
            story.story_tags.add(f"ending:stage_curtain:{outcome_tag}")
            story.choice_flags.add("ending_stage_curtain_power")
        trigger_clear = getattr(self.controller, "trigger_game_clear", None)
        if callable(trigger_clear):
            trigger_clear(
                ending_key=ending_payload.get("ending_key", "stage_curtain_power"),
                ending_title=ending_payload.get("ending_title", "舞台谢幕·接管谢幕"),
                ending_description=ending_payload.get("ending_description", "你以导演代理人身份接管门廊规则，强行完成谢幕。"),
                ending_meta={
                    "stage_route_choice": "power",
                    "stage_outcome": outcome_tag,
                    "stage_scores": {"order": 0, "freedom": 0, "power": 4, "risk": 0},
                    "puppet_kind_rescued": False,
                    "stage_script_ready": False,
                    "curtain_speciale": "",
                    "script_truth_revealed": False,
                    "power_curtain_direct": True,
                },
            )
        else:
            self.controller.scene_manager.go_to("game_over_scene")
        return "Event Completed"


class EndingPowerCurtainChoiceEvent(Event):
    """结局门：已拿剧本、已击败木偶、邪恶值普通或较高时出现；与「与善良木偶对话」互斥（彼为邪恶值低）。三选一：前两项均为接管谢幕、剧情文本不同，第三项为选择困难症。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "接管终幕"
        self.description = (
            "你已从飞贼处取回剧本，黑暗木偶也被你击败，但木偶的黑暗侧仍占上风，没有善良人格前来约定。"
            "门廊深处，你决定如何收束这场演出：以导演身份强行接管谢幕（两种方式），或转身直面选择困难症候群。"
        )
        self.choices = [
            EventChoice("以规则接管——把终幕写进秩序", self.pick_power_order),
            EventChoice("以意志接管——把终幕握在手中", self.pick_power_will),
            EventChoice("选择困难症", self.pick_default),
        ]

    def _trigger_power_curtain(self, variant: str, line: str, description_lead: str):
        """触发接管谢幕结局，variant 用于区分剧情文案。"""
        self.register_story_choice(choice_flag="ending_power_curtain_choice", moral_delta=0)
        self.add_message(line)
        story = getattr(self.controller, "story", None)
        score_payload = _collect_stage_curtain_scores(story) if story else {}
        ending_payload = _resolve_stage_curtain_outcome("power", score_payload)
        resolved_description = str(ending_payload.get("ending_description", "")).strip()
        final_description = f"{description_lead}{resolved_description}".strip()
        if story is not None:
            story.story_tags.add("ending:stage_curtain_completed")
            story.story_tags.add("ending:stage_curtain:power")
            story.choice_flags.add("ending_stage_curtain_power")
        trigger_clear = getattr(self.controller, "trigger_game_clear", None)
        if callable(trigger_clear):
            trigger_clear(
                ending_key="stage_curtain_power",
                ending_title="舞台谢幕·接管谢幕",
                ending_description=final_description,
                ending_meta={
                    "stage_route_choice": "power",
                    "stage_outcome": "power",
                    "power_curtain_choice_variant": variant,
                    "stage_scores": {
                        "order": score_payload.get("order", 0),
                        "freedom": score_payload.get("freedom", 0),
                        "power": score_payload.get("power", 0),
                        "risk": score_payload.get("risk", 0),
                    },
                    "puppet_kind_rescued": False,
                    "stage_script_ready": bool(score_payload.get("stage_script_ready", False)),
                    "curtain_speciale": "",
                    "script_truth_revealed": "curtain_call_truth_revealed" in (story.story_tags if story else set()),
                },
            )
        else:
            self.controller.scene_manager.go_to("game_over_scene")
        return "Event Completed"

    def pick_power_order(self):
        """接管谢幕·秩序向文案"""
        return self._trigger_power_curtain(
            variant="order",
            line="你选择以规则接管终幕，把谢幕写进秩序。",
            description_lead="你先把终幕切进规则：每盏灯、每道门、每份口供都被你编号归档。随后，",
        )

    def pick_power_will(self):
        """接管谢幕·意志向文案"""
        return self._trigger_power_curtain(
            variant="will",
            line="你选择以意志接管终幕，把谢幕握在手中。",
            description_lead="你先把终幕攥进掌心，不再等任何系统给出许可。随后，",
        )

    def pick_default(self):
        """选择困难症 → 进入普通结局主线（终局第一门 → 第二门 → 选择困难症候群 Boss → 击败后 default_normal）"""
        self.register_story_choice(choice_flag="ending_power_curtain_choice_default", moral_delta=0)
        self.add_message("你选择直面内心的迟疑，走向选择困难症候群把守的终局。")
        self.add_message("下一扇门将通往终局回廊的第一道门——你将在那里做出最后的抉择。")
        _schedule_default_first_gate_for_curtain_choice(self.controller)
        return "Event Completed"


class EndingPuppetEchoAftermathEvent(Event):
    """击败木偶的回声后出现的事件门：前两选为即兴谢幕（剧情文本不同），第三选为选择困难症候群结局。"""
    TRIGGER_BASE_PROBABILITY = 0.0

    @classmethod
    def is_trigger_condition_met(cls, controller):
        return False

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "回声散尽之后"
        self.description = (
            "木偶的回声已碎，走廊里只剩你的脚步。没有钥匙，没有剧本；"
            "你可以把一路抉择当作脚本即兴谢幕，也可以转身走向选择困难症候群把守的终局。"
        )
        self.choices = [
            EventChoice("即兴谢幕——把抉择当作台词", self.pick_impromptu_a),
            EventChoice("即兴谢幕——向虚空鞠躬", self.pick_impromptu_b),
            EventChoice("选择困难症", self.pick_default),
        ]

    def _trigger_impromptu(self, line: str, description: str) -> str:
        """触发即兴谢幕结局，文案由调用方传入。"""
        self.add_message(line)
        story = getattr(self.controller, "story", None)
        final_description = description
        if story is not None:
            score_payload = _collect_stage_curtain_scores(story)
            extra_epilogue = "".join(_build_stage_epilogue_lines("freedom", score_payload))
            if extra_epilogue:
                final_description = f"{description}{extra_epilogue}"
        if story is not None:
            story.story_tags.add("ending:stage_curtain_completed")
            story.story_tags.add("ending:stage_curtain:freedom")
            story.choice_flags.add("ending_stage_curtain_freedom")
        ending_meta = {}
        if story and hasattr(story, "_build_final_ending_meta") and callable(getattr(story, "_build_final_ending_meta")):
            ending_meta = story._build_final_ending_meta()
        ending_meta["puppet_echo_final"] = True
        trigger_clear = getattr(self.controller, "trigger_game_clear", None)
        if callable(trigger_clear):
            trigger_clear(
                ending_key="stage_curtain_freedom",
                ending_title="舞台谢幕·即兴谢幕",
                ending_description=final_description,
                ending_meta=ending_meta,
            )
        else:
            self.controller.scene_manager.go_to("game_over_scene")
        return "Event Completed"

    def pick_impromptu_a(self):
        """即兴谢幕·把抉择当作台词"""
        return self._trigger_impromptu(
            "你选择把一路抉择当作唯一的台词，即兴完成最后一幕。",
            "你没有拿到剧本，与银羽也未曾结下信任；但在终局门前你击败了木偶的回声——"
            "那些回荡在走廊里的选择与代价，都成了你即兴谢幕的台词。没有剧本，"
            "你向虚空中的观众鞠躬，完成了只属于你的终幕。",
        )

    def pick_impromptu_b(self):
        """即兴谢幕·向虚空鞠躬"""
        return self._trigger_impromptu(
            "你选择以即兴之姿收束终幕，向虚空鞠躬。",
            "木偶的回声碎裂之后，你没有剧本可依，也没有银羽的约定可循；"
            "你只是把门廊里复诵过的抉择一一收起，即兴完成最后一幕，向虚空鞠躬。"
            "终幕只属于你。",
        )

    def pick_default(self):
        """选择困难症 → 进入普通结局主线（终局第一门 → 第二门 → 选择困难症候群 Boss → 击败后 default_normal）"""
        self.register_story_choice(choice_flag="ending_puppet_echo_aftermath_default", moral_delta=0)
        self.add_message("你选择直面内心的迟疑，走向选择困难症候群把守的终局。")
        self.add_message("下一扇门将通往终局回廊的第一道门——你将在那里做出最后的抉择。")
        _schedule_default_first_gate_for_curtain_choice(self.controller)
        return "Event Completed"


def _dream_well_chain_done(story):
    """梦境井长链是否已完结：封井/卖梦直接完结；喝下则需回声法庭任一选项。"""
    flags = set(getattr(story, "choice_flags", set()))
    if "dream_well_sealed" in flags or "dream_well_sold" in flags:
        return True
    if "dream_well_drank" in flags and (
        "echo_court_redeemed" in flags or "echo_court_taxed" in flags or "echo_court_trading" in flags
    ):
        return True
    return False


def _mirror_theater_chain_done(story):
    """镜面剧场长链是否已完结：英雄/恶徒/撕本任一选项。"""
    flags = set(getattr(story, "choice_flags", set()))
    return (
        "mirror_played_hero" in flags
        or "mirror_played_villain" in flags
        or "mirror_tore_script" in flags
    )


def _should_trigger_dream_mirror_prelude(controller):
    """是否挂载梦境镜面回响门：两长链皆已完结且在倒数窗口内。"""
    story = getattr(controller, "story", None)
    if story is None:
        return False
    if not _dream_well_chain_done(story):
        return False
    if not _mirror_theater_chain_done(story):
        return False
    cfg = _get_pre_final_gate_config("dream_mirror_prelude_gate")
    cid = str(cfg.get("consequence_id", "ending_dream_mirror_prelude_gate"))
    if cid in getattr(story, "pending_consequences", {}) or cid in getattr(story, "consumed_consequences", set()):
        return False
    return True


def _schedule_dream_mirror_prelude_gate(controller, *, min_round=None, max_round=None):
    """倒数窗口内挂载「梦境与镜面回响」事件门（非阻塞）。"""
    if not _should_trigger_dream_mirror_prelude(controller):
        return False
    return _schedule_pre_final_gate(
        controller=controller,
        gate_key="dream_mirror_prelude_gate",
        min_round=min_round,
        max_round=max_round,
    )


def _should_trigger_elf_rival_pre_final(controller):
    """终局前插入飞贼对决：精灵线收束且关系极差时触发。"""
    story = getattr(controller, "story", None)
    if story is None:
        return False
    if not bool(getattr(story, "elf_chain_ended", False)):
        return False
    rel = int(getattr(story, "elf_relation", 0))
    return rel <= -4


def _schedule_elf_rival_final_gate(controller, *, min_round=None, max_round=None):
    """在默认终局 Boss 前插入一次银羽飞贼追猎战。"""
    story = getattr(controller, "story", None)
    if story is None:
        return False
    if not _should_trigger_elf_rival_pre_final(controller):
        return False
    if (
        "ending:elf_rival_final_gate_done" in story.story_tags
        or "ending:elf_rival_parted" in story.story_tags
    ):
        return False
    cfg = _get_pre_final_gate_config("elf_rival_final_gate")
    consequence_id = str(cfg.get("consequence_id", "ending_elf_rival_final_gate"))
    if consequence_id in story.pending_consequences or consequence_id in getattr(story, "consumed_consequences", set()):
        return False
    rel = int(getattr(story, "elf_relation", 0))
    style = "vengeful" if rel <= -5 else "trickster"
    profile_extensions = []
    if "ending_hook:elf_hostile" in story.story_tags:
        profile_extensions.append("ending_hook_hunted")
    if "elf_outcome_hostile" in story.choice_flags or "elf_outcome:hostile" in story.story_tags:
        profile_extensions.append("hostile_outcome")
    if rel <= -5:
        profile_extensions.append("deep_grudge")
    payload = {
            "style": style,
            "relation": rel,
            "extensions": profile_extensions,
    }
    return _schedule_pre_final_gate(
        controller=controller,
        gate_key="elf_rival_final_gate",
        min_round=min_round,
        max_round=max_round,
        extra_payload=payload,
    )


def _should_trigger_puppet_pre_final_gate(controller):
    """木偶终战曾逃跑时，在默认终局前插入一次黑暗木偶补战。"""
    story = getattr(controller, "story", None)
    if story is None:
        return False
    tags = set(getattr(story, "story_tags", set()))
    if "ending:default_normal_completed" in tags or "ending:stage_curtain_completed" in tags:
        return False
    if "ending:puppet_rematch_gate_done" in tags:
        return False
    if "ending:puppet_final_defeated" in tags:
        return False
    cfg = _get_pre_final_gate_config("puppet_rematch_gate")
    consequence_id = str(cfg.get("consequence_id", "ending_puppet_pre_final_rematch_gate"))
    if consequence_id in getattr(story, "pending_consequences", {}):
        return False
    if consequence_id in getattr(story, "consumed_consequences", set()):
        return False
    outcome = str(getattr(story, "puppet_final_outcome", "")).strip()
    escaped = outcome == "escaped" or "ending:puppet_final_escape_recorded" in tags
    return escaped


def _schedule_puppet_pre_final_gate(controller, *, min_round=None, max_round=None):
    story = getattr(controller, "story", None)
    if story is None:
        return False
    if not _should_trigger_puppet_pre_final_gate(controller):
        return False
    tags = set(getattr(story, "story_tags", set()))
    escaped_before = (
        "ending:puppet_final_escape_recorded" in tags
        or str(getattr(story, "puppet_final_outcome", "")).strip() == "escaped"
    )
    if escaped_before:
        payload = {
            "hint": "你刚摸到最终门把，背后又响起那段熟悉的失真童谣——它追来了。",
            "message": "你以为上次抽身就算结束，结果走廊再次弹出怪物门。黑暗木偶拖着火花扑来：'还没轮到你谢幕。'",
        }
    else:
        payload = {
            "hint": "木偶线仍未收束，门框上的红噪光纹提示你必须先清掉这段旧账。",
            "message": "你准备进入最终结局前，回廊先被红噪信号改写：一扇黑暗木偶战斗门强行升起。",
        }
    scheduled = _schedule_pre_final_gate(
        controller=controller,
        gate_key="puppet_rematch_gate",
        min_round=min_round,
        max_round=max_round,
        extra_payload=payload,
    )
    if scheduled:
        story.story_tags.add("ending:puppet_rematch_gate_pending")
    return scheduled


def schedule_next_pre_final_gate(
    controller,
    *,
    include_default_final_boss=True,
    min_round=None,
    max_round=None,
):
    """统一调度最终结局前的事件门/战斗门链。"""
    for gate_key in PRE_FINAL_DISPATCH_ORDER:
        if gate_key == "puppet_rematch_gate":
            if _schedule_puppet_pre_final_gate(controller, min_round=min_round, max_round=max_round):
                return gate_key
        elif gate_key == "elf_rival_final_gate":
            if _schedule_elf_rival_final_gate(controller, min_round=min_round, max_round=max_round):
                return gate_key
        elif gate_key == "dream_mirror_prelude_gate":
            if _schedule_dream_mirror_prelude_gate(controller, min_round=min_round, max_round=max_round):
                return gate_key
        elif gate_key == "default_final_boss_gate":
            if include_default_final_boss and _schedule_default_ending_final_boss(controller):
                return gate_key
    return None


class EndingFinalFirstGateEvent(Event):
    """普通结局主线：回合 200 强制进入的第一道终局门。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "终局回廊·第一门"
        self.description = (
            "你走到迷宫尽头，墙体翻转出三道写着不同字句的门。"
            "门牌像在嘲笑你此前的犹豫：『快一点』『再想想』『都可以』。"
        )
        self.choices = [
            EventChoice("推开『快一点』之门", self.pick_hasty_gate),
            EventChoice("推开『再想想』之门", self.pick_hesitate_gate),
            EventChoice("推开『都可以』之门", self.pick_whatever_gate),
        ]

    def _record_choice_and_schedule(self, choice_flag, line):
        self.register_story_choice(choice_flag=choice_flag, moral_delta=0)
        self.add_message(line)
        scheduled = _schedule_default_ending_forced_event(
            controller=self.controller,
            gate_key="default_second_gate_event",
        )
        if scheduled:
            self.add_message("门后的走廊折叠成新的岔路，下一轮你还得再选一次。")
        else:
            self.add_message("走廊短暂震动后恢复平静，像是在等待你继续前进。")
        return "Event Completed"

    def pick_hasty_gate(self):
        return self._record_choice_and_schedule(
            choice_flag="ending_default_first_gate_hasty",
            line="你咬牙加速，先推开了写着『快一点』的门。",
        )

    def pick_hesitate_gate(self):
        return self._record_choice_and_schedule(
            choice_flag="ending_default_first_gate_hesitate",
            line="你还是停下来反复确认，最终推开了『再想想』那扇门。",
        )

    def pick_whatever_gate(self):
        return self._record_choice_and_schedule(
            choice_flag="ending_default_first_gate_whatever",
            line="你叹了口气：'都到这了随便吧。' 然后推开了『都可以』之门。",
        )


class EndingFinalSecondGateEvent(Event):
    """普通结局主线：第二道终局门，汇合到默认 Boss。"""

    def __init__(self, controller):
        super().__init__(controller)
        self.title = "终局回廊·第二门"
        self.description = (
            "第二段走廊更安静，三道门上只剩简短刻痕：『左』『中』『右』。"
            "你意识到无论怎么选，迷宫都在逼你把犹豫走完。"
        )
        self.choices = [
            EventChoice("走左门", self.pick_left_gate),
            EventChoice("走中门", self.pick_middle_gate),
            EventChoice("走右门", self.pick_right_gate),
        ]

    def _record_choice_and_schedule(self, choice_flag, line):
        self.register_story_choice(choice_flag=choice_flag, moral_delta=0)
        self.add_message(line)
        scheduled = _schedule_default_ending_final_boss(self.controller)
        if scheduled:
            self.add_message("前方只剩最后一扇门，门牌上写着：『请做出最终决定』。")
        else:
            self.add_message("你听见门后有东西在笑，但走廊暂时没有继续变化。")
        return "Event Completed"

    def pick_left_gate(self):
        return self._record_choice_and_schedule(
            choice_flag="ending_default_second_gate_left",
            line="你把手按在左门门把上，深呼吸后推门而入。",
        )

    def pick_middle_gate(self):
        return self._record_choice_and_schedule(
            choice_flag="ending_default_second_gate_middle",
            line="你盯着中央那扇门看了许久，最终还是把它推开。",
        )

    def pick_right_gate(self):
        return self._record_choice_and_schedule(
            choice_flag="ending_default_second_gate_right",
            line="你快步走向右门，像是怕自己又反悔。",
        )

