# Memorandum

**To:** Portfolio Manager
**Re:** 4sight sample dataset — data quality review and signal efficacy assessment
**Attachment:** `4sight_QC_and_Analysis.xlsx` (QC log, cleaned data, live analysis)

---

## 1. Data quality — 39 exceptions across 7 checks

| # | Check | Items | What was wrong | Correction applied |
|---|---|---|---|---|
| QC1 | Trading calendar | 5 | Rows dated 04-Jul-2017 (market holiday), 19/20-May-2018 and 23/24-Jun-2018 (weekends). Each duplicates an adjacent session's OHLC, with the Signal copied from a *different* session. | Rows deleted |
| QC2 | Price range | 1 | 19-Mar-2018 Close of 196.28 sits far outside that day's High/Low (154.45–157.21) — a 1→9 keying error. | Rebuilt from Adj Close ÷ adjustment factor → 156.28 |
| QC3 | Adj Close | 3 | 05-Dec-2016 (166.18) and 27-Mar-2017 (158.58) exceed the Close, with +40 and +30 offsets; 10-Oct-2018 is **negative** (−152.28). | Rebuilt as Close × adjacent-day adjustment factor; sign flipped |
| QC4 | OHLC integrity | 8 | High below the day's Open/Close, or Low above it — logically impossible (e.g. 07-Mar-2018 Low 157.22 vs Open 154.46). | High = max(O,H,L,C); Low = min(O,H,L,C) |
| QC5 | Stale values | 11 | Close and Adj Close frozen at 139.110001 / 133.321198 for 11 consecutive sessions (08–22 Sep 2017) while Open/High/Low kept moving. On 10 of those days the frozen Close sits *below* the day's Low. | Set to NaN and re-sourced; linear interpolation used for analysis only |
| QC6 | Signal coding | 6 | The last six Signals are exactly 0.000000. The other 1,027 observations never fall below 10.58 — this is a missing value written as zero. | Set to NaN, excluded |
| QC7 | Completeness | 5 | 09-Nov-2018 is followed directly by 19-Nov-2018 — a full trading week absent. | Placeholder rows; request re-delivery |

Two further points that are not errors but bear on credibility: the price path (116.06 on
19-Nov-2015, a 173.39 peak in Sep-2018, 165.35 on 06-Jan-2020) matches **IWM, a Russell 2000
small-cap ETF**, not the "broad market ETF" described — worth reconciling against an independent
price source. And the sample stops on 06-Jan-2020, six weeks before the fastest bear market on
record.

## 2. Signal efficacy

**The Signal is mostly just the price.** Regressing Signal on same-day Adj Close gives R² = 0.88,
slope 0.1368 — i.e. Signal ≈ price ÷ 7.3. Roughly seven-eighths of the series carries no information
the price screen does not already show.

**The remaining eighth points the wrong way through time.** Taking the residual (Signal net of that
day's price) and correlating it with the ETF's return *k* days away:

| k (days) | −6 | −4 | −2 | 0 | **+1** | **+2** | **+3** | **+4** | **+5** | **+6** | +7 | +8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| correlation | −0.05 | −0.06 | −0.02 | −0.02 | **+0.16** | **+0.18** | **+0.20** | **+0.12** | **+0.14** | **+0.13** | +0.00 | +0.02 |

The residual is uncorrelated with everything knowable at the forecast date, correlates strongly with
the next six sessions, then falls back to zero. Consistently, Signal fits Adj Close **six days later**
(R² = 0.896) better than it fits the same-day price (0.879). Correlation with the cumulative t+1 to
t+6 return is **+0.37**; with the preceding six days, −0.07; with t+7 to t+12, +0.02.

**The headline numbers are therefore worthless.** A 60-day z-score of the Signal has an information
coefficient of **+0.23** against 5-day forward returns, and a long/flat rule on it returns 17.2%
annualised at a 1.52 Sharpe with a 12% maximum drawdown, versus 10.5% and 0.70 for buy-and-hold. The
same rule applied to the price itself returns 8.7% at 0.81 Sharpe, and price momentum has a
*negative* IC (−0.11) over this window — so the outperformance is not momentum the Signal happens to
capture. An IC of 0.23 on a liquid ETF is roughly an order of magnitude beyond what credible equity
forecasting achieves; the diagnostics above say plainly where it comes from.

## 3. Recommendation

**The product is not believable as delivered, and the data quality problems and the statistical
problem point the same way.** A file with rows invented on market holidays, a negative price, an
eleven-day frozen Close, and missing values coded as zero has not been through any production process
worth the name — and if the vendor's own QC did not catch a negative Adj Close, it will not have
caught a subtler timestamp error either. The efficacy results are consistent with exactly that: the
Signal behaves like a smoothed price series computed over a window centred three to seven sessions
*ahead* of its own date, then scaled down by about eight and dusted with noise. That is the classic
signature of look-ahead bias — a research pipeline that joined signal to price on the wrong key, or
backfilled a vendor field, rather than deliberate fraud. It is also precisely the error that makes a
backtest look extraordinary and live trading look like nothing at all.

**Next steps, in order.** (1) Send the QC log back and ask the vendor to explain each item and
re-deliver — their response to a negative price will tell us as much as the data. (2) Ask directly
for the point-in-time construction: what is the timestamp on each Signal, what is the exact
publication lag, and was the historical series generated by a model trained on data outside its own
window? Request the full unadjusted price source so we can reconcile it independently. (3) Make the
real test a **paper-traded, forward, out-of-sample run** — signals time-stamped on arrival to our
systems, no vendor-supplied history, minimum six months and ideally through a drawdown, benchmarked
against the ETF and a simple momentum rule. Ninety percent of this sample is a rising market and it
stops just before February 2020, so nothing here tells us how the system behaves when it matters.
Until a forward run clears, I would not allocate capital or pay for a licence; the cost of the
paper-trading period is trivial next to the cost of funding a signal whose apparent edge is a
date-alignment bug. I would also stop short of accusing the vendor — send them the residual lead-lag
table and ask them to reproduce it. If the system is real, they can explain the pattern; if it is
not, this is the fastest way to find out.

*All figures reproduce from the attached workbook, which recalculates from the cleaned data.*
