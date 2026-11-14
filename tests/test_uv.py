import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError, HTTPError
from north_beach_uv import find_morning_crossing, find_evening_safe, summarize_day, get_forecast

class UVPlannerTests(unittest.TestCase):
    def test_morning_crossing(self):
        hours = [
            {"hour": 10, "uv": 2.15, "clear": 2.15},
            {"hour": 11, "uv": 3.80, "clear": 3.80},
            {"hour": 12, "uv": 5.25, "clear": 5.25},
        ]
        before, after = find_morning_crossing(hours)
        self.assertEqual((before["hour"], after["hour"]), (11, 12))

    def test_evening_after_last_high_uv_not_midafternoon_cloud_dip(self):
        hours = [
            {"hour": 12, "uv": 5.25, "clear": 5.25},
            {"hour": 13, "uv": 6.10, "clear": 6.10},
            {"hour": 14, "uv": 3.65, "clear": 6.30},
            {"hour": 15, "uv": 3.10, "clear": 5.75},
            {"hour": 16, "uv": 4.60, "clear": 4.60},
            {"hour": 17, "uv": 3.00, "clear": 3.00},
            {"hour": 18, "uv": 1.35, "clear": 1.35},
        ]
        self.assertEqual(find_evening_safe(hours)["hour"], 17)
        self.assertEqual(find_evening_safe(hours, "clear")["hour"], 17)

    def test_summary_uses_conservative_buffer(self):
        rows = [
            {"hour": 10, "uv": 2.15, "clear": 2.15},
            {"hour": 11, "uv": 3.80, "clear": 3.80},
            {"hour": 12, "uv": 5.25, "clear": 5.25},
            {"hour": 16, "uv": 4.55, "clear": 4.60},
            {"hour": 17, "uv": 1.20, "clear": 3.00},
            {"hour": 18, "uv": 1.15, "clear": 1.35},
        ]
        result = summarize_day({"date": "2026-10-24", "hours": rows})
        self.assertEqual(result["morning_uv4_interval"], "11 AM–12 PM")
        self.assertIn("10:30 AM–10:45 AM", result["suggested_departure"])
        self.assertEqual(result["evening_first_uv3_hour"], "5 PM")

    def test_below_four_all_day(self):
        result = summarize_day({"date": "2026-12-20", "hours": [
            {"hour": h, "uv": 2.0, "clear": 3.0} for h in range(7, 19)
        ]})
        self.assertIsNone(result["morning_uv4_interval"])
        self.assertIn("below 4", result["morning_summary"])


    @patch("north_beach_uv.time.sleep")
    @patch("north_beach_uv.urlopen")
    def test_forecast_retries_timeout_then_succeeds(self, mock_open, mock_sleep):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"timezone":"America/New_York"}'
        mock_open.side_effect = [URLError(TimeoutError("handshake timed out")), response]
        self.assertEqual(get_forecast()["timezone"], "America/New_York")
        self.assertEqual(mock_open.call_count, 2)
        mock_sleep.assert_called_once_with(5)

    @patch("north_beach_uv.time.sleep")
    @patch("north_beach_uv.urlopen")
    def test_forecast_does_not_retry_bad_request(self, mock_open, mock_sleep):
        mock_open.side_effect = HTTPError("https://example.com", 400, "Bad Request", {}, None)
        with self.assertRaises(HTTPError):
            get_forecast()
        mock_open.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("north_beach_uv.time.sleep")
    @patch("north_beach_uv.urlopen")
    def test_forecast_gives_up_after_three_timeouts(self, mock_open, mock_sleep):
        mock_open.side_effect = URLError(TimeoutError("handshake timed out"))
        with self.assertRaises(URLError):
            get_forecast()
        self.assertEqual(mock_open.call_count, 3)
        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [5, 10])

if __name__ == "__main__":
    unittest.main()
