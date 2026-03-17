/*******************************************************************************
 * loan_common.h - 대출 심사 시스템 공통 헤더
 *
 * 작성일: 2009-11-10
 * 수정일: 2014-03-20  최차장 - 담보대출 구조체 추가
 * 수정일: 2017-09-15  김대리 - 심사규칙 코드 확장
 * 수정일: 2020-06-01  박과장 - 동적SQL 관련 상수
 * 수정일: 2022-11-30  이사원 - 상환방식 추가
 *
 * 대출 관련 공통 구조체, 상수, 에러코드
 ******************************************************************************/
#ifndef _LOAN_COMMON_H_
#define _LOAN_COMMON_H_

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

/* 시스템 상수 */
#define MAX_LOAN_NO           16
#define MAX_CUST_NO           16
#define MAX_CUST_NAME         50
#define MAX_PROD_CODE         10
#define MAX_PROD_NAME         60
#define MAX_BRANCH_CODE       6
#define MAX_DATE_LEN          11
#define MAX_DATETIME_LEN      20
#define MAX_ERR_MSG           256
#define MAX_NOTE              500
#define MAX_PHONE             15
#define MAX_ADDR              200
#define MAX_ARRAY_SIZE        2000
#define COMMIT_UNIT           100
#define MAX_SCHEDULE_CNT      600      /* 최대 50년 (600개월) */
#define MAX_RULE_CNT          50
#define MAX_SQL_LEN           4000
#define MAX_COLLATERAL_CNT    5

/* 대출 상태 */
#define LOAN_STATUS_APPLY     "10"     /* 신청 */
#define LOAN_STATUS_REVIEW    "20"     /* 심사중 */
#define LOAN_STATUS_APPROVED  "30"     /* 승인 */
#define LOAN_STATUS_REJECTED  "40"     /* 거절 */
#define LOAN_STATUS_DISBURSED "50"     /* 실행 */
#define LOAN_STATUS_NORMAL    "60"     /* 정상상환중 */
#define LOAN_STATUS_OVERDUE   "70"     /* 연체 */
#define LOAN_STATUS_CLOSED    "80"     /* 완제 */
#define LOAN_STATUS_WRITEOFF  "90"     /* 상각 */

/* 상환 방식 */
#define REPAY_EQUAL_PMT       'E'      /* 원리금균등 */
#define REPAY_EQUAL_PRINC     'P'      /* 원금균등 */
#define REPAY_BULLET          'B'      /* 만기일시 */
#define REPAY_INTEREST_ONLY   'I'      /* 거치후일시 (이자만) */

/* 대출 유형 */
#define LOAN_TYPE_PERSONAL    "PL"     /* 개인신용 */
#define LOAN_TYPE_MORTGAGE    "MG"     /* 주택담보 */
#define LOAN_TYPE_AUTO        "AL"     /* 자동차 */
#define LOAN_TYPE_BUSINESS    "BL"     /* 사업자 */

/* 신용등급 */
#define CREDIT_GRADE_1        1        /* 최우량 */
#define CREDIT_GRADE_2        2
#define CREDIT_GRADE_3        3
#define CREDIT_GRADE_4        4
#define CREDIT_GRADE_5        5
#define CREDIT_GRADE_6        6
#define CREDIT_GRADE_7        7
#define CREDIT_GRADE_8        8
#define CREDIT_GRADE_9        9
#define CREDIT_GRADE_10       10       /* 최저 */

/* 금리 유형 */
#define RATE_FIXED            'F'      /* 고정금리 */
#define RATE_VARIABLE         'V'      /* 변동금리 */
#define RATE_MIXED            'M'      /* 혼합금리 (초기고정 후 변동) */

/* 심사 규칙 유형 */
#define RULE_INCOME_RATIO     "R01"    /* 소득대비 상환비율 */
#define RULE_CREDIT_GRADE     "R02"    /* 신용등급 */
#define RULE_AGE_LIMIT        "R03"    /* 나이 제한 */
#define RULE_EXIST_LOAN       "R04"    /* 기존 대출 건수 */
#define RULE_OVERDUE_HIST     "R05"    /* 연체 이력 */
#define RULE_COLLATERAL       "R06"    /* 담보 비율 */
#define RULE_EMPLOYMENT       "R07"    /* 재직 기간 */
#define RULE_BLACKLIST        "R08"    /* 블랙리스트 */

/* 2017-09-15 추가 */
#define RULE_DEBT_RATIO       "R09"    /* 총부채상환비율 (DSR) */
#define RULE_LTV              "R10"    /* 담보인정비율 (LTV) */

/* 에러코드 */
#define LOAN_SUCCESS          0
#define LOAN_ERR_DB           -1001
#define LOAN_ERR_DB_SELECT    -1002
#define LOAN_ERR_DB_INSERT    -1003
#define LOAN_ERR_DB_UPDATE    -1004
#define LOAN_ERR_NOT_FOUND    -2001
#define LOAN_ERR_DUPLICATE    -2002
#define LOAN_ERR_INVALID      -2003
#define LOAN_ERR_STATUS       -2004
#define LOAN_ERR_CREDIT       -3001
#define LOAN_ERR_CALC         -3002
#define LOAN_ERR_RULE         -3003
#define LOAN_ERR_REJECTED     -3004
#define LOAN_ERR_TIMEOUT      -4001
#define LOAN_ERR_EXTERNAL     -4002
#define LOAN_ERR_MEMORY       -5001
#define LOAN_ERR_SQL          -6001

/*******************************************************************************
 * 구조체 정의
 ******************************************************************************/

/* 고객 신용 정보 */
typedef struct _credit_info {
    char    cust_no[MAX_CUST_NO];
    char    cust_name[MAX_CUST_NAME];
    int     credit_grade;                /* 1~10 */
    int     credit_score;                /* 0~1000 */
    double  annual_income;               /* 연소득 */
    double  monthly_income;              /* 월소득 */
    int     age;
    char    employment_type;             /* S:급여 B:사업 F:프리 N:무직 */
    int     employment_months;           /* 재직기간 (월) */
    int     exist_loan_cnt;              /* 기존 대출 건수 */
    double  exist_loan_balance;          /* 기존 대출 잔액 합계 */
    double  monthly_repayment;           /* 기존 월상환액 합계 */
    int     overdue_cnt_1y;              /* 최근1년 연체횟수 */
    int     overdue_cnt_3y;              /* 최근3년 연체횟수 */
    long    max_overdue_days;            /* 최장 연체일수 */
    char    blacklist_yn;                /* 블랙리스트 여부 */
    char    inquiry_date[MAX_DATE_LEN];  /* 조회일자 */
} CREDIT_INFO;

/* 담보 정보 (2014-03-20 추가) */
typedef struct _collateral_info {
    char    collateral_type[5];          /* 담보유형 RE:부동산 VH:차량 DP:예금 */
    char    collateral_desc[100];        /* 담보 설명 */
    double  appraised_value;             /* 감정가 */
    double  collateral_value;            /* 담보가치 (감정가 * 인정비율) */
    double  recognition_rate;            /* 인정비율 */
    double  prior_lien_amt;              /* 선순위 설정금액 */
    double  available_amt;               /* 가용 담보액 = 담보가치 - 선순위 */
} COLLATERAL_INFO;

/* 대출 신청 정보 */
typedef struct _loan_application {
    char    loan_no[MAX_LOAN_NO];
    char    cust_no[MAX_CUST_NO];
    char    prod_code[MAX_PROD_CODE];
    char    loan_type[3];                /* PL, MG, AL, BL */
    double  request_amt;                 /* 신청금액 */
    double  approved_amt;                /* 승인금액 */
    double  interest_rate;               /* 적용금리 */
    char    rate_type;                   /* F:고정 V:변동 M:혼합 */
    int     loan_term_months;            /* 대출기간 (월) */
    int     grace_months;                /* 거치기간 (월) */
    char    repay_type;                  /* E:원리금균등 P:원금균등 B:만기일시 I:거치 */
    char    status[3];                   /* 상태코드 */
    char    apply_date[MAX_DATE_LEN];
    char    approve_date[MAX_DATE_LEN];
    char    disburse_date[MAX_DATE_LEN];
    char    maturity_date[MAX_DATE_LEN];
    char    branch_code[MAX_BRANCH_CODE];
    /* 신용정보 */
    CREDIT_INFO     credit;
    /* 담보정보 */
    COLLATERAL_INFO collaterals[MAX_COLLATERAL_CNT];
    int             collateral_cnt;
    double          total_collateral_value;
    /* 관리 */
    char    note[MAX_NOTE];
    char    reg_user[20];
    char    reg_date[MAX_DATETIME_LEN];
    char    upd_user[20];
    char    upd_date[MAX_DATETIME_LEN];
} LOAN_APPLICATION;

/* 상환 스케줄 */
typedef struct _repay_schedule {
    int     seq;                         /* 회차 */
    char    due_date[MAX_DATE_LEN];      /* 납부일 */
    double  payment;                     /* 납부액 */
    double  principal;                   /* 원금 */
    double  interest;                    /* 이자 */
    double  balance;                     /* 잔액 */
    char    paid_yn;                     /* 납부여부 */
    char    paid_date[MAX_DATE_LEN];     /* 실납부일 */
    int     overdue_days;                /* 연체일수 */
} REPAY_SCHEDULE;

/* 심사 규칙 결과 */
typedef struct _rule_result {
    char    rule_code[5];
    char    rule_name[30];
    char    pass_yn;                     /* Y:통과 N:불통과 W:경고 */
    char    detail[200];                 /* 상세내용 */
    double  threshold;                   /* 기준값 */
    double  actual_value;                /* 실제값 */
} RULE_RESULT;

/* 심사 결과 */
typedef struct _approval_result {
    char    decision;                    /* A:승인 R:거절 C:조건부승인 */
    double  approved_amt;
    double  approved_rate;
    int     approved_term;
    int     rule_cnt;
    RULE_RESULT rules[MAX_RULE_CNT];
    int     pass_cnt;
    int     fail_cnt;
    int     warn_cnt;
    char    reason[MAX_NOTE];
} APPROVAL_RESULT;

/*******************************************************************************
 * 함수 선언
 ******************************************************************************/

/* loan_main.pc */
int  loan_apply(LOAN_APPLICATION *app);
int  loan_select(const char *loan_no, LOAN_APPLICATION *app);
int  loan_update_status(const char *loan_no, const char *new_status, const char *user_id);
int  loan_disburse(const char *loan_no, const char *user_id);
int  loan_search_by_status(const char *status, LOAN_APPLICATION *list, int *cnt);

/* credit_check.pc */
int  credit_inquiry(const char *cust_no, CREDIT_INFO *info);
int  credit_check_blacklist(const char *cust_no, int *is_blacklisted);
int  credit_get_exist_loans(const char *cust_no, double *balance, double *monthly, int *cnt);

/* loan_calc.pc */
int  loan_calc_rate(const LOAN_APPLICATION *app, double *rate);
int  loan_calc_schedule_equal_pmt(double principal, double annual_rate, int months, int grace, REPAY_SCHEDULE *schedule, int *cnt);
int  loan_calc_schedule_equal_princ(double principal, double annual_rate, int months, int grace, REPAY_SCHEDULE *schedule, int *cnt);
int  loan_calc_schedule_bullet(double principal, double annual_rate, int months, REPAY_SCHEDULE *schedule, int *cnt);
int  loan_calc_schedule(const LOAN_APPLICATION *app, REPAY_SCHEDULE *schedule, int *cnt);
double loan_calc_dsr(double monthly_income, double monthly_repay_total);
double loan_calc_ltv(double loan_amt, double collateral_value);

/* loan_approve.pc */
int  loan_approve_check(LOAN_APPLICATION *app, APPROVAL_RESULT *result);
int  loan_execute_rules(LOAN_APPLICATION *app, RULE_RESULT *rules, int *cnt);
int  loan_dynamic_rule_query(const char *rule_code, const char *cust_no, double *result_value);

/*******************************************************************************
 * 유틸리티 매크로
 ******************************************************************************/
#define LN_STRCPY(dst, src, len) do { strncpy((dst), (src), (len)-1); (dst)[(len)-1] = '\0'; } while(0)

#define LN_LOG(level, fmt, ...) do { \
    time_t _t = time(NULL); struct tm *_tm = localtime(&_t); \
    fprintf(stderr, "[%04d-%02d-%02d %02d:%02d:%02d][%s] " fmt "\n", \
        _tm->tm_year+1900, _tm->tm_mon+1, _tm->tm_mday, \
        _tm->tm_hour, _tm->tm_min, _tm->tm_sec, (level), ##__VA_ARGS__); \
} while(0)

#define LN_INFO(fmt, ...)  LN_LOG("INFO", fmt, ##__VA_ARGS__)
#define LN_ERROR(fmt, ...) LN_LOG("ERROR", fmt, ##__VA_ARGS__)
#define LN_WARN(fmt, ...)  LN_LOG("WARN", fmt, ##__VA_ARGS__)
#define LN_DEBUG(fmt, ...) LN_LOG("DEBUG", fmt, ##__VA_ARGS__)

#define LN_CHECK_NULL(p) do { if (!(p)) { LN_ERROR("NULL param at %s:%d", __FILE__, __LINE__); return LOAN_ERR_INVALID; } } while(0)

/* 10원 단위 반올림 */
#define ROUND_10(x) (((long long)((x) + 5) / 10) * 10)

/* 원 단위 반올림 */
#define ROUND_1(x) ((long long)((x) + 0.5))

#endif /* _LOAN_COMMON_H_ */
