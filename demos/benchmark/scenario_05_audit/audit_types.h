/*******************************************************************************
 * audit_types.h - 감사 로그 시스템 공통 타입
 *
 * 작성일: 2011-04-15
 * 수정일: 2016-02-20  최과장 - 이벤트 유형 코드 확장
 * 수정일: 2019-10-10  김대리 - XML 내보내기 구조체 추가
 * 수정일: 2022-05-01  박사원 - 보안감사 필드 추가
 *
 * 감사 로그 관련 구조체, 상수, 에러코드
 * C + Pro*C 혼합 시스템에서 사용
 ******************************************************************************/
#ifndef _AUDIT_TYPES_H_
#define _AUDIT_TYPES_H_

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* 시스템 상수 */
#define MAX_AUDIT_SEQ         12
#define MAX_USER_ID           20
#define MAX_USER_NAME         40
#define MAX_IP_ADDR           16
#define MAX_TABLE_NAME        30
#define MAX_COLUMN_NAME       30
#define MAX_OLD_VALUE         500
#define MAX_NEW_VALUE         500
#define MAX_ACTION_DESC       200
#define MAX_DATE_LEN          11
#define MAX_DATETIME_LEN      20
#define MAX_ERR_MSG           256
#define MAX_ARRAY_SIZE        10000
#define MAX_PATH_LEN          256
#define COMMIT_UNIT           500
#define MAX_EXPORT_COLS       50
#define PAGE_SIZE             60
#define CSV_DELIMITER         ','
#define CSV_QUOTE             '"'
#define XML_INDENT            "  "

/* 감사 이벤트 유형 코드 */
#define EVT_LOGIN             "A01"    /* 로그인 */
#define EVT_LOGOUT            "A02"    /* 로그아웃 */
#define EVT_LOGIN_FAIL        "A03"    /* 로그인 실패 */
#define EVT_PASSWORD_CHANGE   "A04"    /* 비밀번호 변경 */
#define EVT_DATA_SELECT       "D01"    /* 데이터 조회 */
#define EVT_DATA_INSERT       "D02"    /* 데이터 등록 */
#define EVT_DATA_UPDATE       "D03"    /* 데이터 수정 */
#define EVT_DATA_DELETE       "D04"    /* 데이터 삭제 */
#define EVT_DATA_EXPORT       "D05"    /* 데이터 내보내기 */
#define EVT_DATA_PRINT        "D06"    /* 데이터 출력 */
#define EVT_ADMIN_GRANT       "S01"    /* 권한 부여 */
#define EVT_ADMIN_REVOKE      "S02"    /* 권한 회수 */
#define EVT_ADMIN_CONFIG      "S03"    /* 시스템 설정 변경 */
#define EVT_BATCH_START       "B01"    /* 배치 시작 */
#define EVT_BATCH_END         "B02"    /* 배치 종료 */
#define EVT_BATCH_ERROR       "B03"    /* 배치 오류 */

/* 2016-02-20 추가 */
#define EVT_PERSONAL_INFO     "P01"    /* 개인정보 조회 */
#define EVT_PERSONAL_DOWNLOAD "P02"    /* 개인정보 다운로드 */
#define EVT_PERSONAL_MASKING  "P03"    /* 마스킹 해제 */

/* 2022-05-01 추가 - 보안감사 */
#define EVT_SECURITY_ALERT    "X01"    /* 보안 경고 */
#define EVT_ABNORMAL_ACCESS   "X02"    /* 비정상 접근 */
#define EVT_PRIVILEGE_ESCALATION "X03" /* 권한 상승 시도 */

/* 이벤트 심각도 */
#define SEV_INFO              'I'      /* 정보 */
#define SEV_WARNING           'W'      /* 경고 */
#define SEV_ERROR             'E'      /* 에러 */
#define SEV_CRITICAL          'C'      /* 위험 */

/* 내보내기 형식 */
#define EXPORT_CSV            1
#define EXPORT_XML            2
#define EXPORT_FIXED          3        /* 고정폭 텍스트 */

/* 에러코드 */
#define AUDIT_SUCCESS         0
#define AUDIT_ERR_DB          -1001
#define AUDIT_ERR_DB_SELECT   -1002
#define AUDIT_ERR_DB_INSERT   -1003
#define AUDIT_ERR_NOT_FOUND   -2001
#define AUDIT_ERR_INVALID     -2002
#define AUDIT_ERR_FILE_OPEN   -3001
#define AUDIT_ERR_FILE_WRITE  -3002
#define AUDIT_ERR_FILE_FORMAT -3003
#define AUDIT_ERR_MEMORY      -4001
#define AUDIT_ERR_OVERFLOW    -4002
#define AUDIT_ERR_PARAM       -5001

/*******************************************************************************
 * 구조체 정의
 ******************************************************************************/

/* 감사 로그 레코드 */
typedef struct _audit_record {
    long    audit_seq;                       /* 감사일련번호 */
    char    event_type[4];                   /* 이벤트유형 */
    char    event_date[MAX_DATE_LEN];        /* 이벤트일자 */
    char    event_time[9];                   /* 이벤트시각 HH:MI:SS */
    char    event_datetime[MAX_DATETIME_LEN]; /* 이벤트일시 */
    char    severity;                         /* 심각도 I/W/E/C */
    char    user_id[MAX_USER_ID];            /* 사용자ID */
    char    user_name[MAX_USER_NAME];        /* 사용자명 */
    char    ip_addr[MAX_IP_ADDR];            /* IP주소 */
    char    table_name[MAX_TABLE_NAME];      /* 대상테이블 */
    char    column_name[MAX_COLUMN_NAME];    /* 변경컬럼 */
    char    old_value[MAX_OLD_VALUE];        /* 변경전값 */
    char    new_value[MAX_NEW_VALUE];        /* 변경후값 */
    char    action_desc[MAX_ACTION_DESC];    /* 행위설명 */
    char    result;                           /* 결과 S:성공 F:실패 */
    char    session_id[30];                  /* 세션ID */
    /* 2022-05-01 추가 */
    char    menu_id[20];                     /* 메뉴ID */
    char    screen_id[20];                   /* 화면ID */
    int     affected_rows;                   /* 영향행수 */
} AUDIT_RECORD;

/* 검색 조건 */
typedef struct _audit_search {
    char    from_date[MAX_DATE_LEN];
    char    to_date[MAX_DATE_LEN];
    char    event_type[4];                   /* 빈값이면 전체 */
    char    user_id[MAX_USER_ID];            /* 빈값이면 전체 */
    char    table_name[MAX_TABLE_NAME];      /* 빈값이면 전체 */
    char    ip_addr[MAX_IP_ADDR];
    char    severity;                         /* 0이면 전체 */
    char    result;                           /* 0이면 전체 */
    int     limit;                            /* 최대 건수 (0이면 무제한) */
} AUDIT_SEARCH;

/* 내보내기 옵션 */
typedef struct _export_option {
    int     format;                          /* CSV/XML/FIXED */
    char    output_path[MAX_PATH_LEN];
    char    encoding[20];                    /* UTF-8, EUC-KR */
    int     include_header;                  /* 헤더 포함 여부 */
    char    columns[MAX_EXPORT_COLS][MAX_COLUMN_NAME]; /* 출력 컬럼 목록 */
    int     column_cnt;
    char    date_format[20];                 /* 날짜 형식 */
} EXPORT_OPTION;

/* 감사 통계 */
typedef struct _audit_stat {
    char    date[MAX_DATE_LEN];
    char    event_type[4];
    int     total_cnt;
    int     success_cnt;
    int     fail_cnt;
    int     info_cnt;
    int     warn_cnt;
    int     error_cnt;
    int     critical_cnt;
    int     unique_users;
    int     unique_ips;
} AUDIT_STAT;

/*******************************************************************************
 * 함수 선언 - audit_main.pc
 ******************************************************************************/
int  audit_insert(const AUDIT_RECORD *record);
int  audit_search(const AUDIT_SEARCH *search, AUDIT_RECORD *records, int *cnt);
int  audit_get_stat(const char *from_date, const char *to_date, AUDIT_STAT *stats, int *cnt);
int  audit_purge(const char *before_date, int *purged_cnt);
int  audit_batch_register(AUDIT_RECORD *records, int cnt);

/*******************************************************************************
 * 함수 선언 - audit_export.c (순수 C)
 ******************************************************************************/
int  audit_export(const EXPORT_OPTION *opt, AUDIT_RECORD *records, int cnt);
int  audit_export_csv(FILE *fp, AUDIT_RECORD *records, int cnt, const EXPORT_OPTION *opt);
int  audit_export_xml(FILE *fp, AUDIT_RECORD *records, int cnt, const EXPORT_OPTION *opt);
int  audit_export_fixed(FILE *fp, AUDIT_RECORD *records, int cnt, const EXPORT_OPTION *opt);
void audit_escape_csv(const char *src, char *dst, int dst_len);
void audit_escape_xml(const char *src, char *dst, int dst_len);

/*******************************************************************************
 * 유틸리티 매크로
 ******************************************************************************/
#define AUD_STRCPY(dst, src, len) do { strncpy((dst), (src), (len)-1); (dst)[(len)-1] = '\0'; } while(0)

#define AUD_LOG(level, fmt, ...) do { \
    time_t _t = time(NULL); struct tm *_tm = localtime(&_t); \
    fprintf(stderr, "[%04d-%02d-%02d %02d:%02d:%02d][%s] " fmt "\n", \
        _tm->tm_year+1900, _tm->tm_mon+1, _tm->tm_mday, \
        _tm->tm_hour, _tm->tm_min, _tm->tm_sec, (level), ##__VA_ARGS__); \
} while(0)

#define AUD_INFO(fmt, ...)  AUD_LOG("INFO", fmt, ##__VA_ARGS__)
#define AUD_ERROR(fmt, ...) AUD_LOG("ERROR", fmt, ##__VA_ARGS__)
#define AUD_WARN(fmt, ...)  AUD_LOG("WARN", fmt, ##__VA_ARGS__)

#define AUD_CHECK_NULL(p) do { if (!(p)) { AUD_ERROR("NULL param at %s:%d", __FILE__, __LINE__); return AUDIT_ERR_PARAM; } } while(0)

/* 이벤트 유형명 반환 */
static const char* audit_event_name(const char *event_type)
{
    if (strcmp(event_type, EVT_LOGIN) == 0) return "로그인";
    if (strcmp(event_type, EVT_LOGOUT) == 0) return "로그아웃";
    if (strcmp(event_type, EVT_LOGIN_FAIL) == 0) return "로그인실패";
    if (strcmp(event_type, EVT_PASSWORD_CHANGE) == 0) return "비밀번호변경";
    if (strcmp(event_type, EVT_DATA_SELECT) == 0) return "데이터조회";
    if (strcmp(event_type, EVT_DATA_INSERT) == 0) return "데이터등록";
    if (strcmp(event_type, EVT_DATA_UPDATE) == 0) return "데이터수정";
    if (strcmp(event_type, EVT_DATA_DELETE) == 0) return "데이터삭제";
    if (strcmp(event_type, EVT_DATA_EXPORT) == 0) return "데이터내보내기";
    if (strcmp(event_type, EVT_DATA_PRINT) == 0) return "데이터출력";
    if (strcmp(event_type, EVT_ADMIN_GRANT) == 0) return "권한부여";
    if (strcmp(event_type, EVT_ADMIN_REVOKE) == 0) return "권한회수";
    if (strcmp(event_type, EVT_ADMIN_CONFIG) == 0) return "시스템설정";
    if (strcmp(event_type, EVT_BATCH_START) == 0) return "배치시작";
    if (strcmp(event_type, EVT_BATCH_END) == 0) return "배치종료";
    if (strcmp(event_type, EVT_BATCH_ERROR) == 0) return "배치오류";
    if (strcmp(event_type, EVT_PERSONAL_INFO) == 0) return "개인정보조회";
    if (strcmp(event_type, EVT_PERSONAL_DOWNLOAD) == 0) return "개인정보다운로드";
    if (strcmp(event_type, EVT_SECURITY_ALERT) == 0) return "보안경고";
    if (strcmp(event_type, EVT_ABNORMAL_ACCESS) == 0) return "비정상접근";
    return "기타";
}

/* 심각도명 반환 */
static const char* audit_severity_name(char severity)
{
    switch (severity) {
        case SEV_INFO:     return "INFO";
        case SEV_WARNING:  return "WARN";
        case SEV_ERROR:    return "ERROR";
        case SEV_CRITICAL: return "CRITICAL";
        default:           return "UNKNOWN";
    }
}

#endif /* _AUDIT_TYPES_H_ */
