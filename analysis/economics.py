"""Recalculate scenario economics from explicit, hypothetical assumptions."""

import json
from decimal import Decimal
from pathlib import Path


ASSUMPTIONS = Path(__file__).with_name("assumptions.json")


def calculate(data):
    d = lambda value: Decimal(str(value))
    capex = sum(d(item["days"]) * d(item["rate_per_day"]) for item in data["implementation"])
    results = {}
    for name, scenario in data["scenarios"].items():
        recovered_leads = d(data["monthly_leads"]) * (d(data["baseline_lost_share"]) - d(scenario["lost_share_after"]))
        extra_wins = recovered_leads * d(scenario["win_rate_recovered"])
        gross_monthly = extra_wins * d(scenario["contribution_per_win"])
        net_monthly = gross_monthly - d(data["recurring_monthly"])
        results[name] = {
            "recovered_leads_monthly": recovered_leads,
            "extra_wins_monthly": extra_wins,
            "gross_monthly": gross_monthly,
            "net_monthly": net_monthly,
            "payback_months": capex / net_monthly if net_monthly > 0 else None,
            "first_year_net_after_capex": net_monthly * 12 - capex,
        }
    return capex, results


def main():
    data = json.loads(ASSUMPTIONS.read_text(encoding="utf-8"))
    capex, results = calculate(data)
    print(f"Внедрение: {capex:,.0f} RUB; поддержка: {data['recurring_monthly']:,.0f} RUB/мес")
    for name, r in results.items():
        payback = f"{r['payback_months']:.1f} мес" if r["payback_months"] is not None else "нет"
        print(f"{name}: возвращено {r['recovered_leads_monthly']:.0f} лидов/мес; "
              f"доп. вклад {r['gross_monthly']:,.0f} RUB/мес; "
              f"чистый эффект {r['net_monthly']:,.0f} RUB/мес; окупаемость {payback}; "
              f"1-й год {r['first_year_net_after_capex']:,.0f} RUB")


if __name__ == "__main__":
    main()
