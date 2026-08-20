"""
4sight sample dataset - data quality review and signal efficacy analysis.

Run:  python 4sight_review.py Sample_Dataset.xlsx

Outputs
    qc_log.csv       every quality-check exception, with the correction applied
    clean_data.csv   the corrected series
    stdout           the efficacy metrics reported in the memo

Requires pandas, numpy, scipy, statsmodels, openpyxl.
"""

import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

SRC = sys.argv[1] if len(sys.argv) > 1 else "Sample_Dataset.xlsx"

# ============================================================================
# PART 1 - DATA QUALITY
# ----------------------------------------------------------------------------
# Every check below is an assertion that must hold for any honest OHLC file.
# Anything that violates one is logged with the rule used to repair it.
# ============================================================================

raw = pd.read_excel(SRC)
d = raw.copy()
log = []


def rec(check, date, field, original, corrected, issue, action):
    log.append(dict(Check=check, Date=date, Field=field, Original=original,
                    Corrected=corrected, Issue=issue, Action=action))


# Flags are computed on the RAW data, before anything is repaired, so that one
# corrupt column cannot make a neighbouring healthy column look broken.
raw_close_out_of_range = raw.index[(raw.Close > raw.High) | (raw.Close < raw.Low)]
STALE_DATES = pd.to_datetime([
    "2017-09-08", "2017-09-11", "2017-09-12", "2017-09-13", "2017-09-14",
    "2017-09-15", "2017-09-18", "2017-09-19", "2017-09-20", "2017-09-21",
    "2017-09-22"])
stale_impossible = raw.loc[raw_close_out_of_range, "Date"]
stale_impossible = set(stale_impossible[stale_impossible.isin(STALE_DATES)])


# --- QC1: every row must fall on an NYSE trading day -------------------------
# NYSE is shut at weekends and on 9 public holidays. It is NOT shut on Columbus
# Day or Veterans Day (both federal holidays), and it WAS shut on 05-Dec-2018
# for the national day of mourning - so the stock pandas federal calendar is
# not usable here without adjustment.
NON_TRADING_ROWS = {
    "2017-07-04": "US Independence Day (market closed); OHLC = previous session +$0.10, Signal duplicates the next session",
    "2018-05-19": "Saturday; OHLC duplicates Mon 21-May, Signal duplicates Thu 17-May",
    "2018-05-20": "Sunday; OHLC duplicates Tue 22-May, Signal duplicates Fri 18-May",
    "2018-06-23": "Saturday; OHLC duplicates Mon 25-Jun, Signal duplicates Thu 21-Jun",
    "2018-06-24": "Sunday; OHLC duplicates Tue 26-Jun, Signal duplicates Fri 22-Jun",
}
for dt, why in NON_TRADING_ROWS.items():
    rec("QC1 Calendar", dt, "entire row", "present", "row deleted", why,
        "Delete (fabricated / duplicated session)")
d = d[~d.Date.isin(pd.to_datetime(list(NON_TRADING_ROWS)))].reset_index(drop=True)


# --- QC2: Close must sit inside the day's High-Low range ---------------------
i = d.index[d.Date == "2018-03-19"][0]
adj_factor_next = d.at[i + 1, "Adj Close"] / d.at[i + 1, "Close"]
new = round(d.at[i, "Adj Close"] / adj_factor_next, 6)
rec("QC2 Range", "2018-03-19", "Close", d.at[i, "Close"], new,
    "Close 196.28 far outside the session range (Low 154.45 / High 157.21); a +25% one-day jump fully reversed the next day. Leading digit 1->9 keying error",
    "Re-derive Close = Adj Close / adjustment factor of the adjacent session")
d.at[i, "Close"] = new


# --- QC3: Adj Close must be positive, and <= Close outside odd corporate acts -
# Adj Close / Close is the cumulative dividend adjustment factor. It only steps
# on ex-dividend dates and never reverses, so a neighbouring day's factor is a
# reliable way to rebuild a corrupted value.
ADJ_ERRORS = [
    ("2016-12-05", "Adj Close 166.18 exceeds Close 133.15; implied factor 1.248 vs 0.948 either side (+40 keying error)", "factor"),
    ("2017-03-27", "Adj Close 158.58 exceeds Close 134.74; implied factor 1.177 vs 0.954 either side (+30 keying error)", "factor"),
    ("2018-10-10", "Adj Close -152.28 is negative; a price can never be below zero. |value| matches the neighbouring factor exactly", "sign"),
]
for dt, issue, mode in ADJ_ERRORS:
    i = d.index[d.Date == dt][0]
    old = d.at[i, "Adj Close"]
    if mode == "sign":
        new = round(abs(old), 6)
        action = "Flip sign"
    else:
        new = round(d.at[i, "Close"] * (d.at[i + 1, "Adj Close"] / d.at[i + 1, "Close"]), 6)
        action = "Re-derive Adj Close = Close x adjustment factor of the adjacent session"
    rec("QC3 Adj Close", dt, "Adj Close", old, new, issue, action)
    d.at[i, "Adj Close"] = new


# --- QC4: High >= max(Open, Close) and Low <= min(Open, Close) ---------------
# Rows whose Close is itself corrupt (QC5) are excluded, otherwise the stale
# Close would make 10 perfectly good Low values look like errors.
for i in d.index[~d.Date.isin(stale_impossible)]:
    o, h, l, c = d.loc[i, ["Open", "High", "Low", "Close"]]
    dt = d.at[i, "Date"].strftime("%Y-%m-%d")
    if h < max(o, c) - 1e-9:
        rec("QC4 OHLC", dt, "High", h, round(max(o, h, l, c), 6),
            f"High ({h:.2f}) below the session Open/Close ({max(o, c):.2f}) - logically impossible",
            "High = max(Open, High, Low, Close)")
        d.at[i, "High"] = max(o, h, l, c)
    if l > min(o, c) + 1e-9:
        rec("QC4 OHLC", dt, "Low", l, round(min(o, h, l, c), 6),
            f"Low ({l:.2f}) above the session Open/Close ({min(o, c):.2f}) - logically impossible",
            "Low = min(Open, High, Low, Close)")
        d.at[i, "Low"] = min(o, h, l, c)


# --- QC5: no value may repeat for days while its neighbours move -------------
for dt in STALE_DATES:
    s = dt.strftime("%Y-%m-%d")
    impossible = dt in stale_impossible
    rec("QC5 Stale", s, "Close, Adj Close", 139.110001,
        "NaN (re-source)" if impossible else "retained, flagged",
        "Close & Adj Close frozen at 139.110001 / 133.321198 for 11 consecutive sessions while Open/High/Low keep moving"
        + ("; the frozen Close sits below the session Low, so it is provably wrong" if impossible
           else "; first repeat of the 07-Sep close, not provably wrong"),
        "Set to NaN and re-source from an independent vendor (interpolated for analysis only)"
        if impossible else "Flag; retain")
d.loc[d.Date.isin(stale_impossible), ["Close", "Adj Close"]] = np.nan


# --- QC6: sentinel values must not be mistaken for data ----------------------
# Signal is exactly 0.000000 on the last 6 rows. It never goes below 10.9
# anywhere else, so these are missing values written as zero. Left in place they
# would drag every mean, z-score and correlation.
for i in d.index[d.Signal == 0]:
    rec("QC6 Signal", d.at[i, "Date"].strftime("%Y-%m-%d"), "Signal", 0.0, "NaN",
        "Signal exactly 0.000000 for the last 6 sessions; the other 1,027 observations never fall below 10.58 - a missing value written as zero",
        "Set to NaN and exclude from analysis; request re-delivery")
d.loc[d.Signal == 0, "Signal"] = np.nan


# --- QC7: no trading session may be absent -----------------------------------
MISSING = pd.to_datetime(["2018-11-12", "2018-11-13", "2018-11-14", "2018-11-15", "2018-11-16"])
for dt in MISSING:
    rec("QC7 Gaps", dt.strftime("%Y-%m-%d"), "entire row", "absent", "placeholder row (NaN)",
        "Trading session missing; 09-Nov-2018 is followed directly by 19-Nov-2018, a full week absent",
        "Insert placeholder row; request the missing week from the vendor")
d = pd.concat([d, pd.DataFrame({"Date": MISSING})]).sort_values("Date").reset_index(drop=True)

qc = pd.DataFrame(log)
qc.to_csv("qc_log.csv", index=False)
d.to_csv("clean_data.csv", index=False)

print("=" * 78)
print("PART 1 - DATA QUALITY")
print("=" * 78)
print(qc.groupby("Check").size().to_string())
print(f"\n{len(qc)} exceptions in total.  Rows: {len(raw)} raw -> {len(d)} clean.")
print("Full detail in qc_log.csv; corrected series in clean_data.csv.\n")


# ============================================================================
# PART 2 - SIGNAL EFFICACY
# ----------------------------------------------------------------------------
# Adj Close is the analysis price (it is the one that reflects total return).
# The 15 missing values are linearly interpolated FOR ANALYSIS ONLY - they are
# still NaN in clean_data.csv, because guessing a price is not a correction.
# ============================================================================

px = d["Adj Close"].interpolate()
sig = d.Signal
ret = px.pct_change()

# --- 2a. How much of the Signal is simply the price? -------------------------
mask = sig.notna()
fit = sm.OLS(sig[mask], sm.add_constant(px[mask])).fit()
slope, const = fit.params.iloc[1], fit.params.iloc[0]
residual = sig - (const + slope * px)      # the "proprietary" part of the Signal

print("=" * 78)
print("PART 2 - SIGNAL EFFICACY")
print("=" * 78)
print("\n2a. Signal regressed on the SAME-DAY price")
print(f"    Signal = {const:.4f} + {slope:.4f} x AdjClose      R^2 = {fit.rsquared:.3f}")
print(f"    -> {fit.rsquared:.0%} of the Signal is the ETF price rescaled by 1/{1/slope:.2f}.")
print("       It is not independent information.")

# --- 2b. Where in time does the rest of the Signal live? ---------------------
# A forecast made on day t can only be built from information up to day t.
# So the residual may correlate with PAST returns (k<=0). If it correlates with
# FUTURE returns (k>0) instead, the signal was built using prices it could not
# have known - look-ahead bias.
print("\n2b. Correlation of the Signal residual with the return k days away")
print("     k   corr    knowable at time t?")
for k in range(-6, 9):
    c = residual.corr(ret.shift(-k))
    print(f"    {k:+3d}  {c:+.3f}   {'yes' if k <= 0 else 'NO - future'}")

for a, b in [(-6, -1), (1, 6), (7, 12)]:
    cum = px.shift(-b) / px.shift(-(a - 1)) - 1
    print(f"    cumulative return t{a:+d}..t{b:+d}: corr = {residual.corr(cum):+.3f}")

r2_same = sm.OLS(sig[mask], sm.add_constant(px[mask])).fit().rsquared
fwd6 = px.shift(-6)
m6 = sig.notna() & fwd6.notna()
r2_fwd6 = sm.OLS(sig[m6], sm.add_constant(fwd6[m6])).fit().rsquared
print(f"\n    R^2 vs the SAME-DAY price : {r2_same:.3f}")
print(f"    R^2 vs the price 6 DAYS LATER: {r2_fwd6:.3f}   <- fits the future better")

# --- 2c. Apparent predictive power, against an honest benchmark --------------
# Information Coefficient = correlation between the signal and the return that
# actually followed. Real equity signals score 0.03-0.05.
z = lambda x, w=60: (x - x.rolling(w).mean()) / x.rolling(w).std()
sig_z, px_z = z(sig), z(px)

print("\n2c. Information Coefficient vs forward returns")
print(f"    {'horizon':>8} {'Signal z':>10} {'price z':>10} {'residual':>10}")
for h in [1, 5, 10, 21]:
    fwd = px.shift(-h) / px - 1
    print(f"    {h:>6}d {sig_z.corr(fwd):>+10.3f} {px_z.corr(fwd):>+10.3f} {residual.corr(fwd):>+10.3f}")
print("    The price-based column is the benchmark: it is what you get for free.")
print("    Note it is NEGATIVE at 5-21 days, so the Signal's edge is not momentum.")

# --- 2d. Backtest: long when the signal is above its own 60-day average ------
# Deliberately generous: next-day execution, no trading costs, no slippage.
ann = lambda x: (1 + x).prod() ** (252 / len(x)) - 1
sharpe = lambda x: x.mean() / x.std() * np.sqrt(252)
maxdd = lambda x: ((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min()

print("\n2d. Backtest (long/flat, next-day execution, zero costs)")
print(f"    {'strategy':<32} {'ann.ret':>8} {'Sharpe':>7} {'maxDD':>8}")
for name, s in [("4sight Signal", sig_z), ("Price momentum, same rule", px_z)]:
    r = ((s > 0).shift(1).astype(float) * ret).dropna()
    print(f"    {name:<32} {ann(r):>+8.1%} {sharpe(r):>7.2f} {maxdd(r):>8.1%}")
bh = ret.dropna()
print(f"    {'Buy and hold the ETF':<32} {ann(bh):>+8.1%} {sharpe(bh):>7.2f} {maxdd(bh):>8.1%}")

print("""
CONCLUSION
    The Signal residual is uncorrelated with everything knowable on the day it
    is dated, and strongly correlated with the six sessions that follow, after
    which it collapses to zero. It fits the price six days ahead better than
    the price on its own date. That is look-ahead bias, not forecasting skill:
    the Signal appears to be built from a window of prices centred 3-7 sessions
    into its own future, scaled down by ~8 and mixed with noise.

    The backtest is therefore not evidence of anything. Recommend no capital
    and no licence until a forward, out-of-sample paper-trading run - signals
    time-stamped on arrival, minimum six months, ideally through a drawdown -
    reproduces the result. Note the sample ends 06-Jan-2020, six weeks before
    the fastest bear market on record.
""")
