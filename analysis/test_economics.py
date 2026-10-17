import json
import unittest
from pathlib import Path

from economics import calculate


class EconomicsTest(unittest.TestCase):
    def test_documented_base_scenario(self):
        data = json.loads(Path(__file__).with_name("assumptions.json").read_text(encoding="utf-8"))
        capex, scenarios = calculate(data)
        self.assertEqual(capex, 630_000)
        self.assertEqual(scenarios["base"]["recovered_leads_monthly"], 24)
        self.assertEqual(scenarios["base"]["net_monthly"], 99_600)
        self.assertEqual(scenarios["base"]["first_year_net_after_capex"], 565_200)
        self.assertLess(scenarios["conservative"]["first_year_net_after_capex"], 0)


if __name__ == "__main__":
    unittest.main()
