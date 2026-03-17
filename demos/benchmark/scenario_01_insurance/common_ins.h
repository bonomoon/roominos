/*******************************************************************************
 * common_ins.h - 보험 공통 헤더
 *
 * 작성일: 2008-03-15
 * 수정일: 2019-11-22  김대리 - 단체보험 구조체 추가
 * 수정일: 2021-06-10  박과장 - 에러코드 확장
 *
 * 보험 계약 관리 시스템 공통 정의
 * - 구조체, 매크로, 에러코드, 유틸리티 함수 선언
 ******************************************************************************/
#ifndef _COMMON_INS_H_
#define _COMMON_INS_H_

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* 시스템 상수 */
#define MAX_CONTRACT_NO       20
#define MAX_CUST_NAME         50
#define MAX_PROD_CODE         10
#define MAX_BRANCH_CODE       6
#define MAX_ERR_MSG           256
#define MAX_PHONE             15
#define MAX_ADDR              200
#define MAX_NOTE              500
#define MAX_ARRAY_SIZE        1000
#define COMMIT_UNIT           100
#define MAX_RIDER_CNT         10
#define MAX_BENEFICIARY_CNT   5
#define MAX_PRODUCT_NAME      60
#define MAX_DATE_LEN          11       /* YYYY-MM-DD + null */
#define MAX_DATETIME_LEN      20       /* YYYY-MM-DD HH:MI:SS + null */
#define MAX_AMT_STR           20

/* 2019-11-22 김대리 추가 - 단체보험 */
#define MAX_GROUP_MEMBER      500
#define MAX_GROUP_NAME        100

/* 계약 상태 코드 */
#define STATUS_NORMAL         "01"     /* 정상 */
#define STATUS_LAPSE          "02"     /* 실효 */
#define STATUS_SURRENDER      "03"     /* 해약 */
#define STATUS_MATURITY       "04"     /* 만기 */
#define STATUS_CANCEL         "05"     /* 취소 */
#define STATUS_PENDING        "06"     /* 보류 */
#define STATUS_REINSTATE      "07"     /* 부활 */

/* 2021-01-15 이사원 추가 - 사용안함 */
/* #define STATUS_TRANSFER    "08" */
/* #define STATUS_CONVERT     "09" */

/* 납입 주기 */
#define PAY_MONTHLY           "M"
#define PAY_QUARTERLY         "Q"
#define PAY_SEMIANNUAL        "S"
#define PAY_ANNUAL            "A"
#define PAY_SINGLE            "1"

/* 보험료 계산 관련 */
#define BASE_RATE_MALE_20     0.0152
#define BASE_RATE_MALE_30     0.0187
#define BASE_RATE_MALE_40     0.0245
#define BASE_RATE_MALE_50     0.0356
#define BASE_RATE_MALE_60     0.0512
#define BASE_RATE_FEMALE_20   0.0128
#define BASE_RATE_FEMALE_30   0.0156
#define BASE_RATE_FEMALE_40   0.0198
#define BASE_RATE_FEMALE_50   0.0289
#define BASE_RATE_FEMALE_60   0.0421

/* 등급별 할인/할증 */
#define GRADE_SUPER           0.85     /* 우량체 15% 할인 */
#define GRADE_PREF            0.92     /* 표준우량 8% 할인 */
#define GRADE_STD             1.00     /* 표준체 */
#define GRADE_SUB1            1.15     /* 표준미달1 15% 할증 */
#define GRADE_SUB2            1.30     /* 표준미달2 30% 할증 */
#define GRADE_DECLINE         9.99     /* 인수거절 */

/* 에러코드 */
#define ERR_SUCCESS           0
#define ERR_DB_CONNECT        -1001
#define ERR_DB_SELECT         -1002
#define ERR_DB_INSERT         -1003
#define ERR_DB_UPDATE         -1004
#define ERR_DB_DELETE         -1005
#define ERR_DB_COMMIT         -1006
#define ERR_DB_ROLLBACK       -1007
#define ERR_NOT_FOUND         -2001
#define ERR_DUPLICATE         -2002
#define ERR_INVALID_PARAM     -2003
#define ERR_INVALID_STATUS    -2004
#define ERR_CALC_OVERFLOW     -3001
#define ERR_CALC_UNDERFLOW    -3002
#define ERR_CALC_INVALID_AGE  -3003
#define ERR_CALC_INVALID_SEX  -3004
#define ERR_CALC_INVALID_GRADE -3005
#define ERR_FILE_OPEN         -4001
#define ERR_FILE_WRITE        -4002
#define ERR_MEMORY            -5001
#define ERR_UNKNOWN           -9999

/* 2021-06-10 박과장 추가 */
#define ERR_RIDER_LIMIT       -3010
#define ERR_BENEFICIARY_LIMIT -3011
#define ERR_PREMIUM_ZERO      -3012
#define ERR_CONTRACT_LOCKED   -6001
#define ERR_BATCH_TIMEOUT     -7001

/*******************************************************************************
 * 구조체 정의
 ******************************************************************************/

/* 고객 정보 */
typedef struct _customer_info {
    char    cust_no[MAX_CONTRACT_NO];       /* 고객번호 */
    char    cust_name[MAX_CUST_NAME];       /* 고객명 */
    char    birth_date[MAX_DATE_LEN];       /* 생년월일 YYYY-MM-DD */
    char    sex_code;                        /* 성별 M/F */
    int     age;                             /* 나이 */
    char    phone[MAX_PHONE];               /* 전화번호 */
    char    addr[MAX_ADDR];                 /* 주소 */
    char    grade_code[3];                   /* 건강등급 코드 */
    double  grade_factor;                    /* 등급 계수 */
} CUSTOMER_INFO;

/* 상품 정보 */
typedef struct _product_info {
    char    prod_code[MAX_PROD_CODE];       /* 상품코드 */
    char    prod_name[MAX_PRODUCT_NAME];    /* 상품명 */
    char    prod_type;                       /* 상품유형 L:종신 T:정기 E:양로 U:유니버셜 */
    int     ins_period;                      /* 보험기간 (년) */
    int     pay_period;                      /* 납입기간 (년) */
    double  base_premium;                    /* 기본보험료 */
    double  insured_amt;                     /* 보험가입금액 */
    int     max_rider_cnt;                   /* 최대 특약 수 */
    char    sale_yn;                          /* 판매여부 Y/N */
} PRODUCT_INFO;

/* 특약 정보 */
typedef struct _rider_info {
    char    rider_code[MAX_PROD_CODE];      /* 특약코드 */
    char    rider_name[MAX_PRODUCT_NAME];   /* 특약명 */
    double  rider_premium;                   /* 특약보험료 */
    double  rider_amt;                       /* 특약가입금액 */
    char    rider_type;                      /* 특약유형 D:사망 H:입원 S:수술 C:진단 */
} RIDER_INFO;

/* 수익자 정보 */
typedef struct _beneficiary_info {
    char    benef_name[MAX_CUST_NAME];      /* 수익자명 */
    char    benef_rel[10];                   /* 관계코드 */
    double  benef_ratio;                     /* 수익비율 */
    char    benef_type;                      /* 수익자유형 D:사망 M:만기 */
} BENEFICIARY_INFO;

/* 계약 정보 (메인) */
typedef struct _contract_info {
    char    contract_no[MAX_CONTRACT_NO];   /* 계약번호 */
    char    status_code[3];                  /* 계약상태 */
    char    contract_date[MAX_DATE_LEN];    /* 계약일자 */
    char    commence_date[MAX_DATE_LEN];    /* 개시일자 */
    char    maturity_date[MAX_DATE_LEN];    /* 만기일자 */
    char    pay_cycle[2];                    /* 납입주기 */
    double  total_premium;                   /* 총보험료 */
    double  main_premium;                    /* 주계약보험료 */
    double  rider_premium_sum;               /* 특약보험료합 */
    char    branch_code[MAX_BRANCH_CODE];   /* 지점코드 */
    CUSTOMER_INFO   customer;                /* 고객정보 */
    PRODUCT_INFO    product;                 /* 상품정보 */
    RIDER_INFO      riders[MAX_RIDER_CNT];  /* 특약배열 */
    int             rider_cnt;               /* 특약수 */
    BENEFICIARY_INFO beneficiaries[MAX_BENEFICIARY_CNT]; /* 수익자배열 */
    int             beneficiary_cnt;         /* 수익자수 */
    char    last_pay_date[MAX_DATE_LEN];    /* 최종납입일 */
    int     unpaid_months;                   /* 미납월수 */
    char    note[MAX_NOTE];                  /* 비고 */
    char    reg_user[20];                    /* 등록자 */
    char    reg_date[MAX_DATETIME_LEN];     /* 등록일시 */
    char    upd_user[20];                    /* 수정자 */
    char    upd_date[MAX_DATETIME_LEN];     /* 수정일시 */
} CONTRACT_INFO;

/* 보험료 계산 결과 */
typedef struct _premium_result {
    double  base_premium;                    /* 기본보험료 */
    double  age_factor;                      /* 나이계수 */
    double  sex_factor;                      /* 성별계수 */
    double  grade_factor;                    /* 등급계수 */
    double  period_factor;                   /* 기간계수 */
    double  cycle_factor;                    /* 납입주기계수 */
    double  main_premium;                    /* 주계약보험료 */
    double  rider_premiums[MAX_RIDER_CNT];  /* 특약별보험료 */
    double  total_rider_premium;             /* 특약보험료합계 */
    double  total_premium;                   /* 총보험료 */
    double  discount_amt;                    /* 할인금액 */
    double  surcharge_amt;                   /* 할증금액 */
    int     err_code;                        /* 에러코드 */
    char    err_msg[MAX_ERR_MSG];           /* 에러메시지 */
} PREMIUM_RESULT;

/* 2019-11-22 김대리 추가 - 단체보험 */
typedef struct _group_contract {
    char    group_no[MAX_CONTRACT_NO];
    char    group_name[MAX_GROUP_NAME];
    int     member_cnt;
    double  group_discount_rate;
    char    contract_nos[MAX_GROUP_MEMBER][MAX_CONTRACT_NO];
} GROUP_CONTRACT;

/*******************************************************************************
 * 함수 선언 - contract_main.pc
 ******************************************************************************/
int  ins_select_contract(const char *contract_no, CONTRACT_INFO *info);
int  ins_insert_contract(const CONTRACT_INFO *info);
int  ins_update_contract(const CONTRACT_INFO *info);
int  ins_update_status(const char *contract_no, const char *new_status, const char *user_id);
int  ins_delete_contract(const char *contract_no);
int  ins_search_by_customer(const char *cust_no, CONTRACT_INFO *list, int *cnt);
int  ins_search_by_branch(const char *branch_code, const char *from_date, const char *to_date, CONTRACT_INFO *list, int *cnt);
int  ins_batch_lapse_check(const char *base_date, int *processed_cnt);

/*******************************************************************************
 * 함수 선언 - premium_calc.pc
 ******************************************************************************/
int  calc_premium(const CONTRACT_INFO *contract, PREMIUM_RESULT *result);
int  calc_main_premium(const PRODUCT_INFO *product, const CUSTOMER_INFO *customer, double *premium);
int  calc_rider_premium(const RIDER_INFO *rider, const CUSTOMER_INFO *customer, double *premium);
int  calc_age_factor(int age, char sex_code, double *factor);
int  calc_grade_factor(const char *grade_code, double *factor);
int  calc_cycle_factor(const char *pay_cycle, double *factor);
int  calc_period_factor(int ins_period, int pay_period, double *factor);
int  recalc_all_premiums(const char *prod_code, int *processed_cnt);

/*******************************************************************************
 * 유틸리티 매크로
 ******************************************************************************/
#define SAFE_STRCPY(dst, src, len) do { \
    strncpy((dst), (src), (len)-1); \
    (dst)[(len)-1] = '\0'; \
} while(0)

#define LOG_ERROR(code, msg) do { \
    fprintf(stderr, "[ERROR][%d] %s (file:%s line:%d)\n", (code), (msg), __FILE__, __LINE__); \
} while(0)

#define LOG_INFO(msg) do { \
    fprintf(stdout, "[INFO] %s\n", (msg)); \
} while(0)

#define LOG_DEBUG(fmt, ...) do { \
    fprintf(stdout, "[DEBUG][%s:%d] " fmt "\n", __FILE__, __LINE__, ##__VA_ARGS__); \
} while(0)

/* NULL 체크 매크로 */
#define CHECK_NULL(ptr) do { \
    if ((ptr) == NULL) { \
        LOG_ERROR(ERR_INVALID_PARAM, "NULL pointer"); \
        return ERR_INVALID_PARAM; \
    } \
} while(0)

/* DB 에러 체크 매크로 - Pro*C용 */
#define CHECK_DB_ERROR(sqlca, action) do { \
    if (sqlca.sqlcode != 0 && sqlca.sqlcode != 1403) { \
        char _errbuf[256]; \
        sprintf(_errbuf, "DB Error [%ld]: %.*s (%s)", sqlca.sqlcode, \
                (int)sqlca.sqlerrm.sqlerrml, sqlca.sqlerrm.sqlerrmc, (action)); \
        LOG_ERROR((int)sqlca.sqlcode, _errbuf); \
        return (int)sqlca.sqlcode; \
    } \
} while(0)

/* 금액 포맷 (3자리 콤마) */
static void format_amount(double amt, char *buf, int buf_len)
{
    char tmp[MAX_AMT_STR];
    int len, i, j;
    int neg = 0;

    if (amt < 0) { neg = 1; amt = -amt; }
    sprintf(tmp, "%.0f", amt);
    len = strlen(tmp);

    j = 0;
    if (neg) buf[j++] = '-';
    for (i = 0; i < len && j < buf_len - 1; i++) {
        if (i > 0 && (len - i) % 3 == 0) buf[j++] = ',';
        buf[j++] = tmp[i];
    }
    buf[j] = '\0';
}

/* 날짜 차이 계산 (일수) - 간이 계산 */
static int date_diff_days(const char *date1, const char *date2)
{
    int y1, m1, d1, y2, m2, d2;
    struct tm t1, t2;
    time_t tt1, tt2;

    if (sscanf(date1, "%d-%d-%d", &y1, &m1, &d1) != 3) return -1;
    if (sscanf(date2, "%d-%d-%d", &y2, &m2, &d2) != 3) return -1;

    memset(&t1, 0, sizeof(t1));
    t1.tm_year = y1 - 1900; t1.tm_mon = m1 - 1; t1.tm_mday = d1;
    memset(&t2, 0, sizeof(t2));
    t2.tm_year = y2 - 1900; t2.tm_mon = m2 - 1; t2.tm_mday = d2;

    tt1 = mktime(&t1);
    tt2 = mktime(&t2);

    return (int)((tt2 - tt1) / 86400);
}

/* 현재 날짜 문자열 반환 */
static void get_current_date(char *buf, int buf_len)
{
    time_t now = time(NULL);
    struct tm *tm_now = localtime(&now);
    snprintf(buf, buf_len, "%04d-%02d-%02d", tm_now->tm_year + 1900, tm_now->tm_mon + 1, tm_now->tm_mday);
}

/* 현재 일시 문자열 반환 */
static void get_current_datetime(char *buf, int buf_len)
{
    time_t now = time(NULL);
    struct tm *tm_now = localtime(&now);
    snprintf(buf, buf_len, "%04d-%02d-%02d %02d:%02d:%02d",
             tm_now->tm_year + 1900, tm_now->tm_mon + 1, tm_now->tm_mday,
             tm_now->tm_hour, tm_now->tm_min, tm_now->tm_sec);
}

#endif /* _COMMON_INS_H_ */
