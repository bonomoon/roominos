/* ============================================= */
/* 파일명 : common_def.h                          */
/* 설  명 : 공통 매크로/구조체/상수 정의           */
/* 작성자 : 홍길동                                */
/* 작성일 : 2008.03.15                            */
/* 수정이력 :                                     */
/*   2009.01.10 이과장 - 에러코드 추가            */
/*   2011.07.22 박사원 - 로깅 매크로 변경         */
/*   2014.03.05 김대리 - 구조체 필드 추가         */
/*   2016.09.30 최주임 - 플랫폼 분기 수정         */
/*   2019.11.15 정대리 - 배치사이즈 상수 추가     */
/* ============================================= */
#ifndef _COMMON_DEF_H_
#define _COMMON_DEF_H_

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

/* ============================================= */
/* 시스템 상수 정의                               */
/* ============================================= */
#define MAX_ACCT_LEN        20
#define MAX_NAME_LEN        100
#define MAX_BR_CD_LEN       4
#define MAX_MSG_LEN         1024
#define MAX_SQL_LEN         4096
#define MAX_PATH_LEN        256
#define MAX_LINE_LEN        2048
#define MAX_ERR_MSG         512
#define COMMIT_UNIT         100
#define MAX_RETRY           3
#define DB_FETCH_SIZE       100

/* 20190115 정대리 - 배치 처리 단위 */
#define BATCH_SIZE_SMALL    500
#define BATCH_SIZE_MEDIUM   5000
#define BATCH_SIZE_LARGE    50000

/* 2016.09.30 최주임 - 이건 더이상 안쓰는데 혹시 몰라서 남겨둠 */
#ifdef _HP_UX_
#define ALIGN_SIZE  8
#define PTR_SIZE    4
#elif defined(_AIX_)
#define ALIGN_SIZE  8
#define PTR_SIZE    4
#elif defined(_LINUX_)
#define ALIGN_SIZE  4
#define PTR_SIZE    4
#else
#define ALIGN_SIZE  4
#define PTR_SIZE    4
#endif

/* 옛날에 쓰던거 - 건들지 말것 */
/* #define OLD_COMMIT_UNIT  50 */
/* #define USE_PARALLEL     0  */
/* #define LEGACY_MODE      1  */ /* 2012.06 이과장 - 레거시 모드 제거 */

/* ============================================= */
/* 에러코드 정의                                  */
/* ============================================= */
#define ERR_SUCCESS          0
#define ERR_GENERAL         -1
#define ERR_DB_CONNECT      -100
#define ERR_DB_DISCONNECT   -101
#define ERR_DB_EXECUTE      -102
#define ERR_DB_FETCH        -103
#define ERR_DB_COMMIT       -104
#define ERR_DB_ROLLBACK     -105
#define ERR_DB_CURSOR_OPEN  -106
#define ERR_DB_CURSOR_CLOSE -107
#define ERR_DB_DEADLOCK     -108
#define ERR_DB_TIMEOUT      -109
#define ERR_DB_DUP_KEY      -110
#define ERR_DB_NOT_FOUND    -111
#define ERR_DB_TOO_MANY     -112

#define ERR_FILE_OPEN       -200
#define ERR_FILE_READ       -201
#define ERR_FILE_WRITE      -202
#define ERR_FILE_CLOSE      -203
#define ERR_FILE_NOT_FOUND  -204
#define ERR_FILE_PERM       -205

#define ERR_PARAM_INVALID   -300
#define ERR_PARAM_MISSING   -301
#define ERR_PARAM_RANGE     -302
#define ERR_PARAM_FORMAT    -303
#define ERR_PARAM_DATE      -304

#define ERR_CALC_OVERFLOW   -400
#define ERR_CALC_UNDERFLOW  -401
#define ERR_CALC_DIVZERO    -402
#define ERR_CALC_RATE       -403
#define ERR_CALC_PERIOD     -404

#define ERR_ACCT_NOT_FOUND  -500
#define ERR_ACCT_DORMANT    -501
#define ERR_ACCT_CLOSED     -502
#define ERR_ACCT_SUSPENDED  -503
#define ERR_ACCT_LOCKED     -504
#define ERR_ACCT_LIMIT      -505
#define ERR_ACCT_TYPE       -506

#define ERR_SETTLE_DUP      -600
#define ERR_SETTLE_AMT      -601
#define ERR_SETTLE_STAT     -602
#define ERR_SETTLE_DATE     -603
#define ERR_SETTLE_LOCK     -604

#define ERR_MEM_ALLOC       -700
#define ERR_MEM_FREE        -701

/* 20130515 김대리 추가 - 수수료 관련 에러 */
#define ERR_FEE_CALC        -800
#define ERR_FEE_TYPE        -801
#define ERR_FEE_RATE        -802
#define ERR_FEE_EXEMPT      -803

/* 20200210 최주임 추가 - 코로나 감면 */
#define ERR_COVID_EXEMPT    -900
#define ERR_COVID_PERIOD    -901
#define ERR_COVID_RATE      -902

/* ============================================= */
/* 계좌 상태 코드 (매직넘버 정의... 라고 하지만    */
/* 실제로는 코드에서 숫자를 직접 쓰는 경우가 더 많음) */
/* ============================================= */
#define ACCT_STAT_NORMAL    1   /* 정상 */
#define ACCT_STAT_SUSPEND   2   /* 정지 */
#define ACCT_STAT_DORMANT   3   /* 휴면 */
#define ACCT_STAT_FROZEN    4   /* 동결 */
#define ACCT_STAT_CLOSED    9   /* 해지 */

/* 정산 유형 코드 */
#define SETTLE_TYPE_INT     "01"  /* 이자정산 */
#define SETTLE_TYPE_FEE     "02"  /* 수수료정산 */
#define SETTLE_TYPE_TAX     "03"  /* 세금정산 */
#define SETTLE_TYPE_PENALTY "04"  /* 위약금정산 */
/* #define SETTLE_TYPE_BONUS "05" */  /* 2017년에 추가하려다 말았음 */

/* ============================================= */
/* 구조체 정의                                    */
/* ============================================= */

/* 계좌 정보 구조체 */
typedef struct _acct_info {
    char    acct_no[MAX_ACCT_LEN + 1];
    char    acct_nm[MAX_NAME_LEN + 1];
    char    br_cd[MAX_BR_CD_LEN + 1];
    int     acct_stat;
    int     acct_type;
    double  bal_amt;
    double  avail_amt;
    double  hold_amt;       /* 2014.03.05 김대리 추가 */
    char    open_dt[9];
    char    close_dt[9];
    char    last_txn_dt[9];
    int     cust_grade;     /* 고객등급 1~5 */
    int     fee_exempt_yn;  /* 수수료면제여부 0/1 */
    /* 2018.09.21 박과장 추가 */
    int     new_acct_type;  /* 신규계좌유형 - acct_type 이랑 뭐가 다른지 모르겠음 */
    char    product_cd[11]; /* 상품코드 */
} ACCT_INFO;

/* 정산 결과 구조체 */
typedef struct _settle_result {
    char    acct_no[MAX_ACCT_LEN + 1];
    char    settle_dt[9];
    char    settle_type[3];
    double  settle_amt;
    double  int_amt;
    double  fee_amt;
    double  tax_amt;
    int     result_cd;
    char    err_msg[MAX_ERR_MSG];
} SETTLE_RESULT;

/* 배치 파라미터 구조체 - 근데 이거 main에서 안쓰고 전역변수 씀 */
typedef struct {
    char    batch_dt[9];
    char    br_cd[5];
    char    job_type[3];     /* 01:전체, 02:영업점별, 03:재처리 */
    int     commit_unit;
    int     debug_mode;
    char    log_path[MAX_PATH_LEN];
} BATCH_PARAM;

/* 일별 집계용 - RPT_DAILY에서 사용 */
typedef struct {
    char    rpt_dt[9];
    char    br_cd[5];
    char    br_nm[51];
    int     total_cnt;
    int     succ_cnt;
    int     fail_cnt;
    double  total_settle_amt;
    double  total_int_amt;
    double  total_fee_amt;
    double  total_tax_amt;
    /* 2022.08.15 정대리 추가 */
    double  limit_over_amt;
    int     limit_over_cnt;
} DAILY_SUMMARY;

/* ============================================= */
/* 로깅 매크로                                    */
/* 2011.07.22 박사원 - 타임스탬프 추가            */
/* ============================================= */
#define LOG_MSG(fp, fmt, ...) \
    do { \
        time_t _t = time(NULL); \
        struct tm *_tm = localtime(&_t); \
        if(fp != NULL) { \
            fprintf(fp, "[%04d%02d%02d %02d:%02d:%02d] " fmt "\n", \
                _tm->tm_year+1900, _tm->tm_mon+1, _tm->tm_mday, \
                _tm->tm_hour, _tm->tm_min, _tm->tm_sec, \
                ##__VA_ARGS__); \
            fflush(fp); \
        } \
    } while(0)

/* 에러 로그 - LOG_MSG랑 거의 같은데 ERR 태그 붙음 */
#define LOG_ERR(fp, fmt, ...) \
    do { \
        time_t _t = time(NULL); \
        struct tm *_tm = localtime(&_t); \
        if(fp != NULL) { \
            fprintf(fp, "[%04d%02d%02d %02d:%02d:%02d][ERR] " fmt "\n", \
                _tm->tm_year+1900, _tm->tm_mon+1, _tm->tm_mday, \
                _tm->tm_hour, _tm->tm_min, _tm->tm_sec, \
                ##__VA_ARGS__); \
            fflush(fp); \
        } \
    } while(0)

/* 디버그 로그 - 운영에서는 안찍히는데 가끔 DEBUG_MODE 켜서 확인용 */
#define LOG_DBG(fp, flag, fmt, ...) \
    do { \
        if(flag) { \
            time_t _t = time(NULL); \
            struct tm *_tm = localtime(&_t); \
            if(fp != NULL) { \
                fprintf(fp, "[%04d%02d%02d %02d:%02d:%02d][DBG] " fmt "\n", \
                    _tm->tm_year+1900, _tm->tm_mon+1, _tm->tm_mday, \
                    _tm->tm_hour, _tm->tm_min, _tm->tm_sec, \
                    ##__VA_ARGS__); \
                fflush(fp); \
            } \
        } \
    } while(0)

/* ============================================= */
/* 유틸 매크로                                    */
/* ============================================= */

/* 날짜 유효성 체크 - 대충 체크함 */
#define IS_VALID_DATE(dt) \
    (strlen(dt) == 8 && \
     dt[0] >= '1' && dt[0] <= '2' && \
     dt[4] >= '0' && dt[4] <= '1' && \
     dt[6] >= '0' && dt[6] <= '3')

/* 문자열 트림 - 오른쪽만 */
#define RTRIM(s) \
    do { \
        int _i = strlen(s) - 1; \
        while(_i >= 0 && (s[_i] == ' ' || s[_i] == '\t')) { \
            s[_i] = '\0'; \
            _i--; \
        } \
    } while(0)

/* 문자열 복사 - strncpy 쓰면 null 안붙어서 만든 매크로 */
#define SAFE_STRCPY(dst, src, len) \
    do { \
        strncpy(dst, src, len); \
        dst[len] = '\0'; \
    } while(0)

/* NULL 체크 */
#define CHK_NULL(ptr) ((ptr) == NULL ? "" : (ptr))

/* 절대값 */
#define ABS_VAL(x) ((x) < 0 ? -(x) : (x))

/* 소수점 반올림 (원단위) */
#define ROUND_WON(x) ((double)((long long)((x) + 0.5)))

/* DB 에러 체크 매크로 - 이거 좀 위험한데 다들 쓰고 있어서 못 바꿈 */
#define CHK_SQL_ERR(label) \
    if(sqlca.sqlcode != 0 && sqlca.sqlcode != 1403) { \
        sprintf(g_err_msg, "SQL ERROR [%d]: %.70s", sqlca.sqlcode, sqlca.sqlerrm.sqlerrmc); \
        goto label; \
    }

/* 2016년에 만들었는데 아무도 안씀 */
#define SAFE_FREE(ptr) \
    do { \
        if(ptr != NULL) { \
            free(ptr); \
            ptr = NULL; \
        } \
    } while(0)

/* ============================================= */
/* 전역 변수 (extern)                             */
/* 각 .pc 파일에서 실제 선언함                     */
/* ============================================= */
/* 이거 extern 으로 해야하는데 실제로는 각 파일에서 */
/* 그냥 새로 선언해서 쓰고 있음... 나중에 정리 필요 */

/* 에러 메시지 버퍼 - 여러 파일에서 공유 */
/* char g_err_msg[MAX_ERR_MSG]; */  /* 주석 풀면 multiple definition 남 */

/* ============================================= */
/* 함수 프로토타입 - 쓰는 파일도 있고 안쓰는 파일도 있음 */
/* ============================================= */
/* int db_connect(char *uid, char *pwd); */   /* SETTLE_BAT에서 인라인으로 함 */
/* int db_disconnect(void); */
/* void write_log(FILE *fp, char *msg); */    /* LOG_MSG 매크로로 대체 */
/* int validate_date(char *dt); */            /* IS_VALID_DATE 매크로로 대체했는데 더 부실함 */

#endif /* _COMMON_DEF_H_ */
