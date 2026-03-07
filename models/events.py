
import random
from models.items import create_random_item
from models.status import StatusName

class EventChoice:
    def __init__(self, text, callback):
        self.text = text
        self.callback = callback

class Event:
    def __init__(self, controller):
        self.controller = controller
        self.title = "Event"
        self.description = "Something happens."
        self.choices = []

    def get_choices(self):
        return [c.text for c in self.choices]

    def resolve_choice(self, index):
        if 0 <= index < len(self.choices):
            return self.choices[index].callback()
        return "Invalid choice."

    def add_message(self, msg):
        self.controller.add_message(msg)
    
    def get_player(self):
        return self.controller.player

    def register_story_choice(self, choice_flag, moral_delta=0, consequences=None):
        story = getattr(self.controller, "story", None)
        if not story:
            return
        story.register_choice(
            choice_flag=choice_flag,
            moral_delta=moral_delta,
            consequences=consequences or [],
        )


# 1. Injured Stranger
class StrangerEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Injured Stranger"
        self.description = "你看到一个满身是血的陌生人倒在路边，看起来非常虚弱。"
        self.choices = [
            EventChoice("救助他 (失去10金币)", self.help_stranger),
            EventChoice("抢劫他", self.rob_stranger),
            EventChoice("无视离开", self.ignore_stranger)
        ]

    def help_stranger(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="stranger_helped",
            moral_delta=8,
            consequences=[
                {
                    "consequence_id": "stranger_help_village_gift",
                    "effect_key": "villagers_gift",
                    "chance": 0.32,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER"],
                    "trigger_monsters": ["土匪", "狼人", "野狼", "小哥布林"],
                    "payload": {"hint": "旧日善意", "message": "你救下的人来自这个族群，对方主动献上宝物。"},
                },
                {
                    "consequence_id": "stranger_help_thief_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.26,
                    "priority": 7,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.2,
                        "atk_ratio": 1.2,
                        "message": "你救人时得罪了打手，他们提前布好了伏击。",
                    },
                },
            ],
        )
        if p.gold >= 10:
            p.gold -= 10
            # 70% Reward, 30% Betrayal
            if random.random() < 0.7:
                self.add_message("你花费10金币为陌生人包扎。")
                item = create_random_item()
                self.add_message(f"陌生人感激地给了你 {item.name} 作为回报！")
                item.acquire(player=p)
            else:
                dmg = 15
                p.take_damage(dmg)
                self.add_message("你刚为他包扎好，他突然拔刀刺向你！")
                self.add_message(f"这个忘恩负义的家伙抢了你的钱就跑了。受到 {dmg} 点伤害。")
        else:
            self.add_message("你囊中羞涩，无法提供帮助，只能遗憾离开。")
        return "Event Completed"

    def rob_stranger(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="stranger_robbed",
            moral_delta=-10,
            consequences=[
                {
                    "consequence_id": "stranger_rob_black_market_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.34,
                    "priority": 7,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.72, "message": "黑市商人认出你的“手法”，给了同路折扣。"},
                },
                {
                    "consequence_id": "stranger_rob_bounty_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.33,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.28,
                        "atk_ratio": 1.18,
                        "message": "你抢劫陌生人的恶行传开，赏金猎人带着怪物来堵你。",
                    },
                },
            ],
        )
        # 60% Success, 40% Fail
        if random.random() < 0.6:
            gold = random.randint(5, 20)
            p.gold += gold
            self.add_message(f"你抢走了陌生人仅剩的 {gold} 金币。你的良心受到了一点谴责。")
        else:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"陌生人突然暴起反击！你受到 {dmg} 点伤害，狼狈逃跑。")
        return "Event Completed"

    def ignore_stranger(self):
        self.register_story_choice(
            choice_flag="stranger_ignored",
            moral_delta=-3,
            consequences=[
                {
                    "consequence_id": "stranger_ignore_guilt_curse",
                    "effect_key": "shrine_curse",
                    "chance": 0.22,
                    "trigger_door_types": ["TRAP", "EVENT"],
                    "payload": {"duration": 1, "message": "你隐约想起那个眼神，动作开始迟滞。"},
                }
            ],
        )
        self.add_message("你冷漠地走开了，不想惹麻烦。")
        return "Event Completed"


# 2. Smuggler
class SmugglerEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Smuggler"
        self.description = "一个看起来鬼鬼祟祟的走私犯向你兜售货物。"
        self.item = create_random_item()
        self.cost = max(10, int(self.item.cost * 0.7)) # 30% off usually
        
        self.choices = [
            EventChoice(f"购买 {self.item.name} ({self.cost}G)", self.buy_item),
            EventChoice("举报他", self.report_smuggler),
            EventChoice("离开", self.leave)
        ]

    def buy_item(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="smuggler_bought_goods",
            moral_delta=-5,
            consequences=[
                {
                    "consequence_id": "smuggler_buy_friend_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.4,
                    "priority": 8,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.65,
                        "message": [
                            "你随口报了个假货编号，掌柜脸色一变，立刻把价格改成了“自己人价”。",
                            "柜台下那本黑账里刚好有你见过的记号，商人什么都没问就给你打了折。",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "smuggler_buy_discount_aftertaste",
                                "effect_key": "black_market_markup",
                                "chance": 0.26,
                                "trigger_door_types": ["SHOP"],
                                "required_flags": ["choice:smuggler_bought_goods"],
                                "payload": {
                                    "ratio": 1.18,
                                    "message": "第二次再去时，对方笑着说：'折扣是入场券，不是终身会员。'",
                                },
                            }
                        ],
                    },
                },
                {
                    "consequence_id": "smuggler_buy_counterfeit_penalty",
                    "effect_key": "black_market_markup",
                    "chance": 0.28,
                    "priority": 6,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.35, "message": "你买过赃物的事被盯上，后续商人趁机抬价。"},
                },
            ],
        )
        if p.gold >= self.cost:
            p.gold -= self.cost
            # 80% Real, 20% Fake
            if random.random() < 0.8:
                self.item.acquire(player=p)
                self.add_message(f"你以 {self.cost}G 的低价买到了 {self.item.name}！")
            else:
                self.add_message("你付了钱，打开包裹一看——里面是一块石头！走私犯早就没影了。")
        else:
            self.add_message("走私犯翻了个白眼：'没钱就滚！'")
        return "Event Completed"

    def report_smuggler(self):
        self.register_story_choice(
            choice_flag="smuggler_reported",
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "smuggler_report_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.35,
                    "priority": 7,
                    "trigger_door_types": ["SHOP", "EVENT", "REWARD"],
                    "payload": {
                        "gold": random.randint(25, 55),
                        "message": [
                            "巡逻队长把一袋赏金塞给你，还嘱咐你下次别单独逞强。",
                            "你以为只是口头感谢，结果卫兵把查扣赃款按功劳分了你一份。",
                        ],
                    },
                },
                {
                    "consequence_id": "smuggler_report_gang_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.32,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.3,
                        "atk_ratio": 1.2,
                        "message": [
                            "你听见巷口有人喊“线人就是他”，下一秒伏击就从阴影里扑了出来。",
                            "走私团伙没来找你讲道理，他们直接把怪物引到了你必经的门后。",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "smuggler_report_aftershock",
                                "effect_key": "black_market_markup",
                                "chance": 0.35,
                                "trigger_door_types": ["SHOP"],
                                "required_flags": ["consumed:smuggler_report_gang_revenge"],
                                "payload": {
                                    "ratio": 1.25,
                                    "message": "你在黑市被认出来了，摊主们统一改了“举报者价”。",
                                },
                            }
                        ],
                    },
                },
            ],
        )
        if random.random() < 0.5:
            reward = random.randint(30, 60)
            self.get_player().gold += reward
            self.add_message(f"卫兵抓住了走私犯，并奖励你 {reward} 金币！")
        else:
            dmg = random.randint(5, 15)
            self.get_player().take_damage(dmg)
            self.add_message(f"走私犯发现了你的意图，把你揍了一顿后跑了！受到 {dmg} 点伤害。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag="smuggler_left", moral_delta=0)
        self.add_message("你摇摇头，转身离开了。")
        return "Event Completed"


# 3. Ancient Shrine
class AncientShrineEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Ancient Shrine"
        self.description = "一座古老的祭坛矗立在森林深处，上面刻满了神秘的符文。"
        self.choices = [
            EventChoice("虔诚祈祷 (恢复50HP)", self.pray),
            EventChoice("破坏祭坛", self.desecrate),
            EventChoice("仔细调查", self.inspect)
        ]

    def pray(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="shrine_prayed",
            moral_delta=4,
            consequences=[
                {
                    "consequence_id": "shrine_pray_bless",
                    "effect_key": "shrine_blessing",
                    "chance": 0.34,
                    "priority": 7,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {"message": "祈祷留下的神圣余辉在关键时刻生效。"},
                },
                {
                    "consequence_id": "shrine_pray_fanatic_hunt",
                    "effect_key": "revenge_ambush",
                    "chance": 0.22,
                    "priority": 6,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"hp_ratio": 1.18, "atk_ratio": 1.15, "message": "祭坛附近的狂信徒误会了你的意图，设下埋伏。"},
                },
            ],
        )
        # 70% Heal, 30% Curse
        if random.random() < 0.7:
            healed = p.heal(50) 
            self.add_message(f"一道温暖的光芒笼罩着你，你的伤势恢复了 {healed} 点！")
        else:
            duration = 3
            p.apply_status(StatusName.WEAK.create_instance(duration=duration, target=p))
            self.add_message(f"祭坛突然喷出一股黑气！你被诅咒了，进入虚弱状态 {duration} 回合。")
        return "Event Completed"

    def desecrate(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="shrine_desecrated",
            moral_delta=-9,
            consequences=[
                {
                    "consequence_id": "shrine_desecrate_curse",
                    "effect_key": "shrine_curse",
                    "chance": 0.45,
                    "priority": 8,
                    "trigger_door_types": ["TRAP", "MONSTER", "EVENT"],
                    "payload": {"duration": 2, "message": "你破坏祭坛的行为引来持续诅咒。"},
                },
                {
                    "consequence_id": "shrine_desecrate_looter_bonus",
                    "effect_key": "guard_reward",
                    "chance": 0.26,
                    "priority": 5,
                    "trigger_door_types": ["REWARD", "SHOP"],
                    "payload": {"gold": random.randint(20, 40), "message": "你记住了祭坛藏宝手法，顺手又捞到一笔。"},
                },
            ],
        )
        gold = random.randint(50, 100)
        p.gold += gold
        self.add_message(f"你在祭坛下挖出了 {gold} 金币！")
        if random.random() < 0.5:
            dmg = 10
            p.take_damage(dmg)
            self.add_message(f"但这触怒了神灵，一道闪电劈中了你！受到 {dmg} 点伤害。")
        return "Event Completed"

    def inspect(self):
        self.register_story_choice(
            choice_flag="shrine_inspected",
            moral_delta=1,
            consequences=[
                {
                    "consequence_id": "shrine_inspect_training",
                    "effect_key": "atk_training",
                    "chance": 0.2,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"delta": 1, "message": "符文学识让你看穿敌人的破绽，攻击微幅提升。"},
                }
            ],
        )
        if random.random() < 0.7:
             self.add_message("你在祭坛后面发现了一个遗落的包裹...")
             item = create_random_item()
             self.add_message(f"里面有 {item.name}！")
             item.acquire(player=self.get_player())
        else:
             self.add_message("你研究了半天，除了一些灰尘什么也没发现。")
        return "Event Completed"

# 4. Gambler Event
class GamblerEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "The Gambler"
        self.description = "一个流浪赌徒向你发起挑战：'想不想玩把大的？'"
        self.choices = [
            EventChoice("玩把大的 (赌50G)", self.high_stakes),
            EventChoice("小玩一把 (赌10G)", self.low_stakes),
            EventChoice("拒绝", self.decline)
        ]

    def high_stakes(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="gambler_high_stakes",
            moral_delta=-2,
            consequences=[
                {
                    "consequence_id": "gambler_high_debtor_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.31,
                    "priority": 7,
                    "trigger_door_types": ["MONSTER"],
                    "payload": {"hp_ratio": 1.23, "atk_ratio": 1.2, "message": "赌局输家雇了打手，你被截杀。"},
                },
                {
                    "consequence_id": "gambler_high_hot_hand_bonus",
                    "effect_key": "guard_reward",
                    "chance": 0.28,
                    "priority": 6,
                    "trigger_door_types": ["REWARD", "SHOP"],
                    "payload": {"gold": random.randint(25, 55), "message": "你手气正旺，后续交易也有额外进账。"},
                },
            ],
        )
        bet = 50
        if p.gold < bet:
            self.add_message("你没有足够的金币！赌徒嘲笑了你一番。")
            return "Event Completed"
        
        p.gold -= bet
        if random.random() < 0.4: # 40% win rate
            win = bet * 3
            p.gold += win
            self.add_message(f"你运气爆棚！赢了 {win} 金币！")
        else:
            self.add_message("你输了！50金币打水漂了。")
        return "Event Completed"

    def low_stakes(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="gambler_low_stakes",
            moral_delta=-1,
            consequences=[
                {
                    "consequence_id": "gambler_low_small_revenge",
                    "effect_key": "lose_gold",
                    "chance": 0.2,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": random.randint(10, 20), "message": "你被赌徒顺走了点钱，事后才发现。"},
                },
                {
                    "consequence_id": "gambler_low_lucky_tip",
                    "effect_key": "black_market_discount",
                    "chance": 0.22,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.82, "message": "赌徒给你的小道消息，让你捡了便宜。"},
                },
            ],
        )
        bet = 10
        if p.gold < bet:
             self.add_message("你连10金币都没有？真可怜。")
             return "Event Completed"
        
        p.gold -= bet
        if random.random() < 0.5: # 50% win rate
            win = bet * 2
            p.gold += win
            self.add_message(f"不错，赢了 {win} 金币。")
        else:
            self.add_message("哎呀，运气不好，输了10金币。")
        return "Event Completed"

    def decline(self):
        self.register_story_choice(
            choice_flag="gambler_declined",
            moral_delta=2,
            consequences=[
                {
                    "consequence_id": "gambler_decline_prudent_bless",
                    "effect_key": "shrine_blessing",
                    "chance": 0.25,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {"message": "克制欲望带来的专注，让你更容易避开危险。"},
                },
                {
                    "consequence_id": "gambler_decline_mocked_markup",
                    "effect_key": "black_market_markup",
                    "chance": 0.15,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.2, "message": "你拒绝赌局得罪了地头蛇，熟人商店也不给你好脸色。"},
                },
            ],
        )
        self.add_message("你拒绝了赌博，赌徒无趣地走开了。")
        return "Event Completed"


# 5. Lost Child Event
class LostChildEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Lost Child"
        self.description = "一个小女孩在森林里哭泣，看起来迷路了。"
        self.choices = [
            EventChoice("护送回家", self.guide_home),
            EventChoice("给点金币路费 (20G)", self.give_gold),
            EventChoice("无视", self.ignore)
        ]

    def guide_home(self):
        self.register_story_choice(
            choice_flag="lost_child_guided_home",
            moral_delta=10,
            consequences=[
                {
                    "consequence_id": "lost_child_village_gift",
                    "effect_key": "villagers_gift",
                    "chance": 0.38,
                    "priority": 8,
                    "trigger_door_types": ["MONSTER"],
                    "trigger_monsters": ["土匪", "狼人", "野狼", "食人魔"],
                    "payload": {
                        "hint": "小女孩的谢礼",
                        "message": [
                            "你正要拔剑，对方却把武器倒插在地上：'你救过我们村的小孩，这仗不打。'",
                            "怪物没冲上来，反而递来一个包裹：'欠你的，不是命，是人情。'",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "lost_child_village_scout_tip",
                                "effect_key": "atk_training",
                                "chance": 0.28,
                                "trigger_door_types": ["MONSTER", "EVENT"],
                                "required_flags": ["choice:lost_child_guided_home"],
                                "payload": {
                                    "delta": 1,
                                    "message": "村里的猎人后来给你演示了两招，出手更稳了。",
                                },
                            }
                        ],
                    },
                },
                {
                    "consequence_id": "lost_child_fame_backfire",
                    "effect_key": "revenge_ambush",
                    "chance": 0.27,
                    "priority": 7,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {
                        "hp_ratio": 1.2,
                        "atk_ratio": 1.18,
                        "message": [
                            "“专挑好人下手”不是笑话——赏金猎人把你当成了最值钱的目标。",
                            "你的名声救过人，也暴露了行踪；埋伏的人比感谢你的人先到。",
                        ],
                    },
                },
            ],
        )
        # High risk (time/encounter), High reward
        if random.random() < 0.3:
            # Encounter monster logic could be complex, for now simple damage from "exhaustion"
            dmg = 15
            self.get_player().take_damage(dmg)
            self.add_message(f"送回家的路上遭遇了野兽袭击，你为了保护孩子受了伤 ({dmg}点伤害)，但最终把她安全送达。")
            # Reward
            reward = 100
            self.get_player().gold += reward
            self.add_message(f"孩子的父母感激涕零，给了你 {reward} 金币作为谢礼！")
        else:
            reward = 50
            self.get_player().gold += reward
            self.add_message(f"你顺利把孩子送回了家。她父母给了你 {reward} 金币。")
        return "Event Completed"

    def give_gold(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="lost_child_gave_gold",
            moral_delta=6,
            consequences=[
                {
                    "consequence_id": "lost_child_give_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.3,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"gold": random.randint(15, 35), "heal": 5, "message": "你资助孩子的事被传开，路人对你伸出了援手。"},
                },
                {
                    "consequence_id": "lost_child_give_pickpocket",
                    "effect_key": "lose_gold",
                    "chance": 0.23,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": random.randint(12, 28), "message": "你出手阔绰被人盯上，后来被顺走了一笔钱。"},
                },
            ],
        )
        if p.gold >= 20:
            p.gold -= 20
            self.add_message("你给了小女孩20金币让她自己打车回家（虽然森林里没有出租车）。")
            # Karma reward (small heal)
            p.heal(10)
            self.add_message("做善事让你心情愉悦，恢复了 10 HP。")
        else:
            self.add_message("你想帮忙但没钱，只能尴尬地安慰了几句。")
        return "Event Completed"

    def ignore(self):
        self.register_story_choice(
            choice_flag="lost_child_ignored",
            moral_delta=-8,
            consequences=[
                {
                    "consequence_id": "lost_child_ignore_curse",
                    "effect_key": "shrine_curse",
                    "chance": 0.33,
                    "trigger_door_types": ["TRAP", "MONSTER", "EVENT"],
                    "payload": {"duration": 2, "message": "你心底的不安挥之不去，战斗时更易露出破绽。"},
                },
                {
                    "consequence_id": "lost_child_ignore_black_market",
                    "effect_key": "black_market_discount",
                    "chance": 0.25,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.78, "message": "冷酷名声让地下商人觉得你“够狠”，愿意给折扣。"},
                },
            ],
        )
        self.add_message("这里是残酷的世界，你选择了无视。")
        return "Event Completed"


# 6. Cursed Chest
class CursedChestEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Cursed Chest"
        self.description = "一个散发着诡异紫光的宝箱，上面刻着警告语：'贪婪者必受惩罚'。"
        self.choices = [
            EventChoice("强行打开", self.open_chest),
            EventChoice("试图净化", self.purify),
            EventChoice("离开", self.leave)
        ]

    def open_chest(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="cursed_chest_opened",
            moral_delta=-4,
            consequences=[
                {
                    "consequence_id": "chest_open_curse_follow",
                    "effect_key": "shrine_curse",
                    "chance": 0.36,
                    "trigger_door_types": ["MONSTER", "TRAP", "EVENT"],
                    "payload": {"duration": 2, "message": "贪婪的回响仍缠着你，诅咒持续发作。"},
                },
                {
                    "consequence_id": "chest_open_rogue_profit",
                    "effect_key": "black_market_discount",
                    "chance": 0.24,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.8, "message": "你敢开诅咒箱的名声传到黑市，商人愿和你做“高风险生意”。"},
                },
            ],
        )
        if random.random() < 0.6: # 60% bad
            dmg = 20
            p.take_damage(dmg)
            self.add_message(f"宝箱突然咬了你一口！受到 {dmg} 点巨大伤害。里面什么也没有。")
        else:
            item = create_random_item()
            item.acquire(player=p)
            gold = 100
            p.gold += gold
            self.add_message(f"你忍受着诅咒的侵蚀打开了箱子，获得了 {item.name} 和 {gold} 金币！")
        return "Event Completed"

    def purify(self):
        self.register_story_choice(
            choice_flag="cursed_chest_purified",
            moral_delta=5,
            consequences=[
                {
                    "consequence_id": "chest_purify_blessing",
                    "effect_key": "shrine_blessing",
                    "chance": 0.32,
                    "trigger_door_types": ["TRAP", "MONSTER"],
                    "payload": {"message": "你净化诅咒后的灵力在下一次危险中保护了你。"},
                },
                {
                    "consequence_id": "chest_purify_cult_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.22,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"hp_ratio": 1.18, "atk_ratio": 1.16, "message": "崇拜诅咒宝箱的邪教徒盯上了你。"},
                },
            ],
        )
        # Assume successful purify for now, or random
        if random.random() < 0.5:
            gold = 50
            self.get_player().gold += gold
            self.add_message(f"你成功净化了诅咒，箱子里只剩下一些普通的财宝 ({gold}G)。")
        else:
            self.add_message("你的净化失败了，箱子消失在虚空中。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag="cursed_chest_left", moral_delta=1)
        self.add_message("你明智地远离了诅咒之物。")
        return "Event Completed"


# 7. Wise Sage
class WiseSageEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Wise Sage"
        self.description = "一位白胡子老者拦住了去路：'年轻的勇士，为了什么而战？'"
        self.choices = [
            EventChoice("为了力量 (加攻击)", self.power),
            EventChoice("为了财富 (加金币)", self.wealth),
            EventChoice("为了生存 (恢复50HP)", self.health)
        ]

    def power(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="sage_power_choice",
            moral_delta=-1,
            consequences=[
                {
                    "consequence_id": "sage_power_training",
                    "effect_key": "atk_training",
                    "chance": 0.3,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"delta": 2, "message": "老者的教诲回响在你脑海，出手更加凌厉。"},
                },
                {
                    "consequence_id": "sage_power_backlash",
                    "effect_key": "shrine_curse",
                    "chance": 0.22,
                    "trigger_door_types": ["MONSTER", "TRAP"],
                    "payload": {"duration": 2, "message": "你对力量的执念引发反噬，行动变得沉重。"},
                },
            ],
        )
        if random.random() < 0.7:
            self.add_message("老者点了点头：'力量是双刃剑。'")
            p.change_base_atk(3)
        else:
            duration = 3
            p.apply_status(StatusName.WEAK.create_instance(duration=duration, target=p))
            self.add_message(f"老者摇头：'你渴望力量，却被力量吞噬。' 你变得虚弱了 ({duration}回合)。")
        return "Event Completed"

    def wealth(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="sage_wealth_choice",
            moral_delta=-3,
            consequences=[
                {
                    "consequence_id": "sage_wealth_windfall",
                    "effect_key": "guard_reward",
                    "chance": 0.28,
                    "trigger_door_types": ["SHOP", "REWARD", "EVENT"],
                    "payload": {"gold": random.randint(30, 70), "message": "你嗅到财富机会，后续顺手就赚了一笔。"},
                },
                {
                    "consequence_id": "sage_wealth_fine",
                    "effect_key": "lose_gold",
                    "chance": 0.3,
                    "trigger_door_types": ["SHOP", "EVENT"],
                    "payload": {"amount": random.randint(20, 50), "message": "你的逐利行为引来盘查，被罚了一笔钱。"},
                },
            ],
        )
        if random.random() < 0.7:
            gold = 200
            p.gold += gold
            self.add_message(f"老者叹了口气：'身外之物。' 他丢给你 {gold} 金币后消失了。")
        else:
            lost = min(p.gold, 50)
            p.gold -= lost
            self.add_message(f"老者手一挥，你口袋里的 {lost} 金币变成了石头。'贪婪是原罪。'")
        return "Event Completed"

    def health(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="sage_health_choice",
            moral_delta=4,
            consequences=[
                {
                    "consequence_id": "sage_health_guard_help",
                    "effect_key": "guard_reward",
                    "chance": 0.27,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"gold": random.randint(10, 30), "heal": 8, "message": "你重视生存的态度感染了路人，获得援助。"},
                },
                {
                    "consequence_id": "sage_health_dependency",
                    "effect_key": "black_market_markup",
                    "chance": 0.2,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.25, "message": "你显得过于求稳，被商人看穿后趁机抬价。"},
                },
            ],
        )
        if random.random() < 0.7:
            p.heal(50)
            self.add_message("老者微笑道：'活着就有希望。' 你的生命值恢复了 50 点。")
        else:
            duration = 3
            p.apply_status(StatusName.FIELD_POISON.create_instance(duration=duration, target=p))
            self.add_message(f"老者给你喝了一杯水，你却感到腹痛。'不仅是身体，心灵也需净化。' 你中毒了 ({duration}回合)。")
        return "Event Completed"


class RefugeeCaravanEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Refugee Caravan"
        self.description = "一支逃难车队拦住了你，他们请求食物与路费。"
        self.choices = [
            EventChoice("捐助 25G", self.donate),
            EventChoice("索要保护费", self.extort),
            EventChoice("假装没看见", self.walk_away),
        ]

    def donate(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="caravan_donated",
            moral_delta=7,
            consequences=[
                {
                    "consequence_id": "caravan_donate_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.35,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 0.7, "message": "车队里有人是商会亲属，后续商店给你打了折。"},
                },
                {
                    "consequence_id": "caravan_donate_bandit_envy",
                    "effect_key": "revenge_ambush",
                    "chance": 0.24,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"hp_ratio": 1.2, "atk_ratio": 1.16, "message": "你帮助难民的事惹怒了劫匪，他们要拿你开刀。"},
                },
            ],
        )
        if p.gold >= 25:
            p.gold -= 25
            self.add_message("你捐出了 25 金币，车队成员向你致谢。")
        else:
            self.add_message("你想捐助，但钱不够。")
        return "Event Completed"

    def extort(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="caravan_extorted",
            moral_delta=-9,
            consequences=[
                {
                    "consequence_id": "caravan_extort_markup",
                    "effect_key": "black_market_markup",
                    "chance": 0.38,
                    "trigger_door_types": ["SHOP"],
                    "payload": {"ratio": 1.35, "message": "商会知道你勒索车队后，把你列入高风险名单。"},
                },
                {
                    "consequence_id": "caravan_extort_black_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.27,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.75,
                        "message": [
                            "你的恶名先你一步到了黑市，摊主把价格写低了，语气却更客气了。",
                            "掌柜把算盘往你这边一推：'我们欣赏效率，尤其是你那种。'",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "caravan_extort_enforcer_test",
                                "effect_key": "revenge_ambush",
                                "chance": 0.24,
                                "trigger_door_types": ["MONSTER", "EVENT"],
                                "required_flags": ["choice:caravan_extorted"],
                                "payload": {
                                    "hp_ratio": 1.18,
                                    "atk_ratio": 1.15,
                                    "message": "地下行会想“试试你够不够狠”，于是派人来探底。",
                                },
                            }
                        ],
                    },
                },
            ],
        )
        gain = random.randint(20, 45)
        p.gold += gain
        self.add_message(f"你恐吓了车队，抢到 {gain} 金币。")
        return "Event Completed"

    def walk_away(self):
        self.register_story_choice(choice_flag="caravan_ignored", moral_delta=-2)
        self.add_message("你低头赶路，不愿卷入是非。")
        return "Event Completed"


class FallenKnightEvent(Event):
    def __init__(self, controller):
        super().__init__(controller)
        self.title = "Fallen Knight"
        self.description = "一名重伤骑士倒在路边，盔甲上有王国徽记。"
        self.choices = [
            EventChoice("救治骑士", self.aid_knight),
            EventChoice("搜刮装备", self.loot_knight),
            EventChoice("谨慎离开", self.leave),
        ]

    def aid_knight(self):
        self.register_story_choice(
            choice_flag="knight_aided",
            moral_delta=8,
            consequences=[
                {
                    "consequence_id": "knight_aid_guard_reward",
                    "effect_key": "guard_reward",
                    "chance": 0.36,
                    "trigger_door_types": ["EVENT", "SHOP", "REWARD"],
                    "payload": {"gold": random.randint(20, 50), "heal": 10, "message": "王国巡逻队认出你的善举，给予补给。"},
                },
                {
                    "consequence_id": "knight_aid_traitor_revenge",
                    "effect_key": "revenge_ambush",
                    "chance": 0.23,
                    "trigger_door_types": ["MONSTER", "EVENT"],
                    "payload": {"hp_ratio": 1.2, "atk_ratio": 1.18, "message": "追杀骑士的叛徒盯上了你。"},
                },
            ],
        )
        healed = self.get_player().heal(15)
        self.add_message(f"你为骑士包扎，自己也振作起来，恢复了 {healed} 生命。")
        return "Event Completed"

    def loot_knight(self):
        p = self.get_player()
        self.register_story_choice(
            choice_flag="knight_looted",
            moral_delta=-10,
            consequences=[
                {
                    "consequence_id": "knight_loot_bounty",
                    "effect_key": "lose_gold",
                    "chance": 0.34,
                    "trigger_door_types": ["EVENT", "SHOP"],
                    "payload": {"amount": random.randint(20, 40), "message": "你洗劫骑士的事被追责，花钱才摆平。"},
                },
                {
                    "consequence_id": "knight_loot_underworld_discount",
                    "effect_key": "black_market_discount",
                    "chance": 0.29,
                    "trigger_door_types": ["SHOP"],
                    "payload": {
                        "ratio": 0.74,
                        "message": [
                            "你拿出的徽记还带着血渍，黑市商人却只问了一句：'整套还是散卖？'",
                            "对方认出那是军械制式，压低声音说：'这种货，今天我给你高价低税。'",
                        ],
                        "chain_followups": [
                            {
                                "consequence_id": "knight_loot_witness",
                                "effect_key": "lose_gold",
                                "chance": 0.26,
                                "trigger_door_types": ["EVENT", "SHOP"],
                                "required_flags": ["choice:knight_looted"],
                                "payload": {
                                    "amount": random.randint(15, 35),
                                    "message": "有人认出了那套装备，你花钱才堵住了对方的嘴。",
                                },
                            }
                        ],
                    },
                },
            ],
        )
        gain = random.randint(25, 55)
        p.gold += gain
        self.add_message(f"你扒下骑士身上的值钱物件，获得 {gain} 金币。")
        return "Event Completed"

    def leave(self):
        self.register_story_choice(choice_flag="knight_left", moral_delta=0)
        self.add_message("你不确定这是陷阱，选择绕开。")
        return "Event Completed"


def get_random_event(controller):
    events = [
        StrangerEvent, SmugglerEvent, AncientShrineEvent, 
        GamblerEvent, LostChildEvent, CursedChestEvent, WiseSageEvent,
        RefugeeCaravanEvent, FallenKnightEvent,
    ]
    event_cls = random.choice(events)
    return event_cls(controller)
