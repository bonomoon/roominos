# Verification Checklist: Task 010 - Complex Batch Settlement Migration

## 1. Schema Mapping (14 tables)

- [ ] **1.1** `TB_ACCT_MST` mapped with all 17 columns including `NEW_ACCT_TYPE`, `FEE_EXEMPT_YN`, `HOLD_AMT`
- [ ] **1.2** `TB_CUST_MST` mapped with `CUST_GRADE` (1-5 numeric) and `CUST_TYPE`
- [ ] **1.3** `TB_PRODUCT_MST` mapped with `BASE_RATE`, `SPC_RATE`, `PRODUCT_CD`
- [ ] **1.4** `TB_BRANCH_MST` mapped with hierarchical fields (`PARENT_BR_CD`, `BR_LEVEL`)
- [ ] **1.5** `TB_TXN_HIST` mapped with composite PK (`ACCT_NO`, `TXN_DT`, `TXN_SEQ`)
- [ ] **1.6** `TB_FEE_MST` mapped with `FEE_RATE`, `FREE_TXN_CNT`, `MAINT_FEE`, date range
- [ ] **1.7** `TB_PROMO_RATE` mapped with `PROMO_RATE`, date range, `USE_YN`
- [ ] **1.8** `TB_ACCT_LIMIT` mapped with `LIMIT_AMT`
- [ ] **1.9** `TB_COVID_EXEMPT` mapped with `EXEMPT_RATE`, date range, `USE_YN`
- [ ] **1.10** `TB_SETTLE_HIST` mapped with `BF_BAL`, `AF_BAL`, composite PK
- [ ] **1.11** `TB_SETTLE_DAILY` mapped with `INT_AMT`, `FEE_AMT`, `TAX_AMT`, `SETTLE_AMT`, `BAL_AMT`
- [ ] **1.12** `TB_BATCH_CTL` mapped with status codes (`R`/`P`/`C`/`E`), counters
- [ ] **1.13** `TB_BATCH_ERR_LOG` mapped (no PK — append-only error log)
- [ ] **1.14** `TB_LIMIT_OVER_LOG` mapped with `OVER_AMT`, composite PK

## 2. Data Type Fidelity

- [ ] **2.1** All `NUMBER(18,2)` monetary columns use `BigDecimal` (not `double`)
- [ ] **2.2** All `VARCHAR2(8)` date strings mapped to proper date types or preserved as strings with validation
- [ ] **2.3** `NUMBER(1)` status codes (`ACCT_STAT`) mapped to int or enum
- [ ] **2.4** `NUMBER(7,4)` rate columns use `BigDecimal` with 4-decimal precision
- [ ] **2.5** NULL indicator variables mapped to `Optional` or nullable types with explicit null handling

## 3. SQL Equivalence — SETTLE_BAT Main Cursor

- [ ] **3.1** 4-table outer join cursor (`TB_ACCT_MST`, `TB_PRODUCT_MST`, `TB_CUST_MST`, `TB_ACCT_LIMIT`) with Oracle `(+)` syntax mapped to ANSI LEFT JOIN
- [ ] **3.2** Duplicate cursor logic (c_acct for ALL branches, c_acct_br for specific branch) consolidated or preserved
- [ ] **3.3** `NVL()` default values preserved for all 18 SELECT columns
- [ ] **3.4** Filter conditions: `ACCT_STAT IN (1,2,3)`, `CLOSE_DT IS NULL`, `OPEN_DT <= batch_dt`
- [ ] **3.5** `ORDER BY BR_CD, ACCT_NO` preserved for deterministic processing order

## 4. SQL Equivalence — SETTLE_BAT Inline Queries

- [ ] **4.1** `TB_BATCH_CTL` status check (`BATCH_STAT IN ('R','E')`) mapped
- [ ] **4.2** `TB_BATCH_CTL` status update to `P` (processing) mapped
- [ ] **4.3** `TB_COVID_EXEMPT` lookup with date range and `ROWNUM = 1` mapped
- [ ] **4.4** `TB_TXN_HIST` COUNT/SUM aggregate with `CASE WHEN TXN_TYPE IN ('01','02')` mapped
- [ ] **4.5** `TB_LIMIT_OVER_LOG` INSERT with DUP_KEY (`sqlcode == -1`) ignore mapped
- [ ] **4.6** `TB_SETTLE_DAILY` UPSERT (INSERT, on DUP_KEY UPDATE) mapped
- [ ] **4.7** `TB_BATCH_ERR_LOG` INSERT (failure silently ignored) mapped
- [ ] **4.8** `TB_ACCT_MST` balance UPDATE (`BAL_AMT`, `LAST_TXN_DT`, `UPD_DT`) mapped
- [ ] **4.9** `TB_BATCH_CTL` final status update to `C` or `E` with counters mapped

## 5. SQL Equivalence — calc_interest Function

- [ ] **5.1** `TB_PROMO_RATE` lookup with date range, `USE_YN='Y'`, `ROWNUM=1` mapped
- [ ] **5.2** `TB_SETTLE_DAILY` monthly accumulated interest SUM with `SUBSTR(batch_dt,1,6)||'01'` date range mapped
- [ ] **5.3** Tiered interest rate logic (6 balance tiers for types 1,2) preserved
- [ ] **5.4** Period-based rate logic (4 tiers: <90d, <180d, <365d, 365d+ for type 3) preserved
- [ ] **5.5** Corporate checking (type 5) negative balance +3% loan rate preserved
- [ ] **5.6** Promotion rate additive logic preserved

## 6. SQL Equivalence — calc_fee Function

- [ ] **6.1** `TB_FEE_MST` + `TB_ACCT_MST` join with date range and `USE_YN='Y'` mapped
- [ ] **6.2** Default fallback values (0.01% rate, 10 free txns, 1000 won maint) when no fee record found
- [ ] **6.3** Grade-based free transaction count (VIP=unlimited, Gold+20, Silver+10, Bronze+5) preserved
- [ ] **6.4** Per-type transaction fee rates (500/300/0/400/200/100 won) preserved
- [ ] **6.5** Monthly maintenance fee (1st of month only, exempt if balance >= 1M) preserved
- [ ] **6.6** Fee cap at 50,000 won/month preserved

## 7. SQL Equivalence — proc_settlement Function

- [ ] **7.1** `MAX(SETTLE_SEQ) + 1` sequence generation from `TB_SETTLE_HIST` mapped (or replaced with proper sequence)
- [ ] **7.2** `SELECT FOR UPDATE NOWAIT` with ORA-00054 retry loop (max 3 retries, 1s sleep) mapped
- [ ] **7.3** `TB_SETTLE_HIST` INSERT with `BF_BAL`, `AF_BAL` calculation mapped
- [ ] **7.4** Commented-out balance UPDATE in proc_settlement NOT reintroduced (was a double-posting bug)

## 8. SQL Equivalence — RPT_DAILY

- [ ] **8.1** `TB_BATCH_CTL` result check for report generation mapped
- [ ] **8.2** Branch report: `CONNECT BY PRIOR BR_CD = PARENT_BR_CD` with `START WITH PARENT_BR_CD IS NULL` mapped to recursive CTE or equivalent
- [ ] **8.3** Branch report: `ORDER SIBLINGS BY BR_CD` ordering preserved
- [ ] **8.4** Branch report: subquery with `GROUP BY BR_CD` aggregation on `TB_SETTLE_DAILY` mapped
- [ ] **8.5** Grade report: `DECODE(CUST_GRADE, 1, 1, 0)` pivot for 5 grades mapped to `CASE WHEN` or equivalent
- [ ] **8.6** Type report: `GROUP BY ACCT_TYPE` with `AVG`, `MAX`, `MIN` aggregation mapped
- [ ] **8.7** Limit report: join `TB_ACCT_MST` + `TB_ACCT_LIMIT` with `BAL_AMT > LIMIT_AMT`, top-100 cutoff mapped
- [ ] **8.8** All `NVL()` calls in report queries mapped to `COALESCE()` or application-level null handling

## 9. Transaction Management

- [ ] **9.1** `SAVEPOINT sp_acct` per account mapped to nested transaction or programmatic savepoint
- [ ] **9.2** `ROLLBACK TO SAVEPOINT sp_acct` on error/skip with continue-processing preserved
- [ ] **9.3** Periodic COMMIT every N records (configurable, default 100) preserved via chunk processing
- [ ] **9.4** Final COMMIT after main loop preserved
- [ ] **9.5** `SELECT FOR UPDATE NOWAIT` with retry in proc_settlement mapped to pessimistic locking with timeout
- [ ] **9.6** `ROLLBACK WORK` in signal handler mapped to graceful shutdown hook
- [ ] **9.7** `COMMIT WORK RELEASE` (disconnect) mapped to connection pool management

## 10. Error Handling Patterns

- [ ] **10.1** GOTO `ERR_HANDLE`: rollback savepoint, log error, insert error log, continue processing — mapped to try-catch per record
- [ ] **10.2** GOTO `SKIP_ACCT`: rollback savepoint, increment skip counter, continue — mapped to skip logic
- [ ] **10.3** `sqlca.sqlcode == 1403` (NOT FOUND) mapped to empty result handling
- [ ] **10.4** `sqlca.sqlcode == -1` (DUP_KEY) mapped to upsert or `DuplicateKeyException`
- [ ] **10.5** `sqlca.sqlcode == -54` (RESOURCE BUSY) mapped to lock timeout with retry
- [ ] **10.6** Error count threshold (>1000 errors aborts batch) preserved
- [ ] **10.7** Return code pattern (0=success, -1=error, 1=skip) in calc_interest mapped to exceptions or result type
- [ ] **10.8** Silent error ignore (INSERT failure for error log) preserved or made explicit
- [ ] **10.9** `WHENEVER SQLERROR GOTO` for DB connect mapped to connection exception handling
- [ ] **10.10** `WHENEVER SQLERROR CONTINUE` for all other phases mapped to per-statement error handling

## 11. Business Logic Fidelity

- [ ] **11.1** Daily interest: `balance * (rate / 100) / 365`, rounded to won (not truncated) preserved with BigDecimal
- [ ] **11.2** Tiered interest by balance range (6 tiers with +0.1% to +0.5% increments) preserved
- [ ] **11.3** Tiered interest by deposit period (4 tiers with 50%/70%/90%/100% of rate) preserved
- [ ] **11.4** VIP auto-premium +0.5% when no spc_rate present preserved
- [ ] **11.5** Non-face-to-face +0.2% additional rate preserved (NOTE: currently double-applied — decide whether to fix or preserve bug)
- [ ] **11.6** COVID interest discount -0.1% for types 1,2 during 2020-2023 preserved
- [ ] **11.7** Promotion rate additive from DB preserved
- [ ] **11.8** Duplicate inline/function interest calculation with reconciliation — either consolidated or preserved with same behavior
- [ ] **11.9** Tax 15.4% (income 14% + local 1.4%) on positive interest preserved
- [ ] **11.10** VIP fixed deposit tax exemption preserved
- [ ] **11.11** Tax-preferential products (product_cd starts with 'T') at 9.5% preserved
- [ ] **11.12** Per-type transaction fee rates preserved (500/300/0/400/200/100 won)
- [ ] **11.13** Grade-based free transaction thresholds preserved
- [ ] **11.14** Monthly maintenance fee on 1st only, exempt if balance >= 1M preserved
- [ ] **11.15** Fee cap 50,000 won/month preserved
- [ ] **11.16** COVID fee exemption rate applied preserved
- [ ] **11.17** Negative settlement handling (fee > interest) preserved
- [ ] **11.18** Dormant account skip (>365 days since last txn) preserved
- [ ] **11.19** Suspended account (stat==2): fee-exempt, interest-only preserved
- [ ] **11.20** Foreign currency (type 6): always skip preserved

## 12. Batch Processing Metrics

- [ ] **12.1** `g_total_cnt` total processed count tracked
- [ ] **12.2** `g_succ_cnt` success count tracked
- [ ] **12.3** `g_err_cnt` error count tracked
- [ ] **12.4** `g_skip_cnt` skip count tracked
- [ ] **12.5** `g_total_settle` total settlement amount tracked
- [ ] **12.6** `g_total_interest` total interest amount tracked
- [ ] **12.7** `g_total_fee` total fee amount tracked
- [ ] **12.8** `g_total_tax` total tax amount tracked
- [ ] **12.9** `g_limit_over_cnt` and `g_limit_over_total` tracked
- [ ] **12.10** Start/end time and elapsed seconds tracked

## 13. Report Output

- [ ] **13.1** Branch report with tree indentation (by BR_LEVEL) and column headers preserved
- [ ] **13.2** Grade report with VIP/GOLD/SILVER/BRONZE/NORMAL rows and per-record average preserved
- [ ] **13.3** Type report with type names and MIN/MAX/AVG statistics preserved
- [ ] **13.4** Limit-over report with top-100 cutoff and total over-amount preserved
- [ ] **13.5** Fixed-width text format with 132-column width preserved (or migrated to structured format)
- [ ] **13.6** Korean column headers and report titles preserved
- [ ] **13.7** Page breaks every 60 lines in branch report preserved
- [ ] **13.8** Grand total section at end of report preserved
- [ ] **13.9** Report footer with contact info preserved
- [ ] **13.10** Timestamp in report header preserved

## 14. Infrastructure

- [ ] **14.1** Hardcoded DB credentials (`BATCH_USER`/`batch1234`) eliminated — use secure config
- [ ] **14.2** Environment variable fallback (`ORACLE_UID`, `ORACLE_PWD`, `ORACLE_SID`) mapped to application config
- [ ] **14.3** Signal handling (SIGINT/SIGTERM) mapped to graceful shutdown hooks
- [ ] **14.4** Argument parsing (`YYYYMMDD [BR_CD] [JOB_TYPE] [COMMIT_UNIT] [DEBUG]`) mapped to CLI args or config
- [ ] **14.5** Log file management (`/app/batch/log/`) mapped to logging framework
- [ ] **14.6** Report file output (`/app/batch/report/`) mapped to configurable output path
- [ ] **14.7** Global variable state eliminated via proper scoping / dependency injection

## 15. Test Coverage

- [ ] **15.1** Unit tests for daily interest calculation (all 9 account types)
- [ ] **15.2** Unit tests for tiered interest (6 balance tiers, 4 period tiers)
- [ ] **15.3** Unit tests for fee calculation (normal, exempt, cap, maintenance)
- [ ] **15.4** Unit tests for tax calculation (normal 15.4%, exempt, preferential 9.5%)
- [ ] **15.5** Unit tests for settlement amount (positive, negative, zero-balance)
- [ ] **15.6** Integration test: full batch flow with known input and expected output
- [ ] **15.7** Integration test: periodic commit every N records
- [ ] **15.8** Integration test: savepoint rollback on per-record error
- [ ] **15.9** Integration test: dormant account skip
- [ ] **15.10** Integration test: COVID exemption period
- [ ] **15.11** Integration test: limit-over detection and logging
- [ ] **15.12** Integration test: error threshold abort (>1000 errors)
- [ ] **15.13** Report output comparison test (field-by-field against reference)

---

## Verification Summary

| Category | Items | Weight |
|----------|-------|--------|
| Schema Mapping | 14 | 8% |
| Data Type Fidelity | 5 | 5% |
| SQL - Main Cursor | 5 | 8% |
| SQL - Inline Queries | 9 | 10% |
| SQL - calc_interest | 6 | 8% |
| SQL - calc_fee | 6 | 7% |
| SQL - proc_settlement | 4 | 5% |
| SQL - RPT_DAILY | 8 | 7% |
| Transaction Management | 7 | 10% |
| Error Handling | 10 | 8% |
| Business Logic | 20 | 12% |
| Batch Metrics | 10 | 3% |
| Report Output | 10 | 3% |
| Infrastructure | 7 | 3% |
| Test Coverage | 13 | 3% |
| **Total** | **134** | **100%** |

### Pass Criteria
- **All 134 items checked**: Migration is complete and fully verified
- **Schema + SQL + Transaction + Error Handling + Business Logic (90%+ items)**: Migration is functionally equivalent
- **Below 80%**: Migration has critical gaps requiring additional work
