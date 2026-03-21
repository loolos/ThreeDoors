"""舞台谢幕三路线（order / freedom / power）的尾声文案表，由 `stage_curtain` 逻辑调用。"""

from typing import Any, Dict, List


def build_stage_epilogue_lines(route_key: str, score_payload: Dict[str, Any]) -> List[str]:
    """根据长线选择补充结局尾声文案，仅用于文本展示。"""
    lines: List[str] = []
    elf_outcome = str(score_payload.get("elf_outcome", "")).strip()
    elf_rival_outcome = str(score_payload.get("elf_rival_outcome", "")).strip()
    moon_verdict = str(score_payload.get("moon_verdict", "")).strip()
    ticket_outcome = str(score_payload.get("ticket_outcome", "")).strip()
    dream_outcome = str(score_payload.get("dream_outcome", "")).strip()
    mirror_outcome = str(score_payload.get("mirror_outcome", "")).strip()
    script_truth_revealed = bool(score_payload.get("script_truth_revealed", False))
    diary_source = str(score_payload.get("diary_source", "")).strip()
    puppet_kind_rescued = bool(score_payload.get("puppet_kind_rescued", False))
    dark_pressure = int(score_payload.get("power", 0)) > int(score_payload.get("order", 0)) and int(
        score_payload.get("risk", 0)
    ) >= 4

    if route_key == "order":
        if elf_outcome == "alliance":
            lines.append("谢幕后，银羽飞贼把那枚旧钥匙挂回后台钉板，笑你总算学会了按拍子走路。")
        elif elf_outcome == "neutral":
            lines.append("银羽飞贼没有现身，只在票务口留下一张改过坐标的便签：『你补得不错，剩下我自己改。』")
        elif elf_outcome == "hostile":
            lines.append("银羽飞贼仍在通缉名单上，但安保看到你补全后的终幕记录后，先把追缉令压进了抽屉。")
        if elf_rival_outcome == "victory":
            lines.append("那场终局前对决也被写进排练笔记，飞贼在落款处只写了三个字：『算你赢。』")

        if script_truth_revealed and diary_source == "thief_testimony":
            lines.append("月蚀审判庭最终修订了错案档案，命运乐章失窃案不再由替罪羊背锅。")
        elif moon_verdict == "clean":
            lines.append("月蚀审判庭给你出具了合法结案印章，至少今晚不会再有人追着你核对供词。")
        elif moon_verdict in {"burned", "extorted"}:
            lines.append("你处理月蚀案卷的手法依旧有人记着，后台偶尔会传来『那页到底是谁撕的』低声争执。")

        if ticket_outcome == "calibrated":
            lines.append("齿轮售票亭恢复了正常节拍，查票员把你列进『可协助谢幕的熟面孔』名单。")
        elif ticket_outcome in {"hacked", "sabotaged"}:
            lines.append("票务系统虽然被你按住了故障，但计价员每次看见你都会先摸一下腰间印章，像在防你再改一次账。")

        if dream_outcome == "stabilized":
            lines.append("梦境井的回放被重新封存，回声法庭把你的名字写在『归档协助者』那一栏。")
        elif dream_outcome == "improv":
            lines.append("梦境井里仍偶尔浮出你改写过的桥段，观众把它当作『补全版的彩蛋场』反复观看。")
        elif dream_outcome == "traded":
            lines.append("梦境井交易留下的账目仍在流通，不过这一次你把分成规则写进了公开条款。")

    elif route_key == "freedom":
        if elf_outcome == "alliance":
            lines.append("银羽飞贼在散场后翻上灯桥，朝你抛下一枚假门牌：『下次别走正门，观众更爱彩蛋。』")
        elif elf_outcome == "neutral":
            lines.append("银羽飞贼只远远吹了声口哨，像是承认了这场没有排练的收束。")
        elif elf_outcome == "hostile":
            lines.append("哪怕与你敌对，银羽也不得不承认你把失控舞台即兴收好了，至少今晚没有新的追捕令。")
        if elf_rival_outcome == "parted":
            lines.append("你们在终局前错身而过的背影，后来被走廊小报写成了最受欢迎的『未完待续』。")

        if script_truth_revealed and diary_source:
            lines.append("你把命运乐章真相讲给路过的观众听，他们第一次知道『被通缉的人』和『偷剧本的人』并不是同一个。")
        if moon_verdict == "extorted":
            lines.append("审判庭记得你当年的勒索手笔，却也只能把这场即兴当作完成演出的合法结算。")
        elif moon_verdict == "burned":
            lines.append("被烧掉的案卷让很多细节永远缺页，于是你的终幕版本成了后人默认参考答案。")

        if ticket_outcome == "calibrated":
            lines.append("查票员本想按规矩拦你，最后却把闸机调成了常开，算是给即兴演员的特批。")
        elif ticket_outcome in {"hacked", "sabotaged"}:
            lines.append("计价员追着你跑了半条回廊，最终只追到一句：『账我认，谢幕你别管。』")

        if dream_outcome == "traded":
            lines.append("梦境井商贩把你的终幕复刻成限量回放，标题就叫《没有剧本的那一夜》。")
        elif dream_outcome in {"improv", "stabilized", "taxed"}:
            lines.append("梦境井的水面偶尔仍会重播你那次即兴鞠躬，旁白每次都在最后一句笑场。")

        if mirror_outcome == "hero":
            lines.append("镜面剧场后来把你的剪影放进『英雄面具』展柜，说明牌只写：『会临场发挥的那位。』")
        elif mirror_outcome == "villain":
            lines.append("戴过恶徒面具的你把反派台词改成了笑点，连原本准备喝倒彩的观众都跟着鼓掌。")
        elif mirror_outcome == "tore_script":
            lines.append("你曾撕过剧本的传闻反而成了卖点，游客专程来问『那页到底撕得响不响』。")

    elif route_key == "power":
        if elf_outcome == "alliance":
            lines.append("银羽飞贼与其说是站队，不如说是看热闹；她把你的新规抄成暗号，卖给每一个不怕罚款的闯门者。")
        elif elf_outcome == "neutral":
            lines.append("银羽飞贼保持距离，只在黑市里评价你的新秩序：『有效，但别指望人人买账。』")
        elif elf_outcome == "hostile":
            lines.append("你与银羽飞贼的旧账没结，但她暂时收刀——因为连她都得先研究你改过的门廊规则。")
        if elf_rival_outcome == "victory":
            lines.append("那场你赢下的清算战后来成了安保教材第一页，标题是《别在终局前低估门外的人》。")

        if moon_verdict == "clean":
            lines.append("审判庭认可你的终幕执行结果，却在附注里写明：『此人建议远观，不建议共事。』")
        elif moon_verdict in {"burned", "extorted"}:
            lines.append("案卷的灰烬和勒索的印记都还在，你接管后的第一周就收到三封匿名投诉和一封合作邀请。")

        if ticket_outcome == "calibrated":
            lines.append("你把售票和查票并入同一套指令，连计价员都开始按你的节拍报数。")
        elif ticket_outcome == "hacked":
            lines.append("你保留了自己留下的后门，只是把它改名成『紧急维护通道』。")
        elif ticket_outcome == "sabotaged":
            lines.append("那些被你砸坏又重建的机器如今运转稳定，只是每次开机都先响一声警报，像在提醒谁才是主人。")

        if dream_outcome == "traded":
            lines.append("梦境井回放被纳入分级收费，观众一边抱怨票价，一边排队看你如何改写结尾。")
        elif dream_outcome in {"improv", "stabilized", "taxed"}:
            lines.append("你给梦境井加上了播放上限，回声法庭终于不用每天加班追缴旧账。")

        if dark_pressure:
            lines.append("木偶暗侧留下的控制参数被你当成模板，整座剧场从此学会了先服从、再讨论。")
        elif puppet_kind_rescued:
            lines.append("即便你选择接管，木偶善侧仍替你保留了最后一条软规则：允许迟到的演员补一句真话。")

    return lines


# 与旧 `models.events` 单文件中的私有名一致，供包层 re-export
_build_stage_epilogue_lines = build_stage_epilogue_lines
