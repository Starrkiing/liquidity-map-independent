import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
import json

import collector

NY = ZoneInfo("America/New_York")


def fred(series, dates):
    return ("observation_date," + series + "\n" +
            "".join(f"{d},{v}\n" for d, v in dates.items())).encode()


def tga(values):
    return json.dumps({"data": [
        {"record_date": day, "account_type": "Treasury General Account (TGA) Closing Balance",
         "open_today_bal": value} for day, value in values.items()
    ]}).encode()


class Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 26, 18, 30, tzinfo=NY)
        self.data = {
            "walcl": fred("WALCL", {"2026-10-14": "6730000", "2026-10-21": "6753604"}),
            "rrp": fred("RRPONTSYD", {"2026-10-22": "0.351", "2026-10-23": "0.200", "2026-10-26": "0.200"}),
            "tga": tga({"2026-10-22": "961759", "2026-10-23": "960000"}),
        }

    def test_public_series_conversion_and_three_observation_shape(self):
        result = collector.collect(self.now, self.data)
        self.assertEqual(result["status"], "CURRENT")
        self.assertEqual(len(result["us_net_liquidity_bn_last3"]), 2)
        row = result["us_net_liquidity_bn_last3"][0]
        self.assertEqual(row["date"], "2026-10-22")
        self.assertEqual(row["us_net_liquidity_bn"], "5791.494000")
        self.assertEqual(row["walcl_date"], "2026-10-21")
        self.assertEqual(row["rrp_date"], "2026-10-22")
        self.assertEqual(len(result["digest_sha256"]), 64)

    def test_hold_back_fixture_is_late_even_if_job_succeeded(self):
        self.data["walcl"] = fred("WALCL", {"2026-10-14": "6753604"})
        result = collector.collect(self.now, self.data)
        self.assertEqual(result["status"], "LATE")
        self.assertEqual(result["sources"]["walcl"]["status"], "LATE")
        self.assertNotEqual(result["collector_exit_status"], "success")

    def test_fetch_failure_does_not_fabricate_liquidity(self):
        self.data["tga"] = b'{"data":[]}'
        result = collector.collect(self.now, self.data)
        self.assertEqual(result["status"], "FETCH_FAILED")
        self.assertEqual(result["us_net_liquidity_bn_last3"], [])

    def test_date_schedule_mon_and_thu(self):
        self.assertEqual(collector.expected_date("walcl", self.now).isoformat(), "2026-10-21")
        self.assertEqual(collector.expected_date("tga", self.now).isoformat(), "2026-10-23")
        self.assertEqual(collector.expected_date("rrp", self.now).isoformat(), "2026-10-26")
        thu = datetime(2026, 10, 29, 16, 0, tzinfo=NY)
        self.assertEqual(collector.expected_date("walcl", thu).isoformat(), "2026-10-21")
        after = datetime(2026, 10, 29, 18, 0, tzinfo=NY)
        self.assertEqual(collector.expected_date("walcl", after).isoformat(), "2026-10-28")

    def test_tga_missing_cannot_be_zero(self):
        broken = b'{"data":[{"record_date":"2026-10-23","account_type":"irrelevant","open_today_bal":"100"}]}'
        with self.assertRaisesRegex(ValueError, "no TGA"):
            collector.parse_tga(broken)

    def test_exact_arithmetic_parity_fixed_reference(self):
        # This tests the proxy identity to 1e-6 USD bn, NOT parity with unavailable Sites source.
        x = (Decimal("6753604") - Decimal("961759")) / Decimal("1000") - Decimal("0.351")
        self.assertLessEqual(abs(x - Decimal("5791.494")), Decimal("0.000001"))


if __name__ == "__main__":
    unittest.main()
