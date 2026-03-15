"""终局前门调度配置：统一维护事件门/战斗门文案与基础参数。"""

ALL_PRE_FINAL_DOOR_TYPES = ("TRAP", "REWARD", "MONSTER", "SHOP", "EVENT")


PRE_FINAL_GATE_STORY_CONFIG = {
    # 回合 200：舞台谢幕链前置入口（优先级高于默认终局入口）
    "round200_stage_preface": {
        "choice_flag": "ending_stage_curtain_route",
        "consequence_id": "ending_stage_curtain_preface",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1260,
        "payload": {
            "event_key": "ending_stage_script_vault_event",
            "hint": "你怀里的旧钥匙忽然发热，像在指向终局前的一扇隐藏事件门。",
            "message": "【终局分歧】银羽留给你的钥匙突然自行转动，走廊侧墙弹出一扇带徽记的暗门。",
            "log_trigger": "【回合200·舞台谢幕链】你触发了银羽秘藏前置事件，终局流程被改写。",
        },
    },
    # 回合 200：默认终局入口（第一门）
    "round200_default_first_gate": {
        "choice_flag": "ending_default_normal_gate",
        "consequence_id": "ending_default_force_gate_round_200",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_final_first_gate_event",
            "hint": "尽头只剩三扇刻着不同字句的门，像是迷宫在等你做最后一次选择。",
            "message": "【终局前兆】走廊尽头忽然亮起终焉指示灯，三扇最终门从墙体里缓缓推出。",
            "log_trigger": "【回合200·终局锁定】你正要按常规选门，整条走廊的门牌同时翻面，迷宫把你推向最后的抉择。",
        },
    },
    # 默认终局链：第一门后强制第二门事件
    "default_second_gate_event": {
        "choice_flag": "ending_default_normal_route",
        "consequence_id": "ending_default_second_gate",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_final_second_gate_event",
            "hint": "第二道终局门已经亮起，像在催促你继续做决定。",
            "message": "你刚离开第一道门，前方又升起三扇写着不同命运注脚的门。",
            "log_trigger": "你刚离开第一道门，前方又升起三扇写着不同命运注脚的门。",
        },
    },
    # 舞台谢幕链：秘藏后强制谢幕门
    "stage_curtain_gate_event": {
        "choice_flag": "ending_default_normal_route",
        "consequence_id": "ending_stage_curtain_gate",
        "effect_key": "force_story_event",
        "force_door_type": "EVENT",
        "priority": 1200,
        "payload": {
            "event_key": "ending_stage_curtain_gate_event",
            "hint": "你怀里的剧本忽然发热，前方三扇门同时亮起：『补全』『即兴』『接管』。",
            "message": "你收起剧本后，终局走廊被改写成了新的谢幕门廊。",
            "log_trigger": "你收起剧本后，终局走廊被改写成了新的谢幕门廊。",
        },
    },
    # 默认终局链：最终 Boss 门
    "default_final_boss_gate": {
        "choice_flag": "ending_default_normal_route",
        "consequence_id": "ending_default_final_boss_gate",
        "effect_key": "default_final_boss",
        "force_door_type": "MONSTER",
        "priority": 1200,
        "payload": {
            "boss_name": "选择困难症候群",
            "hint": "门缝里传来嬉笑声：'看提示看了两百回合，终于舍得进来啦？'",
            "message": "门后出现一张由问号拼成的笑脸。怪物弯腰行礼：'欢迎来到你的最终选择现场。'",
            "taunts": [
                "“看提示看了两百回合，眼睛还好吗？”",
                "“三扇门你每次都要想半天，这不就是选择困难症吗？”",
                "“来吧，把我打倒，证明你终于会做决定了。”",
            ],
            "log_trigger": "三扇终局门同时闭合，只剩中央一道裂隙。裂隙里钻出的怪物自报家门：『选择困难症候群』。",
        },
    },
    # 默认终局链：敌对银羽拦截战
    "elf_rival_final_gate": {
        "choice_flag": "ending_default_second_gate_rival",
        "consequence_id": "ending_elf_rival_final_gate",
        "effect_key": "elf_rival_final_gate",
        "trigger_door_types": ("MONSTER",),
        "force_door_type": "MONSTER",
        "priority": 1250,
        "payload": {
            "hint": "风里有熟悉的银羽划痕，像是有人专程在终局前截住你。",
            "message": "你刚推开第二道终局门，前方墙体忽然裂开一扇怪物门。银羽斗篷从阴影里掠出：'还没结束，我们把旧账在这里算清。'",
        },
    },
    # 默认终局链：黑暗木偶补战门（木偶线未完结或曾逃跑时插入）
    "puppet_rematch_gate": {
        "choice_flag": "ending_default_second_gate_puppet",
        "consequence_id": "ending_puppet_pre_final_rematch_gate",
        "effect_key": "puppet_dark_boss",
        "trigger_door_types": ("MONSTER",),
        "force_door_type": "MONSTER",
        "priority": 1260,
        "payload": {
            "boss_name": "裂齿·夜魇·游荡残响",
            "phase2_name": "裂齿·夜魇·游荡残响",
            "base_hp": 880,
            "base_atk": 40,
            "tier": 5,
            "hint": "你以为已经甩开那段童谣，门缝里却再度传来熟悉的低频拍点。",
            "message": "你正准备走向最终门廊，侧墙忽然滑开一扇怪物门。失真的童谣再次响起：黑暗木偶追上来了。",
            "no_side_event_message": "这一次它像在复读你曾见过的第一阶段战斗节拍，动作没有收束，只剩追猎意图。",
            "neutral_message": "黑暗木偶没有再展开完全体，只是把旧战记录压缩成一段高频猎杀循环。",
            "disable_phase_two": True,
            "mark_as_final_boss": False,
            "pre_final_dispatch": True,
        },
    },
}


PRE_FINAL_DISPATCH_ORDER = (
    "puppet_rematch_gate",
    "elf_rival_final_gate",
    "default_final_boss_gate",
)
