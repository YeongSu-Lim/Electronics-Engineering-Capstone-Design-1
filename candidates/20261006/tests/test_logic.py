"""실장비 없이 실행: python -m unittest -v test_logic.py"""
import math
import unittest

from alert_manager import AlertManager
from main import FrameClock, process_tracking_data
from target_selector import Target, TargetSelector
from ttc_calculator import TTCCalculator


def target(ident, ttc, state="DANGER"):
    return Target(ident, "car", (150, 100, 250, 200), ttc, state)


class Detections:
    def __init__(self, rows=()):
        self.tracker_id = [r[0] for r in rows]
        self.class_id = [2] * len(rows)
        self.xyxy = [r[1] for r in rows]

    def __len__(self):
        return len(self.xyxy)


class LogicTests(unittest.TestCase):
    def setUp(self):
        self.calc = TTCCalculator()
        self.selector = TargetSelector()
        self.messages = []
        self.alerts = AlertManager(emit=self.messages.append)

    def frame(self, t, rows=()):
        return process_tracking_data(
            Detections(rows), {2: "car"}, self.calc, self.selector, self.alerts, t
        )

    def approach(self, ident=1):
        for i, size in enumerate([100, 105, 110, 115]):
            result = self.frame(i * .05, [(ident, (150, 100, 150 + size, 100 + size))])
        return result

    def test_original_stale_ttc_regression(self):
        states = [self.calc.update_and_get_fsm(1, s, s, s, timestamp=t)[1]
                  for t, s in [(0, 100), (.1, 110), (.2, 100), (.3, 99)]]
        self.assertEqual(states, ["SAFE", "CAUTION", "SAFE", "SAFE"])

    def test_sustained_approach_and_selected_alert(self):
        all_targets, primary = self.approach()
        self.assertEqual(primary.state, "DANGER")
        self.assertEqual(primary.track_id, 1)
        self.assertEqual(len(self.messages), 2)  # 주의 1회, 위험 승격 1회

    def test_missing_frame_breaks_streak_and_clears_primary(self):
        self.approach()
        _, primary = self.frame(.2)
        self.assertIsNone(primary)
        self.assertEqual(self.calc.danger_streak[1], 0)
        self.assertEqual(len(self.calc.ttc_history[1]), 0)
        self.assertIn(1, self.calc.history)  # 짧은 누락에는 크기 이력을 유지
        targets, _ = self.frame(.25, [(1, (150, 100, 267, 217))])
        self.assertNotEqual(targets[0].state, "DANGER")

    def test_empty_frames_expire_all_per_id_memory(self):
        self.approach()
        self.assertTrue(self.alerts.last_alert)
        self.frame(.7)
        for store in (self.calc.history, self.calc.ttc_history, self.calc.danger_streak,
                      self.calc.last_reason, self.alerts.last_alert):
            self.assertEqual(store, {})
        self.assertIsNone(self.selector.current_id)

    def test_roi_exit_resets_immediately(self):
        self.approach()
        self.frame(.2, [(1, (0, 50, 100, 160))])
        self.assertNotIn(1, self.calc.history)
        self.assertFalse(self.alerts.last_alert)

    def test_many_ids_are_bounded_by_expiry(self):
        for i in range(200):
            self.frame(i * .1, [(i, (150, 100, 250, 200))])
            self.assertLessEqual(len(self.calc.history), 6)
        self.frame(21)
        self.assertFalse(self.calc.history)

    def test_all_candidates_updated_single_target_alerted(self):
        for i, size in enumerate([100, 105, 110, 115]):
            objects, primary = self.frame(i * .05, [
                (1, (150, 100, 150 + size, 100 + size)),
                (2, (300, 100, 300 + size, 100 + size)),
            ])
        self.assertEqual(len(objects), 2)
        self.assertEqual(set(self.calc.history), {1, 2})
        self.assertEqual(primary.track_id, 1)
        self.assertTrue(all("ID:1 " in message for message in self.messages))

    def test_more_severe_target_interrupts_immediately(self):
        self.selector.select([target(1, 1.0, "CAUTION")], 0)
        result = self.selector.select([target(1, 1.0, "CAUTION"), target(2, 1.8)], .01)
        self.assertEqual(result.track_id, 2)

    def test_same_level_switch_margin_and_duration(self):
        self.selector.select([target(1, 2)], 0)
        self.assertEqual(self.selector.select([target(1, 2), target(2, 1.9)], .1).track_id, 1)
        self.assertEqual(self.selector.select([target(1, 2), target(2, 1)], .2).track_id, 1)
        self.assertEqual(self.selector.select([target(1, 2), target(2, 1)], .4).track_id, 1)
        self.assertEqual(self.selector.select([target(1, 2), target(2, 1)], .51).track_id, 2)

    def test_pending_switch_resets_when_advantage_lost(self):
        self.selector.select([target(1, 2)], 0)
        self.selector.select([target(1, 2), target(2, 1)], .1)
        self.selector.select([target(1, 2), target(2, 1.9)], .3)
        self.assertEqual(self.selector.select([target(1, 2), target(2, 1)], .41).track_id, 1)

    def test_lost_primary_falls_back_without_delay(self):
        self.selector.select([target(1, 1)], 0)
        self.assertEqual(self.selector.select([target(2, 4, "CAUTION")], .1).track_id, 2)
        self.assertIsNone(self.selector.select([target(3, math.inf, "SAFE")], .2))

    def test_alert_cooldown_across_target_switches(self):
        self.assertTrue(self.alerts.process(target(1, 1), 0))
        self.assertFalse(self.alerts.process(target(2, .5), .1))
        self.assertTrue(self.alerts.process(target(2, .5), .5))

    def test_frame_clock_uses_source_time(self):
        c = FrameClock("file", "pts")
        self.assertEqual(c.next(0), 0)
        self.assertEqual(c.next(100), .1)
        with self.assertRaises(ValueError):
            c.next(100)
        c = FrameClock("file", "fps", 25)
        self.assertEqual([c.next() for _ in range(3)], [0, .04, .08])

    def test_reset_clears_session(self):
        self.approach()
        self.calc.reset(); self.selector.reset(); self.alerts.reset()
        self.assertFalse(self.calc.history)
        self.assertIsNone(self.selector.current_id)
        self.assertFalse(self.alerts.last_alert)


if __name__ == "__main__":
    unittest.main()
