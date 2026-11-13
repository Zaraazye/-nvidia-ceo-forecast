"""Forecast Polymarket's "Next CEO of NVIDIA?" Yes prices, minute by minute, 4 hours ahead.

Reads each case at /input/<id>.in (or $MAKEFUN_INPUT_DIR) and writes the forecast
to /output/<id>.out (or $MAKEFUN_OUTPUT_DIR):
  {"forecasts": [{"id": <market id>, "q": [[5 quantiles] x horizon_minutes]}]}

Model (persistence median + adaptive spread, no drift, no network, stdlib only):
  - Median: the market's last price at the checkpoint. Prediction-market prices are
    (close to) a martingale, so the current price is the best point forecast; every
    drift/momentum variant we tried on the 6 practice cases scored WORSE than
    persistence, even heavily damped.
  - Spread: per market, sigma is the average of two estimators of the per-minute
    price-move scale over the last 120 minutes of the case:
        meanabs = mean(|diff|) * sqrt(pi/2)   (robust: a single jump counts once)
        std     = sample std of diffs          (jump-sensitive: jumps cluster)
    sigma = clip(0.5*meanabs + 0.5*std, 0.0005, 0.005).
    The cap matters: an uncapped std over-reacts to a single jump and makes the
    forecast far too wide; the floor keeps never-moving markets from collapsing
    to a degenerate (zero-width) forecast.
  - Quantiles at horizon h (minutes after the checkpoint) use the normal quantiles
    z = [-1.644854, -0.67449, 0, 0.67449, 1.644854]:
        q_tau(h) = clamp(last + z_tau * sigma * sqrt(h), 0, 1), rounded to 6 decimals.
    The sqrt(h) widening is the random-walk shape the house baseline also uses;
    the improvement over the house is entirely the per-market adaptive sigma.

Practice results (mean pinball loss, percentage points; lower is better):
  house baseline (fixed sigma 0.0025, no drift): 0.3718
  this program:                                  0.2812   (~24% better)
  per case: p00 0.4573, p01 0.3119, p02 0.3314, p03 0.2523, p04 0.2002, p05 0.1343.
  It beat the baseline on every one of the 6 practice cases.

Deterministic: no randomness, no clock, no network; the same case always gives
the same bytes. Runs in well under 1 second per case (limit 8 s).
"""
import json
import math
import os
import sys

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at the five levels, to 6 decimals.
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]
# Volatility window (minutes of price diffs), floor and cap for sigma (price units).
WINDOW = 120
SIGMA_FLOOR = 0.0005
SIGMA_CAP = 0.005


def price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)) * 1e6) / 1e6 + 0.0


def _std(xs):
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _meanabs_sigma(xs):
    """Per-minute scale from mean absolute move, rescaled to a normal sigma."""
    if not xs:
        return 0.0
    return (sum(abs(x) for x in xs) / len(xs)) * math.sqrt(math.pi / 2.0)


def sigma_of(prices):
    """Adaptive per-minute volatility for one market, from its last WINDOW minutes."""
    n = len(prices)
    if n < 2:
        return SIGMA_FLOOR
    diffs = [prices[i + 1] - prices[i] for i in range(max(0, n - WINDOW - 1), n - 1)]
    if not diffs:
        return SIGMA_FLOOR
    est = 0.5 * _meanabs_sigma(diffs) + 0.5 * _std(diffs)
    return min(SIGMA_CAP, max(SIGMA_FLOOR, est))


def forecast_market(prices, horizon):
    """240 (horizon) rows of the five quantiles for one market."""
    if not prices:
        raise ValueError("market has no prices")
    x = prices[-1]
    sigma = sigma_of(prices)
    rows = []
    for h in range(1, horizon + 1):
        spread = sigma * math.sqrt(h)
        row = [price6(x + z * spread) for z in Z]
        # Enforce non-decreasing (rounding/clamping are monotone, but be explicit).
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    if not inputs:
        raise SystemExit(f"no .in files in {INPUT_DIR}")
    for fname in inputs:
        case_id = fname[: -len(".in")]
        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as f:
            case = json.load(f)
        if list(case.get("quantiles", [])) != QUANTILES:
            raise SystemExit(
                f"{fname} asks for quantiles {case.get('quantiles')}, not {QUANTILES}"
            )
        horizon = int(case["horizon_minutes"])
        forecasts = [
            {"id": m["id"], "q": forecast_market(m["prices"], horizon)}
            for m in case["markets"]
        ]
        out_path = os.path.join(OUTPUT_DIR, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"forecasts": forecasts}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
