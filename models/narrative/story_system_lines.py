"""story_system 中与终局/木偶/飞贼等流程绑定的固定叙事句。"""

# 结局前倒数窗口：刚挂载阻塞门时的提示
MSG_PRE_FINAL_ELF_RIVAL_REGISTERED = "你在门廊里嗅到熟悉银羽杀意，飞贼清算战即将插入。"
MSG_PRE_FINAL_PUPPET_REMATCH_REGISTERED = "红噪门框开始闪烁，黑暗木偶补战正在逼近。"

# 木偶回声战后
MSG_PUPPET_ECHO_SHATTERED = "木偶的回声在最后一击中碎裂，那些复诵过的选择也随之散入走廊的暗处。"
MSG_PUPPET_ECHO_NO_KEY_SCRIPT = "你没有钥匙，也没有剧本；门廊尽头，你要如何收束这场终幕？"

# 飞贼清算战胜负
MSG_ELF_RIVAL_VICTORY = "她单膝撑地，笑得很勉强：'行，你这次赢了。'"
MSG_ELF_RIVAL_DEFAULT_HINT = "她低声提醒：'终局门里别被第一层答案骗了，真正的出口常藏在第二次选择之后。'"
MSG_ELF_RIVAL_PARTED = "你借着烟幕撤离，她没有追上来，只在远处抛下一句：'下次不用再见了。'"

# 木偶终战击败后
MSG_PUPPET_FINAL_MELODY = "怪物倒下后，走廊响起一段残缺却温柔的收束旋律。"

# 木偶终战逃跑
MSG_PUPPET_FINAL_ESCAPE_FLIGHT = "你借着火花与烟尘冲出核心井，脚步声在空廊里被无限拉长。"
PUPPET_FINAL_ESCAPE_BODY = (
    "你在最后一瞬选择抽身撤离。"
    "机偶没有倒下，它仍沿着那条昏暗走廊来回游荡，"
    "每次转身都像在寻找一个从未兑现的指令。"
    "你离开了战场，却把那段失真童谣永远留在了门后。"
)

# schedule_next_pre_final_gate 战后续链
MSG_AFTER_BATTLE_ELF_RIVAL_GATE = "你刚脱离战斗，走廊另一端又出现一抹银羽杀意。"
MSG_AFTER_BATTLE_PUPPET_REMATCH_WON = "你刚压住战场余震，红噪门框再次亮起：木偶还没彻底罢手。"
MSG_AFTER_BATTLE_PUPPET_REMATCH_FLED = "你抽身退开后，失真童谣又在前方门廊回荡。"

# 默认终局 Boss
MSG_DEFAULT_FINAL_BOSS_DEFEATED = "你击倒了“选择困难症候群”。"
MSG_DEFAULT_NORMAL_EXIT = "你抵达了这座迷宫的出口，从出口离开了。"

# 银羽支线共斗门
MSG_ELF_SIDE_ALLY_WIN = "你们联手解决了敌人。她丢给你一句：'谢了，下次还你。'"
MSG_ELF_SIDE_FLEE = "你转身就跑，背后传来她的骂声与怪物追来的风声。"

# 木偶补战 / 预调度 Boss 入场
MSG_PUPPET_REMATCH_ALARM = "警报弦音与重低鼓点同时拉响。"

# 木偶终战二阶段
MSG_PUPPET_PHASE2_THEME = "失真童谣被重低音撕开，完全体战斗主题开始。"


def format_puppet_phase2_entrance(old_name: str, new_name: str, burst_heal: int, atk: int) -> str:
    return f"{old_name}核心炸裂，{new_name}爆发登场！恢复 {burst_heal} 点生命，攻击抬升至 {atk}。"
