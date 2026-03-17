/*******************************************************************************
 * inv_batch.c - 재고 관리 배치 처리
 *
 * 작성일: 2010-09-01
 * 수정일: 2014-04-20  최과장 - 창고별 분리 재고 관리
 * 수정일: 2018-08-15  김대리 - LOT/바코드 입출고 처리
 * 수정일: 2021-12-01  박사원 - 이동평균원가 계산
 *
 * 순수 C - 파일 기반 재고 처리 (DB 없음)
 * 입력 파일(CSV) -> 재고 계산 -> 결과 파일 출력
 ******************************************************************************/

#include "inv_types.h"

/* 전역 데이터 저장소 */
static ITEM_MASTER      g_items[MAX_ITEMS];
static int              g_item_cnt = 0;
static WAREHOUSE_STOCK  g_stocks[MAX_ITEMS * MAX_WAREHOUSES];
static int              g_stock_cnt = 0;
static INV_TRANSACTION  g_txns[MAX_TRANSACTIONS];
static int              g_txn_cnt = 0;

/* 2018-08-15 사용안함 - 예전 단일창고 재고 배열 */
/* static int g_old_stock[MAX_ITEMS]; */

/*******************************************************************************
 * trim_string - 문자열 앞뒤 공백 제거
 ******************************************************************************/
static char *trim_string(char *str)
{
    char *end;

    if (str == NULL) return NULL;

    while (*str == ' ' || *str == '\t') str++;
    if (*str == '\0') return str;

    end = str + strlen(str) - 1;
    while (end > str && (*end == ' ' || *end == '\t' || *end == '\n' || *end == '\r')) end--;
    *(end + 1) = '\0';

    return str;
}

/*******************************************************************************
 * find_item - 품목코드로 검색 (선형검색)
 ******************************************************************************/
static ITEM_MASTER *find_item(const char *item_code)
{
    int i;
    for (i = 0; i < g_item_cnt; i++) {
        if (strcmp(g_items[i].item_code, item_code) == 0) {
            return &g_items[i];
        }
    }
    return NULL;
}

/*******************************************************************************
 * find_stock - 품목+창고로 재고 검색
 ******************************************************************************/
static WAREHOUSE_STOCK *find_stock(const char *item_code, const char *wh_code)
{
    int i;
    for (i = 0; i < g_stock_cnt; i++) {
        if (strcmp(g_stocks[i].item_code, item_code) == 0 &&
            strcmp(g_stocks[i].wh_code, wh_code) == 0) {
            return &g_stocks[i];
        }
    }
    return NULL;
}

/*******************************************************************************
 * add_stock - 재고 레코드 추가 (없으면 신규 생성)
 ******************************************************************************/
static WAREHOUSE_STOCK *add_stock(const char *item_code, const char *wh_code)
{
    WAREHOUSE_STOCK *stock;

    stock = find_stock(item_code, wh_code);
    if (stock != NULL) return stock;

    if (g_stock_cnt >= MAX_ITEMS * MAX_WAREHOUSES) {
        INV_ERROR("Stock array overflow: cnt=%d", g_stock_cnt);
        return NULL;
    }

    stock = &g_stocks[g_stock_cnt];
    memset(stock, 0, sizeof(WAREHOUSE_STOCK));
    INV_STRCPY(stock->item_code, item_code, sizeof(stock->item_code));
    INV_STRCPY(stock->wh_code, wh_code, sizeof(stock->wh_code));
    stock->status = INV_NORMAL;
    g_stock_cnt++;

    return stock;
}

/*******************************************************************************
 * inv_load_items - 품목 마스터 파일 로드
 *
 * CSV 형식:
 * item_code,item_name,category,unit,vendor_code,vendor_name,unit_price,unit_cost,
 * safety_stock,reorder_point,max_stock,lead_time,expiry_yn,shelf_life,active_yn
 ******************************************************************************/
int inv_load_items(const char *filepath, ITEM_MASTER *items, int *cnt)
{
    FILE *fp;
    char line[MAX_LINE_LEN];
    int line_no = 0;
    int loaded = 0;
    char *token;
    char *saveptr;

    if (filepath == NULL || items == NULL || cnt == NULL) {
        return INV_ERR_PARAM;
    }

    fp = fopen(filepath, "r");
    if (fp == NULL) {
        INV_ERROR("Cannot open item master file: %s", filepath);
        return INV_ERR_FILE_OPEN;
    }

    /* 헤더 스킵 */
    if (fgets(line, sizeof(line), fp) == NULL) {
        fclose(fp);
        return INV_ERR_FILE_READ;
    }

    while (fgets(line, sizeof(line), fp) != NULL && loaded < MAX_ITEMS) {
        line_no++;
        ITEM_MASTER *item = &items[loaded];
        memset(item, 0, sizeof(ITEM_MASTER));

        /* CSV 파싱 - strtok_r 사용 */
        token = strtok_r(line, ",", &saveptr);
        if (token == NULL) { INV_WARN("Skip line %d: empty", line_no); continue; }
        INV_STRCPY(item->item_code, trim_string(token), sizeof(item->item_code));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(item->item_name, trim_string(token), sizeof(item->item_name));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(item->category, trim_string(token), sizeof(item->category));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(item->unit, trim_string(token), sizeof(item->unit));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(item->vendor_code, trim_string(token), sizeof(item->vendor_code));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(item->vendor_name, trim_string(token), sizeof(item->vendor_name));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->unit_price = atof(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->unit_cost = atof(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->safety_stock = atoi(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->reorder_point = atoi(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->max_stock = atoi(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->lead_time_days = atoi(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->expiry_yn = trim_string(token)[0];

        token = strtok_r(NULL, ",", &saveptr);
        if (token) item->shelf_life_days = atoi(trim_string(token));

        token = strtok_r(NULL, ",\n", &saveptr);
        if (token) item->active_yn = trim_string(token)[0];
        else item->active_yn = 'Y';

        loaded++;
    }

    fclose(fp);
    *cnt = loaded;

    /* 전역에도 복사 */
    if (items == g_items) {
        g_item_cnt = loaded;
    } else {
        memcpy(g_items, items, sizeof(ITEM_MASTER) * loaded);
        g_item_cnt = loaded;
    }

    INV_INFO("Loaded %d items from %s", loaded, filepath);
    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_load_transactions - 입출고 트랜잭션 파일 로드
 *
 * CSV 형식:
 * seq,date,type,item_code,wh_code,to_wh_code,qty,unit_price,lot_no,expiry_date,note
 ******************************************************************************/
int inv_load_transactions(const char *filepath, INV_TRANSACTION *txns, int *cnt)
{
    FILE *fp;
    char line[MAX_LINE_LEN];
    int line_no = 0;
    int loaded = 0;
    char *token, *saveptr;

    if (filepath == NULL || txns == NULL || cnt == NULL) return INV_ERR_PARAM;

    fp = fopen(filepath, "r");
    if (fp == NULL) {
        INV_ERROR("Cannot open transaction file: %s", filepath);
        return INV_ERR_FILE_OPEN;
    }

    /* 헤더 스킵 */
    fgets(line, sizeof(line), fp);

    while (fgets(line, sizeof(line), fp) != NULL && loaded < MAX_TRANSACTIONS) {
        line_no++;
        INV_TRANSACTION *txn = &txns[loaded];
        memset(txn, 0, sizeof(INV_TRANSACTION));

        token = strtok_r(line, ",", &saveptr);
        if (!token) continue;
        txn->txn_seq = atoi(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(txn->txn_date, trim_string(token), sizeof(txn->txn_date));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(txn->txn_type, trim_string(token), sizeof(txn->txn_type));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(txn->item_code, trim_string(token), sizeof(txn->item_code));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(txn->wh_code, trim_string(token), sizeof(txn->wh_code));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(txn->to_wh_code, trim_string(token), sizeof(txn->to_wh_code));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) txn->qty = atoi(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) txn->unit_price = atof(trim_string(token));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(txn->lot_no, trim_string(token), sizeof(txn->lot_no));

        token = strtok_r(NULL, ",", &saveptr);
        if (token) INV_STRCPY(txn->expiry_date, trim_string(token), sizeof(txn->expiry_date));

        token = strtok_r(NULL, ",\n", &saveptr);
        if (token) INV_STRCPY(txn->note, trim_string(token), sizeof(txn->note));

        txn->amount = txn->qty * txn->unit_price;
        loaded++;
    }

    fclose(fp);
    *cnt = loaded;
    INV_INFO("Loaded %d transactions from %s", loaded, filepath);
    return INV_SUCCESS;
}

/*******************************************************************************
 * process_single_txn - 단건 트랜잭션 처리
 *
 * 입고: 현재고 증가, 이동평균원가 재계산
 * 출고: 현재고 감소, 가용수량 체크
 * 이동: 출발창고 감소, 도착창고 증가
 * 조정: 직접 증감
 * 반품: 입고와 동일 처리
 * 폐기: 출고와 동일 처리
 ******************************************************************************/
static int process_single_txn(INV_TRANSACTION *txn, BATCH_STAT *stat)
{
    WAREHOUSE_STOCK *stock;
    WAREHOUSE_STOCK *to_stock;
    ITEM_MASTER *item;

    /* 품목 존재 확인 */
    item = find_item(txn->item_code);
    if (item == NULL) {
        INV_WARN("Item not found: %s (txn_seq=%d)", txn->item_code, txn->txn_seq);
        stat->skipped++;
        return INV_ERR_NOT_FOUND;
    }

    if (strcmp(txn->txn_type, TXN_IN) == 0 ||
        strcmp(txn->txn_type, TXN_LOT_IN) == 0 ||
        strcmp(txn->txn_type, TXN_RETURN) == 0) {
        /* === 입고 / 반품 === */
        stock = add_stock(txn->item_code, txn->wh_code);
        if (stock == NULL) return INV_ERR_OVERFLOW;

        /* 이동평균원가 재계산 (2021-12-01) */
        if (txn->unit_price > 0 && txn->qty > 0) {
            double old_value = stock->avg_cost * stock->qty_on_hand;
            double new_value = txn->unit_price * txn->qty;
            int new_total = stock->qty_on_hand + txn->qty;
            if (new_total > 0) {
                stock->avg_cost = (old_value + new_value) / new_total;
            }
        }

        stock->qty_on_hand += txn->qty;
        stock->qty_available = stock->qty_on_hand - stock->qty_allocated;
        stock->total_value = stock->avg_cost * stock->qty_on_hand;
        INV_STRCPY(stock->last_in_date, txn->txn_date, sizeof(stock->last_in_date));

        stat->total_in_amount += txn->amount;

        /* 최대재고 초과 경고 */
        if (item->max_stock > 0 && stock->qty_on_hand > item->max_stock) {
            INV_WARN("Exceed max stock: %s wh=%s qty=%d max=%d", txn->item_code, txn->wh_code, stock->qty_on_hand, item->max_stock);
        }

    } else if (strcmp(txn->txn_type, TXN_OUT) == 0 ||
               strcmp(txn->txn_type, TXN_LOT_OUT) == 0 ||
               strcmp(txn->txn_type, TXN_SCRAP) == 0) {
        /* === 출고 / 폐기 === */
        stock = find_stock(txn->item_code, txn->wh_code);
        if (stock == NULL) {
            INV_ERROR("No stock record: %s wh=%s (txn_seq=%d)", txn->item_code, txn->wh_code, txn->txn_seq);
            stat->errors++;
            return INV_ERR_NOT_FOUND;
        }

        /* 가용수량 체크 */
        if (stock->qty_available < txn->qty) {
            INV_WARN("Insufficient stock: %s wh=%s avail=%d req=%d (txn_seq=%d)", txn->item_code, txn->wh_code, stock->qty_available, txn->qty, txn->txn_seq);
            /* 음수재고 허용 (경고만) */
        }

        stock->qty_on_hand -= txn->qty;
        stock->qty_available = stock->qty_on_hand - stock->qty_allocated;
        stock->total_value = stock->avg_cost * stock->qty_on_hand;
        INV_STRCPY(stock->last_out_date, txn->txn_date, sizeof(stock->last_out_date));

        stat->total_out_amount += txn->amount;

    } else if (strcmp(txn->txn_type, TXN_TRANSFER) == 0) {
        /* === 창고간 이동 === */
        stock = find_stock(txn->item_code, txn->wh_code);
        if (stock == NULL) {
            stat->errors++;
            return INV_ERR_NOT_FOUND;
        }

        to_stock = add_stock(txn->item_code, txn->to_wh_code);
        if (to_stock == NULL) return INV_ERR_OVERFLOW;

        /* 출발창고 감소 */
        stock->qty_on_hand -= txn->qty;
        stock->qty_available = stock->qty_on_hand - stock->qty_allocated;
        stock->total_value = stock->avg_cost * stock->qty_on_hand;

        /* 도착창고 증가 (원가 이전) */
        if (to_stock->qty_on_hand + txn->qty > 0) {
            to_stock->avg_cost = (to_stock->avg_cost * to_stock->qty_on_hand + stock->avg_cost * txn->qty) / (to_stock->qty_on_hand + txn->qty);
        }
        to_stock->qty_on_hand += txn->qty;
        to_stock->qty_available = to_stock->qty_on_hand - to_stock->qty_allocated;
        to_stock->total_value = to_stock->avg_cost * to_stock->qty_on_hand;

    } else if (strcmp(txn->txn_type, TXN_ADJ_PLUS) == 0) {
        /* === 조정 증가 === */
        stock = add_stock(txn->item_code, txn->wh_code);
        if (stock == NULL) return INV_ERR_OVERFLOW;

        stock->qty_on_hand += txn->qty;
        stock->qty_available = stock->qty_on_hand - stock->qty_allocated;
        stock->total_value = stock->avg_cost * stock->qty_on_hand;

    } else if (strcmp(txn->txn_type, TXN_ADJ_MINUS) == 0) {
        /* === 조정 감소 === */
        stock = find_stock(txn->item_code, txn->wh_code);
        if (stock == NULL) { stat->errors++; return INV_ERR_NOT_FOUND; }

        stock->qty_on_hand -= txn->qty;
        stock->qty_available = stock->qty_on_hand - stock->qty_allocated;
        stock->total_value = stock->avg_cost * stock->qty_on_hand;

    } else {
        INV_WARN("Unknown txn type: %s (txn_seq=%d)", txn->txn_type, txn->txn_seq);
        stat->skipped++;
        return INV_ERR_INVALID_TXN;
    }

    stat->processed++;
    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_process_transactions - 전체 트랜잭션 배치 처리
 ******************************************************************************/
int inv_process_transactions(INV_TRANSACTION *txns, int txn_cnt,
                             WAREHOUSE_STOCK *stocks, int *stock_cnt,
                             BATCH_STAT *stat)
{
    int i, rc;

    if (txns == NULL || stocks == NULL || stock_cnt == NULL || stat == NULL) {
        return INV_ERR_PARAM;
    }

    memset(stat, 0, sizeof(BATCH_STAT));
    stat->total_lines = txn_cnt;

    INV_INFO("=== Processing %d transactions ===", txn_cnt);

    for (i = 0; i < txn_cnt; i++) {
        rc = process_single_txn(&txns[i], stat);
        /* 개별 건 실패시 계속 진행 */
        if (rc != INV_SUCCESS && rc != INV_ERR_NOT_FOUND) {
            /* 심각한 에러만 로깅 */
            if (rc == INV_ERR_OVERFLOW) {
                INV_ERROR("Stock overflow at txn_seq=%d, aborting", txns[i].txn_seq);
                break;
            }
        }
    }

    /* 결과를 출력 배열에 복사 */
    memcpy(stocks, g_stocks, sizeof(WAREHOUSE_STOCK) * g_stock_cnt);
    *stock_cnt = g_stock_cnt;

    INV_INFO("=== Batch complete: processed=%d errors=%d skipped=%d ===", stat->processed, stat->errors, stat->skipped);
    INV_INFO("Total IN amount: %.0f, OUT amount: %.0f", stat->total_in_amount, stat->total_out_amount);

    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_sort_by_item - 품목코드 순 정렬 (버블정렬)
 ******************************************************************************/
void inv_sort_by_item(WAREHOUSE_STOCK *stocks, int cnt)
{
    int i, j;
    WAREHOUSE_STOCK tmp;

    for (i = 0; i < cnt - 1; i++) {
        for (j = 0; j < cnt - i - 1; j++) {
            int cmp = strcmp(stocks[j].item_code, stocks[j + 1].item_code);
            if (cmp > 0 || (cmp == 0 && strcmp(stocks[j].wh_code, stocks[j + 1].wh_code) > 0)) {
                memcpy(&tmp, &stocks[j], sizeof(WAREHOUSE_STOCK));
                memcpy(&stocks[j], &stocks[j + 1], sizeof(WAREHOUSE_STOCK));
                memcpy(&stocks[j + 1], &tmp, sizeof(WAREHOUSE_STOCK));
            }
        }
    }
}

/*******************************************************************************
 * inv_calc_summary - 품목별 재고 집계
 ******************************************************************************/
int inv_calc_summary(WAREHOUSE_STOCK *stocks, int stock_cnt,
                     ITEM_MASTER *items, int item_cnt,
                     STOCK_SUMMARY *summaries, int *summary_cnt)
{
    int i, j, sidx = 0;
    char prev_item[MAX_ITEM_CODE] = "";

    if (!stocks || !items || !summaries || !summary_cnt) return INV_ERR_PARAM;

    inv_sort_by_item(stocks, stock_cnt);

    for (i = 0; i < stock_cnt; i++) {
        STOCK_SUMMARY *sum;

        /* 새로운 품목이면 집계 레코드 생성 */
        if (strcmp(stocks[i].item_code, prev_item) != 0) {
            if (sidx >= MAX_ITEMS) break;

            sum = &summaries[sidx];
            memset(sum, 0, sizeof(STOCK_SUMMARY));
            INV_STRCPY(sum->item_code, stocks[i].item_code, sizeof(sum->item_code));
            INV_STRCPY(prev_item, stocks[i].item_code, sizeof(prev_item));

            /* 품목 마스터에서 정보 가져오기 */
            ITEM_MASTER *item = find_item(stocks[i].item_code);
            if (item != NULL) {
                INV_STRCPY(sum->item_name, item->item_name, sizeof(sum->item_name));
                INV_STRCPY(sum->category, item->category, sizeof(sum->category));
                sum->safety_stock = item->safety_stock;
                sum->reorder_point = item->reorder_point;
            }

            sidx++;
        }

        sum = &summaries[sidx - 1];

        /* 창고별 재고 누적 */
        sum->total_on_hand += stocks[i].qty_on_hand;
        sum->total_allocated += stocks[i].qty_allocated;
        sum->total_available += stocks[i].qty_available;
        sum->total_on_order += stocks[i].qty_on_order;
        sum->total_value += stocks[i].total_value;

        /* 창고 내역 저장 */
        if (sum->wh_count < MAX_WAREHOUSES) {
            memcpy(&sum->wh_stocks[sum->wh_count], &stocks[i], sizeof(WAREHOUSE_STOCK));
            sum->wh_count++;
        }
    }

    /* 상태 플래그 설정 */
    for (i = 0; i < sidx; i++) {
        if (summaries[i].total_on_hand > 0) {
            summaries[i].avg_unit_cost = summaries[i].total_value / summaries[i].total_on_hand;
        }

        if (summaries[i].safety_stock > 0 && summaries[i].total_available < summaries[i].safety_stock) {
            summaries[i].status_flag = 'S';  /* 부족 */
        } else {
            ITEM_MASTER *item = find_item(summaries[i].item_code);
            if (item && item->max_stock > 0 && summaries[i].total_on_hand > item->max_stock) {
                summaries[i].status_flag = 'O';  /* 과잉 */
            } else {
                summaries[i].status_flag = 'N';  /* 정상 */
            }
        }
    }

    *summary_cnt = sidx;
    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_save_results - 결과 파일 저장 (CSV)
 ******************************************************************************/
int inv_save_results(const char *filepath, WAREHOUSE_STOCK *stocks, int stock_cnt)
{
    FILE *fp;
    int i;

    if (filepath == NULL || stocks == NULL) return INV_ERR_PARAM;

    fp = fopen(filepath, "w");
    if (fp == NULL) {
        INV_ERROR("Cannot open output file: %s", filepath);
        return INV_ERR_FILE_WRITE;
    }

    /* 헤더 */
    fprintf(fp, "item_code,wh_code,qty_on_hand,qty_allocated,qty_available,qty_on_order,avg_cost,total_value,last_in_date,last_out_date,status\n");

    for (i = 0; i < stock_cnt; i++) {
        fprintf(fp, "%s,%s,%d,%d,%d,%d,%.2f,%.2f,%s,%s,%c\n",
                stocks[i].item_code, stocks[i].wh_code,
                stocks[i].qty_on_hand, stocks[i].qty_allocated,
                stocks[i].qty_available, stocks[i].qty_on_order,
                stocks[i].avg_cost, stocks[i].total_value,
                stocks[i].last_in_date, stocks[i].last_out_date,
                stocks[i].status);
    }

    fclose(fp);
    INV_INFO("Results saved to %s (%d records)", filepath, stock_cnt);
    return INV_SUCCESS;
}

/*******************************************************************************
 * main
 *
 * Usage: inv_batch <item_master.csv> <transactions.csv> <output.csv> [report_type]
 ******************************************************************************/
int main(int argc, char *argv[])
{
    WAREHOUSE_STOCK  out_stocks[MAX_ITEMS * MAX_WAREHOUSES];
    STOCK_SUMMARY    summaries[MAX_ITEMS];
    int out_stock_cnt = 0, summary_cnt = 0;
    BATCH_STAT stat;
    REPORT_OPTION rpt_opt;
    int rc;

    if (argc < 4) {
        printf("Usage: %s <item_master.csv> <transactions.csv> <output.csv> [report_type]\n", argv[0]);
        printf("  report_type: 1=Summary 2=Detail 3=TxnList 4=Shortage 5=Excess\n");
        return 1;
    }

    INV_INFO("=== Inventory Batch Start ===");

    /* 품목 마스터 로드 */
    rc = inv_load_items(argv[1], g_items, &g_item_cnt);
    if (rc != INV_SUCCESS) {
        INV_ERROR("Failed to load items: rc=%d", rc);
        return 1;
    }

    /* 트랜잭션 로드 */
    rc = inv_load_transactions(argv[2], g_txns, &g_txn_cnt);
    if (rc != INV_SUCCESS) {
        INV_ERROR("Failed to load transactions: rc=%d", rc);
        return 1;
    }

    /* 재고 처리 */
    rc = inv_process_transactions(g_txns, g_txn_cnt, out_stocks, &out_stock_cnt, &stat);
    if (rc != INV_SUCCESS) {
        INV_ERROR("Transaction processing failed: rc=%d", rc);
        return 1;
    }

    /* 결과 저장 */
    rc = inv_save_results(argv[3], out_stocks, out_stock_cnt);
    if (rc != INV_SUCCESS) {
        INV_ERROR("Failed to save results: rc=%d", rc);
    }

    /* 집계 */
    rc = inv_calc_summary(out_stocks, out_stock_cnt, g_items, g_item_cnt, summaries, &summary_cnt);

    /* 리포트 생성 */
    if (argc >= 5) {
        memset(&rpt_opt, 0, sizeof(rpt_opt));
        rpt_opt.report_type = atoi(argv[4]);
        rpt_opt.show_zero_stock = 0;
        rpt_opt.page_size = 60;

        rc = inv_generate_report(&rpt_opt, summaries, summary_cnt, g_txns, g_txn_cnt);
        if (rc != INV_SUCCESS) {
            INV_ERROR("Report generation failed: rc=%d", rc);
        }
    }

    printf("Batch completed: processed=%d errors=%d skipped=%d\n", stat.processed, stat.errors, stat.skipped);
    printf("IN amount: %.0f, OUT amount: %.0f\n", stat.total_in_amount, stat.total_out_amount);
    printf("Stock records: %d, Summary items: %d\n", out_stock_cnt, summary_cnt);

    INV_INFO("=== Inventory Batch End ===");
    return 0;
}
