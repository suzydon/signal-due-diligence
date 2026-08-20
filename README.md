# signal-due-diligence

Detecting Look-Ahead Bias in a Vendor Trading Signal

A data-quality review and efficacy assessment of a commercial forecasting signal marketed to an investment manager. The vendor supplied ~4 years of daily signal values alongside price history for a broad-market ETF, and asked to be evaluated on it.

Headline result: the signal produces a 1.52 Sharpe ratio in backtest against 0.70 for holding the ETF. It is worthless. The signal was constructed using prices 3–7 trading days ahead of the date it carries — classic look-ahead bias. This repository shows how that was established.

Contents
File	What it is
Sample_Dataset.xlsx	The vendor's file, as received
4sight_review.py	Fully commented pipeline — reproduces every figure below
4sight_QC_and_Analysis.xlsx	Deliverable workbook: QC log, cleaned data, live analysis
Memo_to_PM.md	The one-page recommendation written for the decision-maker
qc_log.csv, clean_data.csv	Script outputs
bash
pip install pandas numpy statsmodels openpyxl
python 4sight_review.py Sample_Dataset.xlsx
Part 1 — Data quality

I treated the file as untrusted and wrote down the constraints that must hold in any honest OHLC series, then let the code find the violations. Three layers of check:

Does this row belong here? → calendar, duplicates, completeness Is this cell plausible on its own? → sign, sentinel values, outliers Are the cells consistent with each other? → across a row, and down a column

Seven checks, 39 exceptions across 34 rows. All seven checks found problems.

Check	Layer	Found	Detail
Trading calendar	row	5	Rows dated on two weekends and 04-Jul-2017 (US market holiday). Each duplicates an adjacent session's OHLC, with the Signal copied from a different session — fabricated, not merely misdated.
Close inside High–Low	cell	1	19-Mar-2018 Close of 196.28 against a session range of 154.45–157.21. A +25% one-day jump, fully reversed the next day. Leading digit 1→9.
Prices positive	cell	1	10-Oct-2018 Adj Close is −152.28.
Adjustment factor sane	consistency	2	Adj Close ÷ Close is the cumulative dividend factor: it steps only on ex-dividend dates and never reverses. Two rows show 1.248 and 1.177 against ~0.95 on either side (+40 and +30 keying errors).
OHLC integrity	consistency	8	High below the session Open/Close, or Low above it. Logically impossible.
No stale values	consistency	11	08–22 Sep 2017: Close and Adj Close frozen at 139.110001 / 133.321198 for 11 consecutive sessions while Open/High/Low keep moving. On 10 of those days the frozen Close sits below the day's own Low.
Sentinels and gaps	cell / row	11	The final 6 Signals are exactly 0.000000; the other 1,027 observations never fall below 10.58, so 0 encodes "missing". Separately, the entire week of 12–16 Nov 2018 is absent.
Notes on the repairs

Corrections were derived, not guessed. The Close/Adj Close adjustment factor is stable between ex-dividend dates, so a corrupted Close or Adj Close can be rebuilt from its neighbour's factor — this is how 196.28 → 156.28 was established independently of the High/Low range.

Where a value could not be recovered it was set to NaN rather than imputed. The eleven frozen Closes are the clearest case: Open/High/Low for those sessions are intact and internally consistent, so the true Close is knowable — but only from an independent price source, not from this file. Interpolation was used downstream for analysis and flagged as such; it never entered the delivered "clean" series.

Ordering matters. The frozen Close makes ten perfectly healthy Low values look like violations (Low > Close). Running the OHLC check before isolating the stale block would have "corrected" ten good numbers. All violation flags are therefore computed on the raw data before any repair is applied.

Part 2 — Signal efficacy
The signal is mostly the price

Regressing Signal on same-day Adj Close: R² = 0.879, slope 0.1368. The signal is the ETF price divided by roughly 7.3, plus noise. Seven-eighths of it is information already visible on a price screen.

The remainder comes from the future

Stripping the price component leaves a residual — the part a vendor would call proprietary. A forecast dated day t can only be built from information available at t, so the residual may correlate with past returns. It must not correlate with future ones.

k (days)	−6	−5	−4	−3	−2	−1	0	+1	+2	+3	+4	+5	+6	+7	+8
corr(residual, return at t+k)	−0.05	−0.02	−0.06	−0.01	−0.02	−0.02	−0.02	+0.16	+0.18	+0.20	+0.12	+0.14	+0.13	+0.00	+0.02

Zero against everything knowable. Strong across exactly six forward sessions. Then zero again — a hard cut-off, not the smooth decay a real (if weak) forecast would show.

Corroborating tests:

Signal fits Adj Close six days later (R² = 0.896) better than same-day Adj Close (R² = 0.879).
Regressed jointly on both, the t+6 price carries a coefficient of 0.112 (t = 13.4) against 0.026 (t = 3.1) for the same-day price.
Correlation with the cumulative t+1…t+6 return: +0.37. With t−6…t−1: −0.07. With t+7…t+12: +0.02.
Why the backtest is meaningless
Strategy	Annual return	Sharpe	Max drawdown
Signal z-score > 0, long/flat	+17.2%	1.52	−12.2%
Same rule on the price itself	+8.7%	0.81	−11.3%
Buy and hold	+10.5%	0.70	−27.2%

The benchmark row matters more than the headline. Price momentum has a negative information coefficient over this window (−0.11 against 5-day forward returns), so the signal's apparent edge is not a trend-following effect it happens to capture. The information coefficient of the signal z-score is +0.23 against 5-day forward returns; published equity signals live around 0.03–0.05. An IC that high on a liquid ETF is not a discovery, it is a symptom.

Two things the file does not say

The price path — 116.06 on 19-Nov-2015, a 173.39 peak in Sep-2018, 165.35 on 06-Jan-2020 — is consistent with IWM, a Russell 2000 small-cap ETF, not the "broad market ETF" described in the vendor's cover note. Worth reconciling against an independent source before anything else.

The sample also ends on 06-Jan-2020, six weeks before the fastest bear market on record. Close to 90% of it is a rising market, and the one period that would stress-test a forecasting system falls just outside the window.

Conclusion delivered

No capital, no licence. Return the quality-check log and ask the vendor to account for each item — their answer on the negative price is diagnostic in itself. Ask directly for the point-in-time construction: the timestamp on each signal, the publication lag, and whether the historical series was generated by a model trained on data outside its own window.

Then make the real test a forward, out-of-sample paper-trading run — signals time-stamped on arrival, no vendor-supplied history, six months minimum and ideally through a drawdown.

The pattern is most consistent with a research pipeline that joined signal to price on the wrong key, or backfilled a vendor field — not deliberate fraud. It is also precisely the error that makes a backtest extraordinary and live trading flat. The fastest way to resolve it is to send the vendor the residual lead-lag table and ask them to reproduce it. If the system is real, they can explain the shape.

Method notes
Trading calendar is NYSE: weekends, nine market holidays, Good Friday, and 05-Dec-2018 (national day of mourning). The standard USFederalHolidayCalendar is wrong here — it includes Columbus Day and Veterans Day, when the exchange is open.
Adj Close is the analysis price throughout; it is the series that reflects total return.
Backtest is long/flat, next-day execution, zero costs — deliberately generous to the vendor.
Every figure in the workbook except the backtest table is a live worksheet formula, so the analysis recalculates if the underlying data is corrected.
