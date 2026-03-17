/*******************************************************************************
 * pay_common.h - 급여 정산 시스템 공통 헤더
 *
 * 작성일: 2006-05-20
 * 수정일: 2013-01-10  최과장 - 4대보험 요율 업데이트
 * 수정일: 2017-03-15  김대리 - 비과세 한도 확대
 * 수정일: 2020-07-01  박사원 - 2020년 세법 개정 반영
 * 수정일: 2023-01-02  이대리 - 2023년 요율 반영
 *
 * 급여 관련 공통 구조체, 상수, 매크로 정의
 ******************************************************************************/
#ifndef _PAY_COMMON_H_
#define _PAY_COMMON_H_

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

/* 시스템 상수 */
#define MAX_EMP_NO            12
#define MAX_EMP_NAME          40
#define MAX_DEPT_CODE         10
#define MAX_DEPT_NAME         50
#define MAX_POSITION          20
#define MAX_DATE_LEN          11
#define MAX_YYYYMM            7        /* YYYYMM + null */
#define MAX_ERR_MSG           256
#define MAX_ARRAY_SIZE        5000
#define COMMIT_UNIT           200
#define MAX_ALLOW_CNT         20       /* 최대 수당 항목 수 */
#define MAX_DEDUCT_CNT        20       /* 최대 공제 항목 수 */
#define MAX_NOTE              200

/* 급여 항목 코드 - 수당 (1xx) */
#define ALLOW_BASE_PAY        "101"    /* 기본급 */
#define ALLOW_POSITION_PAY    "102"    /* 직책수당 */
#define ALLOW_OVERTIME_PAY    "103"    /* 시간외수당 */
#define ALLOW_NIGHT_PAY       "104"    /* 야간수당 */
#define ALLOW_HOLIDAY_PAY     "105"    /* 휴일수당 */
#define ALLOW_MEAL            "106"    /* 식대 */
#define ALLOW_TRANSPORT       "107"    /* 교통비 */
#define ALLOW_FAMILY          "108"    /* 가족수당 */
#define ALLOW_BONUS           "109"    /* 상여금 */
#define ALLOW_ANNUAL          "110"    /* 연차수당 */
#define ALLOW_TECH            "111"    /* 기술수당 */
#define ALLOW_DANGER          "112"    /* 위험수당 */

/* 2017-03-15 김대리 추가 - 비과세항목 확장 */
#define ALLOW_CHILDCARE       "113"    /* 보육수당 */
#define ALLOW_RESEARCH        "114"    /* 연구수당 */

/* 급여 항목 코드 - 공제 (2xx) */
#define DEDUCT_INCOME_TAX     "201"    /* 소득세 */
#define DEDUCT_LOCAL_TAX      "202"    /* 주민세 (소득세의 10%) */
#define DEDUCT_NPS            "203"    /* 국민연금 */
#define DEDUCT_NHI            "204"    /* 건강보험 */
#define DEDUCT_LTC            "205"    /* 장기요양보험 */
#define DEDUCT_EI             "206"    /* 고용보험 */
#define DEDUCT_UNION          "207"    /* 조합비 */
#define DEDUCT_LOAN           "208"    /* 대출상환 */
#define DEDUCT_ADVANCE        "209"    /* 가불금 */
#define DEDUCT_ETC            "210"    /* 기타공제 */

/* 2023년 4대보험 요율 (근로자 부담분) */
#define RATE_NPS              0.045    /* 국민연금 4.5% */
#define RATE_NHI              0.03545  /* 건강보험 3.545% */
#define RATE_LTC              0.1281   /* 장기요양 12.81% (건보료의) */
#define RATE_EI               0.009    /* 고용보험 0.9% */

/* 국민연금 상/하한 */
#define NPS_MIN_SALARY        370000   /* 하한 기준소득월액 */
#define NPS_MAX_SALARY        5900000  /* 상한 기준소득월액 */

/* 2020년 세법 기준 - 비과세 한도 */
#define TAX_FREE_MEAL         200000   /* 식대 비과세 한도 (2023년 기준) */
#define TAX_FREE_TRANSPORT    200000   /* 교통비 비과세 한도 */
#define TAX_FREE_CHILDCARE    100000   /* 보육수당 비과세 한도 */
#define TAX_FREE_RESEARCH     200000   /* 연구활동비 비과세 한도 */
/* 2017년 이전 값 - 사용안함 */
/* #define TAX_FREE_MEAL_OLD  100000 */
/* #define TAX_FREE_TRANSPORT_OLD 100000 */

/* 시간외 수당 관련 */
#define OVERTIME_RATE         1.5      /* 시간외 할증률 150% */
#define NIGHT_RATE            2.0      /* 야간 할증률 200% */
#define HOLIDAY_RATE          2.0      /* 휴일 할증률 200% */
#define WORK_HOURS_PER_MONTH  209      /* 월 소정근로시간 */

/* 에러코드 */
#define PAY_SUCCESS           0
#define PAY_ERR_DB            -1001
#define PAY_ERR_NOT_FOUND     -2001
#define PAY_ERR_DUPLICATE     -2002
#define PAY_ERR_INVALID       -2003
#define PAY_ERR_CALC          -3001
#define PAY_ERR_TAX           -3002
#define PAY_ERR_OVERFLOW      -3003
#define PAY_ERR_ALREADY_DONE  -4001
#define PAY_ERR_MEMORY        -5001
#define PAY_ERR_FILE          -6001

/*******************************************************************************
 * 구조체 정의
 ******************************************************************************/

/* 사원 정보 */
typedef struct _emp_info {
    char    emp_no[MAX_EMP_NO];              /* 사원번호 */
    char    emp_name[MAX_EMP_NAME];          /* 사원명 */
    char    dept_code[MAX_DEPT_CODE];        /* 부서코드 */
    char    dept_name[MAX_DEPT_NAME];        /* 부서명 */
    char    position[MAX_POSITION];          /* 직급 */
    char    hire_date[MAX_DATE_LEN];         /* 입사일 */
    char    resign_date[MAX_DATE_LEN];       /* 퇴사일 (재직중이면 빈값) */
    int     family_cnt;                      /* 부양가족수 (본인포함) */
    int     child_cnt;                       /* 자녀수 */
    double  base_salary;                     /* 기본급 */
    double  position_pay;                    /* 직책수당 */
    char    tax_type;                        /* 과세유형 A:일반 B:일용직 C:외국인 */
    char    union_yn;                        /* 조합원여부 Y/N */
    double  union_rate;                      /* 조합비율 */
    double  loan_deduct;                     /* 대출상환금 (고정공제) */
    char    bank_code[5];                    /* 은행코드 */
    char    account_no[20];                  /* 계좌번호 */
    char    active_yn;                       /* 재직여부 Y/N */
} EMP_INFO;

/* 수당/공제 항목 */
typedef struct _pay_item {
    char    item_code[5];                    /* 항목코드 */
    char    item_name[30];                   /* 항목명 */
    double  amount;                          /* 금액 */
    char    tax_yn;                          /* 과세여부 Y/N */
} PAY_ITEM;

/* 급여 명세 */
typedef struct _pay_detail {
    char    emp_no[MAX_EMP_NO];
    char    pay_ym[MAX_YYYYMM];              /* 급여년월 */
    /* 수당 */
    PAY_ITEM    allowances[MAX_ALLOW_CNT];
    int         allow_cnt;
    double      allow_total;                 /* 수당 합계 */
    double      taxable_total;               /* 과세 합계 */
    double      nontaxable_total;            /* 비과세 합계 */
    /* 공제 */
    PAY_ITEM    deductions[MAX_DEDUCT_CNT];
    int         deduct_cnt;
    double      deduct_total;                /* 공제 합계 */
    /* 세금 상세 */
    double      income_tax;                  /* 소득세 */
    double      local_tax;                   /* 주민세 */
    double      nps;                         /* 국민연금 */
    double      nhi;                         /* 건강보험 */
    double      ltc;                         /* 장기요양 */
    double      ei;                          /* 고용보험 */
    /* 합계 */
    double      gross_pay;                   /* 총지급액 */
    double      total_deduct;                /* 총공제액 */
    double      net_pay;                     /* 실수령액 */
    /* 상태 */
    char    status;                           /* 상태 N:미확정 C:확정 P:지급완료 */
    char    calc_date[MAX_DATE_LEN];         /* 산출일자 */
    char    pay_date[MAX_DATE_LEN];          /* 지급일자 */
    char    note[MAX_NOTE];
} PAY_DETAIL;

/* 배치 처리 결과 */
typedef struct _batch_result {
    int     total_cnt;
    int     success_cnt;
    int     fail_cnt;
    double  total_gross;
    double  total_deduct;
    double  total_net;
    char    start_time[20];
    char    end_time[20];
} BATCH_RESULT;

/*******************************************************************************
 * 함수 선언 - pay_main.pc
 ******************************************************************************/
int  pay_batch_process(const char *pay_ym, BATCH_RESULT *result);
int  pay_single_process(const char *emp_no, const char *pay_ym, PAY_DETAIL *detail);
int  pay_confirm_batch(const char *pay_ym, int *confirmed_cnt);
int  pay_select_detail(const char *emp_no, const char *pay_ym, PAY_DETAIL *detail);

/*******************************************************************************
 * 함수 선언 - tax_calc.c (순수 C - DB 접근 없음)
 ******************************************************************************/

/* 세금 계산 함수 포인터 타입 */
typedef int (*tax_calc_func_t)(double taxable, int family_cnt, double *tax);

int  tax_calc_income_tax(double taxable, int family_cnt, double *tax);
int  tax_calc_local_tax(double income_tax, double *local_tax);
int  tax_calc_nps(double salary, double *nps);
int  tax_calc_nhi(double salary, double *nhi, double *ltc);
int  tax_calc_ei(double salary, double *ei);
int  tax_calc_all(double taxable, double salary, int family_cnt,
                  double *income_tax, double *local_tax,
                  double *nps, double *nhi, double *ltc, double *ei);
double tax_get_nontaxable(const PAY_ITEM *items, int cnt);

/*******************************************************************************
 * 함수 선언 - pay_detail.pc
 ******************************************************************************/
int  pay_load_allowances(const char *emp_no, const char *pay_ym, PAY_ITEM *items, int *cnt, double *total);
int  pay_load_deductions(const char *emp_no, const char *pay_ym, PAY_ITEM *items, int *cnt, double *total);
int  pay_save_detail(const PAY_DETAIL *detail);
int  pay_calc_overtime(const char *emp_no, const char *pay_ym, double base_salary, double *overtime, double *night, double *holiday);
int  pay_generate_slip(const PAY_DETAIL *detail, FILE *fp);

/*******************************************************************************
 * 유틸리티 매크로
 ******************************************************************************/
#define PAY_STRCPY(dst, src, len) do { \
    strncpy((dst), (src), (len)-1); \
    (dst)[(len)-1] = '\0'; \
} while(0)

#define PAY_LOG(level, fmt, ...) do { \
    char _ts[20]; \
    time_t _now = time(NULL); \
    struct tm *_tm = localtime(&_now); \
    snprintf(_ts, sizeof(_ts), "%04d-%02d-%02d %02d:%02d:%02d", \
        _tm->tm_year+1900, _tm->tm_mon+1, _tm->tm_mday, \
        _tm->tm_hour, _tm->tm_min, _tm->tm_sec); \
    fprintf(stderr, "[%s][%s] " fmt "\n", _ts, (level), ##__VA_ARGS__); \
} while(0)

#define PAY_LOG_INFO(fmt, ...)  PAY_LOG("INFO", fmt, ##__VA_ARGS__)
#define PAY_LOG_ERROR(fmt, ...) PAY_LOG("ERROR", fmt, ##__VA_ARGS__)
#define PAY_LOG_WARN(fmt, ...)  PAY_LOG("WARN", fmt, ##__VA_ARGS__)

/* 원 단위 절사 (10원 미만 절사) */
#define ROUND_10(x) (((long long)(x) / 10) * 10)

/* NULL 체크 */
#define PAY_CHECK_NULL(p) do { if (!(p)) { PAY_LOG_ERROR("NULL param at %s:%d", __FILE__, __LINE__); return PAY_ERR_INVALID; } } while(0)

#endif /* _PAY_COMMON_H_ */
