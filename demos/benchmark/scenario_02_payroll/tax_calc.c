/*******************************************************************************
 * tax_calc.c - 세금 계산 모듈 (순수 C - DB 접근 없음)
 *
 * 작성일: 2006-05-20
 * 수정일: 2013-01-10  최과장 - 4대보험 요율 개정
 * 수정일: 2017-03-15  김대리 - 비과세 항목 확장
 * 수정일: 2020-07-01  박사원 - 2020년 간이세액표 반영
 * 수정일: 2023-01-02  이대리 - 2023년 요율/구간 반영
 *
 * 소득세, 주민세, 4대보험 계산
 * 이 파일은 순수 C로 작성 (Pro*C 아님, EXEC SQL 없음)
 * pay_main.pc에서 함수 포인터로 호출됨
 ******************************************************************************/

#include "pay_common.h"

/*******************************************************************************
 * 간이세액표 구간 (2023년 기준 - 월급여 기준)
 *
 * 과세표준 구간별 세율:
 * ~14,000,000     : 6%
 * ~50,000,000     : 15%  - 1,260,000 공제
 * ~88,000,000     : 24%  - 5,760,000 공제
 * ~150,000,000    : 35%  - 15,440,000 공제
 * ~300,000,000    : 38%  - 19,940,000 공제
 * ~500,000,000    : 40%  - 25,940,000 공제
 * ~1,000,000,000  : 42%  - 35,940,000 공제
 * 1,000,000,000~  : 45%  - 65,940,000 공제
 *
 * 월 환산은 연간 세액 / 12
 ******************************************************************************/

/* 세율 구간 */
#define TAX_BRACKET_CNT  8

static double g_bracket_limit[TAX_BRACKET_CNT] = {
    14000000.0, 50000000.0, 88000000.0, 150000000.0,
    300000000.0, 500000000.0, 1000000000.0, 999999999999.0
};

static double g_bracket_rate[TAX_BRACKET_CNT] = {
    0.06, 0.15, 0.24, 0.35, 0.38, 0.40, 0.42, 0.45
};

static double g_bracket_deduct[TAX_BRACKET_CNT] = {
    0.0, 1260000.0, 5760000.0, 15440000.0,
    19940000.0, 25940000.0, 35940000.0, 65940000.0
};

/* 부양가족 공제 (간이세액표 기준) */
static double g_family_deduct[12] = {
    0,            /* 0명 (본인 미포함 - 사용안함) */
    310000,       /* 1명 (본인만) */
    520000,       /* 2명 */
    730000,       /* 3명 */
    940000,       /* 4명 */
    1150000,      /* 5명 */
    1360000,      /* 6명 */
    1570000,      /* 7명 */
    1780000,      /* 8명 */
    1990000,      /* 9명 */
    2200000,      /* 10명 */
    2410000       /* 11명 이상 */
};

/* 2020-07-01 사용안함 - 이전 간이세액표 */
/*
static double g_old_bracket_limit[7] = { ... };
static double g_old_bracket_rate[7] = { ... };
*/

/*******************************************************************************
 * calc_annual_tax - 연간 소득세 계산 (내부 함수)
 *
 * 연간 과세소득에 대한 산출세액 계산
 ******************************************************************************/
static double calc_annual_tax(double annual_taxable)
{
    int i;
    double tax = 0.0;

    if (annual_taxable <= 0) return 0.0;

    for (i = 0; i < TAX_BRACKET_CNT; i++) {
        if (annual_taxable <= g_bracket_limit[i]) {
            tax = annual_taxable * g_bracket_rate[i] - g_bracket_deduct[i];
            break;
        }
    }

    if (tax < 0) tax = 0;
    return tax;
}

/*******************************************************************************
 * get_family_deduction - 부양가족 공제액 (월)
 ******************************************************************************/
static double get_family_deduction(int family_cnt)
{
    if (family_cnt <= 0) family_cnt = 1;
    if (family_cnt > 11) family_cnt = 11;
    return g_family_deduct[family_cnt];
}

/*******************************************************************************
 * tax_calc_income_tax - 소득세 (간이세액) 계산
 *
 * 월 과세소득 기준 간이세액 산출
 * family_cnt: 부양가족수 (본인 포함)
 *
 * 계산 로직:
 * 1. 월 과세소득 -> 연 환산 (x12)
 * 2. 근로소득공제 적용
 * 3. 인적공제 적용
 * 4. 산출세액 계산
 * 5. 근로소득세액공제 적용
 * 6. 월 환산 (/12)
 ******************************************************************************/
int tax_calc_income_tax(double taxable, int family_cnt, double *tax)
{
    double annual_income;
    double earned_deduct;
    double annual_taxable;
    double annual_tax;
    double tax_credit;
    double family_deduct;
    double monthly_tax;

    if (tax == NULL) return PAY_ERR_INVALID;
    *tax = 0.0;

    if (taxable <= 0) return PAY_SUCCESS;

    /* 1. 연 환산 */
    annual_income = taxable * 12.0;

    /* 2. 근로소득공제 */
    if (annual_income <= 5000000) {
        earned_deduct = annual_income * 0.70;
    } else if (annual_income <= 15000000) {
        earned_deduct = 3500000 + (annual_income - 5000000) * 0.40;
    } else if (annual_income <= 45000000) {
        earned_deduct = 7500000 + (annual_income - 15000000) * 0.15;
    } else if (annual_income <= 100000000) {
        earned_deduct = 12000000 + (annual_income - 45000000) * 0.05;
    } else {
        earned_deduct = 14750000 + (annual_income - 100000000) * 0.02;
    }

    /* 3. 인적공제 (부양가족) */
    family_deduct = get_family_deduction(family_cnt) * 12.0;

    /* 과세표준 = 총급여 - 근로소득공제 - 인적공제 */
    annual_taxable = annual_income - earned_deduct - family_deduct;
    if (annual_taxable < 0) annual_taxable = 0;

    /* 4. 산출세액 */
    annual_tax = calc_annual_tax(annual_taxable);

    /* 5. 근로소득세액공제 */
    if (annual_tax <= 1300000) {
        tax_credit = annual_tax * 0.55;
    } else {
        tax_credit = 715000 + (annual_tax - 1300000) * 0.30;
    }
    /* 세액공제 한도: 66만원 (총급여 3300만 이하), 63만원 (7000만 이하), 50만원 (초과) */
    if (annual_income <= 33000000) {
        if (tax_credit > 660000) tax_credit = 660000;
    } else if (annual_income <= 70000000) {
        if (tax_credit > 630000) tax_credit = 630000;
    } else {
        if (tax_credit > 500000) tax_credit = 500000;
    }

    annual_tax -= tax_credit;
    if (annual_tax < 0) annual_tax = 0;

    /* 6. 월 환산 */
    monthly_tax = annual_tax / 12.0;

    /* 10원 단위 절사 */
    *tax = ROUND_10(monthly_tax);

    return PAY_SUCCESS;
}

/*******************************************************************************
 * tax_calc_local_tax - 주민세 (지방소득세) 계산
 *
 * 소득세의 10%
 ******************************************************************************/
int tax_calc_local_tax(double income_tax, double *local_tax)
{
    if (local_tax == NULL) return PAY_ERR_INVALID;

    *local_tax = ROUND_10(income_tax * 0.10);

    /* 2013-01-10 추가 - 100원 미만 절사 */
    /* *local_tax = ((long long)(*local_tax) / 100) * 100; */
    /* 2017 원복 - 10원 단위로 충분 */

    return PAY_SUCCESS;
}

/*******************************************************************************
 * tax_calc_nps - 국민연금 계산
 *
 * 기준소득월액 * 4.5%
 * 하한: 370,000원  상한: 5,900,000원
 ******************************************************************************/
int tax_calc_nps(double salary, double *nps)
{
    double base_salary;

    if (nps == NULL) return PAY_ERR_INVALID;
    *nps = 0.0;

    if (salary <= 0) return PAY_SUCCESS;

    /* 기준소득월액 결정 */
    base_salary = salary;
    if (base_salary < NPS_MIN_SALARY) base_salary = NPS_MIN_SALARY;
    if (base_salary > NPS_MAX_SALARY) base_salary = NPS_MAX_SALARY;

    *nps = ROUND_10(base_salary * RATE_NPS);

    return PAY_SUCCESS;
}

/*******************************************************************************
 * tax_calc_nhi - 건강보험 + 장기요양보험 계산
 *
 * 건강보험: 보수월액 * 3.545%
 * 장기요양: 건강보험료 * 12.81%
 ******************************************************************************/
int tax_calc_nhi(double salary, double *nhi, double *ltc)
{
    double nhi_amt;

    if (nhi == NULL || ltc == NULL) return PAY_ERR_INVALID;
    *nhi = 0.0;
    *ltc = 0.0;

    if (salary <= 0) return PAY_SUCCESS;

    nhi_amt = salary * RATE_NHI;
    *nhi = ROUND_10(nhi_amt);

    /* 장기요양보험 = 건강보험료의 12.81% */
    *ltc = ROUND_10(nhi_amt * RATE_LTC);

    return PAY_SUCCESS;
}

/*******************************************************************************
 * tax_calc_ei - 고용보험 계산
 *
 * 보수총액 * 0.9%
 ******************************************************************************/
int tax_calc_ei(double salary, double *ei)
{
    if (ei == NULL) return PAY_ERR_INVALID;
    *ei = 0.0;

    if (salary <= 0) return PAY_SUCCESS;

    *ei = ROUND_10(salary * RATE_EI);

    return PAY_SUCCESS;
}

/*******************************************************************************
 * tax_get_nontaxable - 비과세 합계 산출
 *
 * 비과세 항목: 식대(20만), 교통비(20만), 보육수당(10만), 연구활동비(20만)
 * 각 항목별 한도 적용
 ******************************************************************************/
double tax_get_nontaxable(const PAY_ITEM *items, int cnt)
{
    double nontaxable = 0.0;
    int i;

    if (items == NULL || cnt <= 0) return 0.0;

    for (i = 0; i < cnt; i++) {
        if (items[i].tax_yn == 'N') {
            double item_amt = items[i].amount;

            /* 항목별 비과세 한도 적용 */
            if (strcmp(items[i].item_code, ALLOW_MEAL) == 0) {
                if (item_amt > TAX_FREE_MEAL) item_amt = TAX_FREE_MEAL;
            } else if (strcmp(items[i].item_code, ALLOW_TRANSPORT) == 0) {
                if (item_amt > TAX_FREE_TRANSPORT) item_amt = TAX_FREE_TRANSPORT;
            } else if (strcmp(items[i].item_code, ALLOW_CHILDCARE) == 0) {
                if (item_amt > TAX_FREE_CHILDCARE) item_amt = TAX_FREE_CHILDCARE;
            } else if (strcmp(items[i].item_code, ALLOW_RESEARCH) == 0) {
                if (item_amt > TAX_FREE_RESEARCH) item_amt = TAX_FREE_RESEARCH;
            }
            /* 기타 비과세 항목은 전액 비과세 */

            nontaxable += item_amt;
        }
    }

    return nontaxable;
}

/*******************************************************************************
 * tax_calc_all - 전체 세금/공제 일괄 계산
 *
 * pay_main.pc에서 함수 포인터로 호출됨
 * taxable: 과세 합계 (총지급 - 비과세)
 * salary: 보수월액 (4대보험 기준)
 ******************************************************************************/
int tax_calc_all(double taxable, double salary, int family_cnt,
                 double *income_tax, double *local_tax,
                 double *nps, double *nhi, double *ltc, double *ei)
{
    int rc;

    if (!income_tax || !local_tax || !nps || !nhi || !ltc || !ei) {
        return PAY_ERR_INVALID;
    }

    /* 소득세 */
    rc = tax_calc_income_tax(taxable, family_cnt, income_tax);
    if (rc != PAY_SUCCESS) {
        PAY_LOG_ERROR("Income tax calculation failed: rc=%d", rc);
        return rc;
    }

    /* 주민세 */
    rc = tax_calc_local_tax(*income_tax, local_tax);
    if (rc != PAY_SUCCESS) {
        PAY_LOG_ERROR("Local tax calculation failed: rc=%d", rc);
        return rc;
    }

    /* 국민연금 */
    rc = tax_calc_nps(salary, nps);
    if (rc != PAY_SUCCESS) {
        PAY_LOG_ERROR("NPS calculation failed: rc=%d", rc);
        return rc;
    }

    /* 건강보험 + 장기요양 */
    rc = tax_calc_nhi(salary, nhi, ltc);
    if (rc != PAY_SUCCESS) {
        PAY_LOG_ERROR("NHI calculation failed: rc=%d", rc);
        return rc;
    }

    /* 고용보험 */
    rc = tax_calc_ei(salary, ei);
    if (rc != PAY_SUCCESS) {
        PAY_LOG_ERROR("EI calculation failed: rc=%d", rc);
        return rc;
    }

    return PAY_SUCCESS;
}
