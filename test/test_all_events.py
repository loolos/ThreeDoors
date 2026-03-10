
import unittest
import unittest.mock
from test.test_base import BaseTest
import models.events as events_module
from server import GameController
from models.events import (
    StrangerEvent, SmugglerEvent, AncientShrineEvent, 
    GamblerEvent, LostChildEvent, CursedChestEvent, WiseSageEvent,
    TimePawnshopEvent, MirrorTheaterEvent,
    MoonBountyEvent, MoonVerdictEvent,
    ClockworkBazaarEvent, CogAuditEvent,
    DreamWellEvent, EchoCourtEvent,
)
from models.items import FlyingHammer

class TestAllEvents(BaseTest):
    
    def _run_choice(self, event_cls, choice_index, setup_func=None):
        """Helper to run a specific choice of an event"""
        event = event_cls(self.controller)
        self.controller.current_event = event
        
        if setup_func:
            setup_func(event, self.player)
            
        # print(f"Testing {event.title} Choice {choice_index}...")
        try:
            event.resolve_choice(choice_index)
        except Exception as e:
            self.fail(f"{event.title} Choice {choice_index} raised exception: {e}")

    @unittest.mock.patch('models.events.create_random_item')
    @unittest.mock.patch('models.events.random.random')
    def test_stranger_choices(self, mock_random, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")
        
        # 1. Help - Success (< 0.7)
        self.player.hp = 100
        self.player.gold = 20
        self.player.clear_inventory()
        mock_random.return_value = 0.1
        self._run_choice(StrangerEvent, 0)
        # Check last 2 messages as item.acquire adds a message after the gratitude text
        self.assertIn("感激", "".join(self.controller.messages[-2:]))
        
        # 2. Help - Betrayal (>= 0.7)
        self.player.hp = 100
        self.player.gold = 20
        mock_random.return_value = 0.8
        initial_hp = self.player.hp
        self._run_choice(StrangerEvent, 0)
        self.assertLess(self.player.hp, initial_hp)
        self.assertIn("忘恩负义", self.controller.messages[-1])

        # 3. Help - No Gold
        self.player.gold = 0
        self._run_choice(StrangerEvent, 0)

        # 4. Rob - Success (< 0.6)
        self.player.hp = 100
        mock_random.return_value = 0.1
        self._run_choice(StrangerEvent, 1)
        self.assertIn("抢走了", self.controller.messages[-1])

        # 5. Rob - Fail (>= 0.6)
        self.player.hp = 100
        mock_random.return_value = 0.7
        initial_hp = self.player.hp
        self._run_choice(StrangerEvent, 1)
        self.assertLess(self.player.hp, initial_hp)
        self.assertIn("反击", self.controller.messages[-1])

        # 6. Ignore
        self._run_choice(StrangerEvent, 2)

    @unittest.mock.patch('models.events.create_random_item')
    @unittest.mock.patch('models.events.random.random')
    def test_smuggler_choices(self, mock_random, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")

        # 1. Buy - Success (< 0.8)
        self.player.gold = 100
        mock_random.return_value = 0.1
        self._run_choice(SmugglerEvent, 0)
        self.assertIn("买到了", self.controller.messages[-1])

        # 2. Buy - Valid (No Gold)
        self.player.gold = 0
        self._run_choice(SmugglerEvent, 0)
        
        # 3. Buy - Fake (>= 0.8)
        self.player.gold = 100
        mock_random.return_value = 0.9
        self._run_choice(SmugglerEvent, 0)
        self.assertIn("石头", self.controller.messages[-1])

        # Report & Leave
        mock_random.return_value = 0.1
        self._run_choice(SmugglerEvent, 1) # Reward
        mock_random.return_value = 0.6
        self._run_choice(SmugglerEvent, 1) # Fail
        
        self._run_choice(SmugglerEvent, 2)

    @unittest.mock.patch('models.events.create_random_item')
    @unittest.mock.patch('models.events.random.random')
    def test_shrine_choices(self, mock_random, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")
        
        # 1. Pray - Success (< 0.7)
        self.player.hp = 50
        mock_random.return_value = 0.1
        self._run_choice(AncientShrineEvent, 0)
        self.assertIn("恢复", self.controller.messages[-1])
        
        # 2. Pray - Curse (>= 0.7)
        self.clear_player_status()
        mock_random.return_value = 0.8
        self._run_choice(AncientShrineEvent, 0)
        from models.status import StatusName
        self.assertTrue(self.player.has_status(StatusName.WEAK))

        mock_random.return_value = 0.1 
        self._run_choice(AncientShrineEvent, 1)
        self._run_choice(AncientShrineEvent, 2)

    def test_gambler_choices(self):
        # 0: High Stakes
        self.player.gold = 100
        self._run_choice(GamblerEvent, 0)
        # 1: Low Stakes
        self.player.gold = 100
        self._run_choice(GamblerEvent, 1)
        # 2: Decline
        self._run_choice(GamblerEvent, 2)

    def test_lost_child_choices(self):
        # 0: Guide Home (might trigger damage)
        self.player.hp = 100
        self._run_choice(LostChildEvent, 0)
        # 1: Give Gold
        self.player.gold = 100
        self._run_choice(LostChildEvent, 1)
        # 2: Ignore
        self._run_choice(LostChildEvent, 2)

    @unittest.mock.patch('models.events.create_random_item')
    def test_cursed_chest_choices(self, mock_create):
        mock_create.return_value = FlyingHammer("TestHammer")
        # 0: Open
        self._run_choice(CursedChestEvent, 0)
        # 1: Purify
        self._run_choice(CursedChestEvent, 1)
        # 2: Leave
        self._run_choice(CursedChestEvent, 2)

    def test_death_in_event(self):
        """Test if player dies during event, scene stays GameOver"""
        # Force low HP
        self.player.hp = 1
        # Remove Revive Scroll to ensure death
        self.player.clear_inventory()
        
        with unittest.mock.patch('models.events.random.random') as mock_rand:
            mock_rand.return_value = 0.1 # < 0.3 triggers damage path
            
            event = LostChildEvent(self.controller)
            self.controller.current_event = event
            
            scene = self.controller.scene_manager.scene_dict["event_scene"]
            self.controller.scene_manager.current_scene = scene
            
            scene.handle_choice(0)
            
            from scenes import SceneType
            self.assertEqual(self.controller.scene_manager.current_scene.enum, SceneType.GAME_OVER)

    @unittest.mock.patch('models.events.random.random')
    def test_sage_choices(self, mock_random):
        # 1. Power - Success (< 0.7)
        self.player.atk = 10
        mock_random.return_value = 0.1
        self._run_choice(WiseSageEvent, 0)
        self.assertEqual(self.player.atk, 13)
        
        # 2. Power - Curse
        self.clear_player_status()
        mock_random.return_value = 0.8
        self._run_choice(WiseSageEvent, 0)
        from models.status import StatusName
        self.assertTrue(self.player.has_status(StatusName.WEAK))

        # 3. Wealth - Success
        self.player.gold = 0
        mock_random.return_value = 0.1
        self._run_choice(WiseSageEvent, 1)
        self.assertEqual(self.player.gold, 200)
        
        # 4. Wealth - Illusion
        mock_random.return_value = 0.8
        self.player.gold = 100
        self._run_choice(WiseSageEvent, 1)
        self.assertLess(self.player.gold, 100)

        # 5. Health - Success
        self.player.hp = 50
        mock_random.return_value = 0.1
        self._run_choice(WiseSageEvent, 2)
        self.assertEqual(self.player.hp, 100)
        
        # 6. Health - Poison
        self.clear_player_status()
        with unittest.mock.patch('models.events.random.random', return_value=0.8):
            self._run_choice(WiseSageEvent, 2)
            self.assertTrue(self.player.has_status(StatusName.FIELD_POISON))

    def test_new_long_chain_starter_event_choices(self):
        self.player.gold = 300
        self._run_choice(TimePawnshopEvent, 0)
        self._run_choice(TimePawnshopEvent, 1)
        self._run_choice(TimePawnshopEvent, 2)

        self._run_choice(MirrorTheaterEvent, 0)
        self._run_choice(MirrorTheaterEvent, 1)
        self._run_choice(MirrorTheaterEvent, 2)

        self._run_choice(MoonBountyEvent, 0)
        self._run_choice(MoonBountyEvent, 1)
        self._run_choice(MoonBountyEvent, 2)

        self._run_choice(ClockworkBazaarEvent, 0)
        self._run_choice(ClockworkBazaarEvent, 1)
        self._run_choice(ClockworkBazaarEvent, 2)

        self._run_choice(DreamWellEvent, 0)
        self._run_choice(DreamWellEvent, 1)
        self._run_choice(DreamWellEvent, 2)

    def test_new_long_chain_followup_event_choices(self):
        self.player.gold = 300
        self._run_choice(MoonVerdictEvent, 0)
        self._run_choice(MoonVerdictEvent, 1)
        self._run_choice(MoonVerdictEvent, 2)

        self._run_choice(CogAuditEvent, 0)
        self._run_choice(CogAuditEvent, 1)
        self._run_choice(CogAuditEvent, 2)

        self._run_choice(EchoCourtEvent, 0)
        self._run_choice(EchoCourtEvent, 1)
        self._run_choice(EchoCourtEvent, 2)

    def test_long_chain_choices_have_immediate_impact(self):
        c = GameController()
        c.player.gold = 100
        MoonBountyEvent(c).resolve_choice(0)
        self.assertEqual(c.player.gold, 92)

        c = GameController()
        c.player.hp = 60
        MoonBountyEvent(c).resolve_choice(1)
        self.assertEqual(c.player.hp, 70)

        c = GameController()
        c.player.gold = 100
        c.player.hp = 100
        MoonBountyEvent(c).resolve_choice(2)
        self.assertEqual(c.player.gold, 118)
        self.assertEqual(c.player.hp, 94)

        c = GameController()
        c.player.gold = 80
        c.player.hp = 70
        MoonVerdictEvent(c).resolve_choice(0)
        self.assertEqual(c.player.gold, 92)
        self.assertEqual(c.player.hp, 76)

        c = GameController()
        c.player.hp = 100
        MoonVerdictEvent(c).resolve_choice(1)
        self.assertEqual(c.player.hp, 88)

        c = GameController()
        c.player.gold = 50
        MoonVerdictEvent(c).resolve_choice(2)
        self.assertEqual(c.player.gold, 72)

        c = GameController()
        c.player.gold = 30
        ClockworkBazaarEvent(c).resolve_choice(0)
        self.assertEqual(c.player.gold, 42)

        c = GameController()
        c.player.gold = 30
        ClockworkBazaarEvent(c).resolve_choice(1)
        self.assertEqual(c.player.gold, 46)

        c = GameController()
        c.player.gold = 30
        c.player.hp = 100
        ClockworkBazaarEvent(c).resolve_choice(2)
        self.assertEqual(c.player.gold, 50)
        self.assertEqual(c.player.hp, 92)

        c = GameController()
        c.player.gold = 100
        CogAuditEvent(c).resolve_choice(0)
        self.assertEqual(c.player.gold, 82)

        c = GameController()
        c.player.gold = 100
        CogAuditEvent(c).resolve_choice(1)
        self.assertEqual(c.player.gold, 124)

        c = GameController()
        c.player.gold = 100
        CogAuditEvent(c).resolve_choice(2)
        self.assertEqual(c.player.gold, 80)

        c = GameController()
        c.player.hp = 60
        DreamWellEvent(c).resolve_choice(0)
        self.assertEqual(c.player.hp, 72)

        c = GameController()
        c.player.hp = 60
        DreamWellEvent(c).resolve_choice(1)
        self.assertEqual(c.player.hp, 68)

        c = GameController()
        c.player.gold = 100
        c.player.hp = 100
        DreamWellEvent(c).resolve_choice(2)
        self.assertEqual(c.player.gold, 126)
        self.assertEqual(c.player.hp, 94)

        c = GameController()
        c.player.hp = 60
        EchoCourtEvent(c).resolve_choice(0)
        self.assertEqual(c.player.hp, 70)

        c = GameController()
        c.player.gold = 100
        EchoCourtEvent(c).resolve_choice(1)
        self.assertEqual(c.player.gold, 85)

        c = GameController()
        c.player.gold = 100
        c.player.hp = 100
        EchoCourtEvent(c).resolve_choice(2)
        self.assertEqual(c.player.gold, 120)
        self.assertEqual(c.player.hp, 92)

    def test_get_random_event_checks_condition_then_probability(self):
        with unittest.mock.patch.object(events_module, "STARTER_EVENT_POOL", [StrangerEvent, SmugglerEvent]):
            with unittest.mock.patch.object(StrangerEvent, "is_trigger_condition_met", return_value=True):
                with unittest.mock.patch.object(SmugglerEvent, "is_trigger_condition_met", return_value=False):
                    with unittest.mock.patch.object(StrangerEvent, "get_trigger_probability", return_value=0.9):
                        with unittest.mock.patch("models.events.random.random", return_value=0.1):
                            event = events_module.get_random_event(self.controller)
        self.assertIsInstance(event, StrangerEvent)

    def test_get_random_event_probability_formula_can_increase_with_state(self):
        self.controller.round_count = 0
        self.player.gold = 0
        low = SmugglerEvent.get_trigger_probability(self.controller)
        self.controller.round_count = 20
        self.player.gold = 100
        high = SmugglerEvent.get_trigger_probability(self.controller)
        self.assertGreater(high, low)

    @unittest.mock.patch("models.events.random.random", return_value=0.1)
    def test_core_event_effect_can_scale_with_progression(self, _):
        early = GameController()
        early.player.hp = 20
        AncientShrineEvent(early).resolve_choice(0)
        early_healed = early.player.hp - 20

        late = GameController()
        late.round_count = 28
        late.player.atk = 24
        late.player.hp = 20
        AncientShrineEvent(late).resolve_choice(0)
        late_healed = late.player.hp - 20

        self.assertGreater(late_healed, early_healed)

    def test_high_intensity_events_are_progression_locked(self):
        self.controller.round_count = 4
        self.player.atk = 6
        self.assertFalse(TimePawnshopEvent.is_trigger_condition_met(self.controller))
        self.assertFalse(MirrorTheaterEvent.is_trigger_condition_met(self.controller))
        self.assertFalse(MoonBountyEvent.is_trigger_condition_met(self.controller))
        self.assertFalse(ClockworkBazaarEvent.is_trigger_condition_met(self.controller))
        self.assertFalse(DreamWellEvent.is_trigger_condition_met(self.controller))

        self.controller.round_count = 26
        self.player.atk = 24
        self.assertTrue(TimePawnshopEvent.is_trigger_condition_met(self.controller))
        self.assertTrue(MirrorTheaterEvent.is_trigger_condition_met(self.controller))
        self.assertTrue(MoonBountyEvent.is_trigger_condition_met(self.controller))
        self.assertTrue(ClockworkBazaarEvent.is_trigger_condition_met(self.controller))
        self.assertTrue(DreamWellEvent.is_trigger_condition_met(self.controller))
