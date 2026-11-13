# NVIDIA CEO price forecaster — make.fun bounty

Forecasts the Yes price of every trading market of Polymarket's
"Next CEO of NVIDIA?" event, minute by minute, 4 hours ahead
(240 minutes × 5 quantiles per market).

## Run

```sh
python3 main.py            # reads /input/<id>.in, writes /output/<id>.out
# local test:
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13, standard library only, no network, deterministic.
~0.06 s per case (limit 8 s).

## Model

- **Median:** the market's last price at the checkpoint (persistence).
  Prediction-market prices are close to a martingale; every drift/momentum
  variant tried scored worse than persistence on the practice cases.
- **Spread:** per-market sigma = average of two per-minute volatility
  estimators over the last 120 minutes —
  mean-|diff| rescaled to a normal sigma (robust to jumps) and the sample
  std of diffs (jump-sensitive) — clipped to [0.0005, 0.005].
  Quantiles use normal z-scores, widening as sigma·√h.
- Prices clamped to [0, 1], rounded to 6 decimals, non-decreasing rows.

## Practice score (mean pinball loss, percentage points)

| | p00 | p01 | p02 | p03 | p04 | p05 | mean |
|---|---|---|---|---|---|---|---|
| house baseline | 0.5361 | 0.3804 | 0.4084 | 0.3686 | 0.2988 | 0.2382 | 0.3718 |
| this program | 0.4573 | 0.3119 | 0.3314 | 0.2523 | 0.2002 | 0.1343 | **0.2812** |

24% better than the house baseline, and better on every practice case.
Ground truth for the practice cases was fetched from Polymarket's public
CLOB price history and rebuilt on the house's 1-minute grid.

## License

MIT — see LICENSE.
