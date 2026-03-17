/*******************************************************************************
 * inv_types.h - 재고 관리 공통 타입 정의
 *
 * 작성일: 2010-09-01
 * 수정일: 2014-04-20  최과장 - 창고별 재고 구조체 추가
 * 수정일: 2018-08-15  김대리 - 바코드/LOT 관리 추가
 * 수정일: 2021-12-01  박사원 - 유통기한 관리 필드
 *
 * 순수 C 헤더 (Pro*C 없음)
 * 재고 관리 배치에서 사용하는 구조체, 상수, 매크로
 ******************************************************************************/
#ifndef _INV_TYPES_H_
#define _INV_TYPES_H_

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* 시스템 상수 */
#define MAX_ITEM_CODE         15
#define MAX_ITEM_NAME         60
#define MAX_WH_CODE           8
#define MAX_WH_NAME           40
#define MAX_LOT_NO            20
#define MAX_BARCODE           30
#define MAX_UNIT              5
#define MAX_CATEGORY          10
#define MAX_VENDOR_CODE       10
#define MAX_VENDOR_NAME       50
#define MAX_DATE_LEN          11
#define MAX_LINE_LEN          512
#define MAX_ITEMS             10000
#define MAX_WAREHOUSES        50
#define MAX_TRANSACTIONS      50000
#define MAX_PATH_LEN          256
#define MAX_NOTE              200
#define REPORT_LINE_WIDTH     132

/* 재고 이동 유형 */
#define TXN_IN                "IN"     /* 입고 */
#define TXN_OUT               "OUT"    /* 출고 */
#define TXN_ADJ_PLUS          "A+"     /* 조정증가 */
#define TXN_ADJ_MINUS         "A-"     /* 조정감소 */
#define TXN_TRANSFER          "TR"     /* 이동 (창고간) */
#define TXN_RETURN            "RT"     /* 반품 */
#define TXN_SCRAP             "SC"     /* 폐기 */

/* 2018-08-15 추가 */
#define TXN_LOT_IN            "LI"     /* LOT 입고 */
#define TXN_LOT_OUT           "LO"     /* LOT 출고 */

/* 재고 상태 */
#define INV_NORMAL            'N'      /* 정상 */
#define INV_HOLD              'H'      /* 보류 */
#define INV_INSPECT           'I'      /* 검수중 */
#define INV_DEFECT            'D'      /* 불량 */
#define INV_EXPIRED           'E'      /* 유통기한초과 */

/* 안전재고 기준 (일수) */
#define SAFETY_STOCK_DAYS     7
#define REORDER_POINT_DAYS    14
#define MAX_STOCK_DAYS        90

/* 리포트 유형 */
#define RPT_STOCK_SUMMARY     1        /* 재고 현황 요약 */
#define RPT_STOCK_DETAIL      2        /* 재고 현황 상세 */
#define RPT_TXN_LIST          3        /* 입출고 내역 */
#define RPT_SHORTAGE          4        /* 부족재고 리스트 */
#define RPT_EXCESS            5        /* 과잉재고 리스트 */
#define RPT_AGING             6        /* 재고 장기보유 */
#define RPT_EXPIRY            7        /* 유통기한 임박 */

/* 에러코드 */
#define INV_SUCCESS           0
#define INV_ERR_FILE_OPEN     -1001
#define INV_ERR_FILE_READ     -1002
#define INV_ERR_FILE_WRITE    -1003
#define INV_ERR_FORMAT        -2001
#define INV_ERR_NOT_FOUND     -2002
#define INV_ERR_DUPLICATE     -2003
#define INV_ERR_OVERFLOW      -2004
#define INV_ERR_NEGATIVE_QTY  -3001
#define INV_ERR_EXCEED_MAX    -3002
#define INV_ERR_INVALID_TXN   -3003
#define INV_ERR_MEMORY        -4001
#define INV_ERR_PARAM         -5001

/*******************************************************************************
 * 구조체 정의
 ******************************************************************************/

/* 품목 마스터 */
typedef struct _item_master {
    char    item_code[MAX_ITEM_CODE];
    char    item_name[MAX_ITEM_NAME];
    char    category[MAX_CATEGORY];
    char    unit[MAX_UNIT];              /* EA, BOX, KG, L 등 */
    char    barcode[MAX_BARCODE];
    char    vendor_code[MAX_VENDOR_CODE];
    char    vendor_name[MAX_VENDOR_NAME];
    double  unit_price;                   /* 단가 */
    double  unit_cost;                    /* 원가 */
    int     safety_stock;                 /* 안전재고 수량 */
    int     reorder_point;                /* 재주문점 */
    int     max_stock;                    /* 최대재고 */
    int     lead_time_days;               /* 리드타임 (일) */
    char    expiry_yn;                    /* 유통기한관리여부 Y/N */
    int     shelf_life_days;              /* 유통기한 (일) */
    char    active_yn;                    /* 사용여부 */
} ITEM_MASTER;

/* 창고별 재고 (2014-04-20 추가) */
typedef struct _warehouse_stock {
    char    wh_code[MAX_WH_CODE];
    char    wh_name[MAX_WH_NAME];
    char    item_code[MAX_ITEM_CODE];
    int     qty_on_hand;                  /* 현재고 */
    int     qty_allocated;                /* 할당수량 (출고예정) */
    int     qty_available;                /* 가용수량 = 현재고 - 할당 */
    int     qty_on_order;                 /* 발주수량 (입고예정) */
    char    last_in_date[MAX_DATE_LEN];   /* 최종입고일 */
    char    last_out_date[MAX_DATE_LEN];  /* 최종출고일 */
    double  avg_cost;                     /* 이동평균원가 */
    double  total_value;                  /* 재고금액 */
    char    status;                        /* 상태 */
} WAREHOUSE_STOCK;

/* 입출고 트랜잭션 */
typedef struct _inv_transaction {
    int     txn_seq;                       /* 거래순번 */
    char    txn_date[MAX_DATE_LEN];        /* 거래일자 */
    char    txn_type[3];                   /* 거래유형 */
    char    item_code[MAX_ITEM_CODE];
    char    wh_code[MAX_WH_CODE];
    char    to_wh_code[MAX_WH_CODE];       /* 이동 대상 창고 (TR시) */
    int     qty;                           /* 수량 */
    double  unit_price;                    /* 단가 */
    double  amount;                        /* 금액 */
    char    lot_no[MAX_LOT_NO];            /* LOT번호 */
    char    expiry_date[MAX_DATE_LEN];     /* 유통기한 */
    char    note[MAX_NOTE];
} INV_TRANSACTION;

/* 재고 집계 */
typedef struct _stock_summary {
    char    item_code[MAX_ITEM_CODE];
    char    item_name[MAX_ITEM_NAME];
    char    category[MAX_CATEGORY];
    int     total_on_hand;                 /* 전체 현재고 */
    int     total_allocated;
    int     total_available;
    int     total_on_order;
    int     safety_stock;
    int     reorder_point;
    double  total_value;                   /* 총 재고금액 */
    double  avg_unit_cost;                 /* 평균 단가 */
    int     stock_days;                    /* 재고일수 (현재고/일평균출고) */
    char    status_flag;                   /* S:부족 O:과잉 N:정상 */
    int     wh_count;                      /* 보관 창고수 */
    WAREHOUSE_STOCK wh_stocks[MAX_WAREHOUSES]; /* 창고별 내역 */
} STOCK_SUMMARY;

/* 배치 처리 결과 */
typedef struct _batch_stat {
    int     total_lines;
    int     processed;
    int     errors;
    int     skipped;
    double  total_in_amount;
    double  total_out_amount;
    char    start_time[20];
    char    end_time[20];
} BATCH_STAT;

/* 리포트 옵션 */
typedef struct _report_option {
    int     report_type;
    char    from_date[MAX_DATE_LEN];
    char    to_date[MAX_DATE_LEN];
    char    wh_code[MAX_WH_CODE];          /* 빈값이면 전체 */
    char    category[MAX_CATEGORY];        /* 빈값이면 전체 */
    char    item_code[MAX_ITEM_CODE];      /* 빈값이면 전체 */
    int     show_zero_stock;               /* 0재고 표시 여부 */
    int     page_size;                     /* 페이지당 줄수 */
    char    output_path[MAX_PATH_LEN];
} REPORT_OPTION;

/*******************************************************************************
 * 함수 선언 - inv_batch.c
 ******************************************************************************/
int  inv_load_items(const char *filepath, ITEM_MASTER *items, int *cnt);
int  inv_load_transactions(const char *filepath, INV_TRANSACTION *txns, int *cnt);
int  inv_process_transactions(INV_TRANSACTION *txns, int txn_cnt,
                              WAREHOUSE_STOCK *stocks, int *stock_cnt,
                              BATCH_STAT *stat);
int  inv_calc_summary(WAREHOUSE_STOCK *stocks, int stock_cnt,
                      ITEM_MASTER *items, int item_cnt,
                      STOCK_SUMMARY *summaries, int *summary_cnt);
int  inv_save_results(const char *filepath, WAREHOUSE_STOCK *stocks, int stock_cnt);
void inv_sort_by_item(WAREHOUSE_STOCK *stocks, int cnt);

/*******************************************************************************
 * 함수 선언 - inv_report.c
 ******************************************************************************/
int  inv_generate_report(const REPORT_OPTION *opt,
                         STOCK_SUMMARY *summaries, int summary_cnt,
                         INV_TRANSACTION *txns, int txn_cnt);
int  inv_report_stock_summary(FILE *fp, STOCK_SUMMARY *summaries, int cnt, const REPORT_OPTION *opt);
int  inv_report_stock_detail(FILE *fp, STOCK_SUMMARY *summaries, int cnt, const REPORT_OPTION *opt);
int  inv_report_txn_list(FILE *fp, INV_TRANSACTION *txns, int cnt, const REPORT_OPTION *opt);
int  inv_report_shortage(FILE *fp, STOCK_SUMMARY *summaries, int cnt);
int  inv_report_excess(FILE *fp, STOCK_SUMMARY *summaries, int cnt);

/*******************************************************************************
 * 유틸리티 매크로
 ******************************************************************************/
#define INV_STRCPY(dst, src, len) do { strncpy((dst), (src), (len)-1); (dst)[(len)-1] = '\0'; } while(0)

#define INV_LOG(level, fmt, ...) do { \
    time_t _t = time(NULL); struct tm *_tm = localtime(&_t); \
    fprintf(stderr, "[%04d-%02d-%02d %02d:%02d:%02d][%s] " fmt "\n", \
        _tm->tm_year+1900, _tm->tm_mon+1, _tm->tm_mday, \
        _tm->tm_hour, _tm->tm_min, _tm->tm_sec, (level), ##__VA_ARGS__); \
} while(0)

#define INV_INFO(fmt, ...)  INV_LOG("INFO", fmt, ##__VA_ARGS__)
#define INV_ERROR(fmt, ...) INV_LOG("ERROR", fmt, ##__VA_ARGS__)
#define INV_WARN(fmt, ...)  INV_LOG("WARN", fmt, ##__VA_ARGS__)

/* 날짜 비교 (문자열 YYYY-MM-DD) */
#define DATE_CMP(d1, d2) strcmp((d1), (d2))

#endif /* _INV_TYPES_H_ */
