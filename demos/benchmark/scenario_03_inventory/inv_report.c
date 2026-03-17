/*******************************************************************************
 * inv_report.c - 재고 리포트 생성
 *
 * 작성일: 2010-09-01
 * 수정일: 2014-04-20  최과장 - 창고별 상세 리포트 추가
 * 수정일: 2018-08-15  김대리 - 부족/과잉 재고 리포트
 * 수정일: 2021-12-01  박사원 - 재고금액 표시 추가
 *
 * 순수 C - fprintf 기반 고정폭 리포트 생성
 * 표준출력 또는 파일로 출력
 ******************************************************************************/

#include "inv_types.h"

/* 전역 - 페이지 카운터 */
static int g_page_no = 0;
static int g_line_no = 0;

/* 2014-04-20 사용안함 - 구버전 리포트 폭 */
/* #define OLD_REPORT_WIDTH 80 */

/*******************************************************************************
 * print_header - 리포트 헤더 출력
 ******************************************************************************/
static void print_header(FILE *fp, const char *title, int page_size)
{
    char date_buf[MAX_DATE_LEN];
    time_t now = time(NULL);
    struct tm *tm_now = localtime(&now);

    snprintf(date_buf, sizeof(date_buf), "%04d-%02d-%02d",
             tm_now->tm_year + 1900, tm_now->tm_mon + 1, tm_now->tm_mday);

    g_page_no++;
    g_line_no = 0;

    fprintf(fp, "\f");  /* 페이지 넘김 */
    fprintf(fp, "%-*s%s  Page: %d\n", REPORT_LINE_WIDTH - 30, title, date_buf, g_page_no);
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "====================================================================================================================================================================");
    g_line_no += 2;
}

/*******************************************************************************
 * check_page_break - 페이지 넘김 체크
 ******************************************************************************/
static void check_page_break(FILE *fp, const char *title, int page_size)
{
    if (page_size > 0 && g_line_no >= page_size) {
        print_header(fp, title, page_size);
    }
}

/*******************************************************************************
 * format_number - 숫자 3자리 콤마 포맷
 ******************************************************************************/
static void format_number(double val, char *buf, int buf_len)
{
    char tmp[30];
    int len, i, j;
    int neg = 0;

    if (val < 0) { neg = 1; val = -val; }
    sprintf(tmp, "%.0f", val);
    len = strlen(tmp);

    j = 0;
    if (neg && j < buf_len - 1) buf[j++] = '-';
    for (i = 0; i < len && j < buf_len - 1; i++) {
        if (i > 0 && (len - i) % 3 == 0 && j < buf_len - 1) buf[j++] = ',';
        buf[j++] = tmp[i];
    }
    buf[j] = '\0';
}

/*******************************************************************************
 * inv_report_stock_summary - 재고 현황 요약 리포트
 ******************************************************************************/
int inv_report_stock_summary(FILE *fp, STOCK_SUMMARY *summaries, int cnt,
                             const REPORT_OPTION *opt)
{
    int i;
    char amt_buf[20], val_buf[20];
    double grand_total_value = 0;
    int grand_total_qty = 0;
    int shortage_cnt = 0, excess_cnt = 0;

    if (fp == NULL || summaries == NULL) return INV_ERR_PARAM;

    print_header(fp, "[ 재 고 현 황 요 약 ]", opt ? opt->page_size : 60);

    fprintf(fp, "%-15s %-30s %-6s %10s %10s %10s %10s %15s %4s\n",
            "품목코드", "품목명", "단위", "현재고", "가용수량", "안전재고", "발주잔량", "재고금액", "상태");
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "--------------------------------------------------------------------------------------------------------------------------------------------------------------------");
    g_line_no += 2;

    for (i = 0; i < cnt; i++) {
        /* 필터 적용 */
        if (opt && opt->category[0] != '\0' && strcmp(summaries[i].category, opt->category) != 0) continue;
        if (opt && !opt->show_zero_stock && summaries[i].total_on_hand == 0) continue;

        format_number(summaries[i].total_value, val_buf, sizeof(val_buf));

        fprintf(fp, "%-15s %-30s %-6s %10d %10d %10d %10d %15s   %c\n",
                summaries[i].item_code,
                summaries[i].item_name,
                "",  /* 단위는 마스터에서 가져와야 하지만 생략 */
                summaries[i].total_on_hand,
                summaries[i].total_available,
                summaries[i].safety_stock,
                summaries[i].total_on_order,
                val_buf,
                summaries[i].status_flag);

        grand_total_qty += summaries[i].total_on_hand;
        grand_total_value += summaries[i].total_value;

        if (summaries[i].status_flag == 'S') shortage_cnt++;
        if (summaries[i].status_flag == 'O') excess_cnt++;

        g_line_no++;
        check_page_break(fp, "[ 재 고 현 황 요 약 (계속) ]", opt ? opt->page_size : 60);
    }

    /* 합계 */
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "--------------------------------------------------------------------------------------------------------------------------------------------------------------------");
    format_number(grand_total_value, val_buf, sizeof(val_buf));
    fprintf(fp, "%-52s %10d %10s %10s %10s %15s\n", "[ 합 계 ]", grand_total_qty, "", "", "", val_buf);
    fprintf(fp, "\n");
    fprintf(fp, " 총 품목수: %d   부족: %d   과잉: %d   정상: %d\n", cnt, shortage_cnt, excess_cnt, cnt - shortage_cnt - excess_cnt);
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "====================================================================================================================================================================");

    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_report_stock_detail - 재고 현황 상세 (창고별)
 ******************************************************************************/
int inv_report_stock_detail(FILE *fp, STOCK_SUMMARY *summaries, int cnt,
                            const REPORT_OPTION *opt)
{
    int i, j;
    char val_buf[20];

    if (fp == NULL || summaries == NULL) return INV_ERR_PARAM;

    print_header(fp, "[ 재 고 현 황 상 세 (창고별) ]", opt ? opt->page_size : 60);

    for (i = 0; i < cnt; i++) {
        if (opt && !opt->show_zero_stock && summaries[i].total_on_hand == 0) continue;
        if (opt && opt->item_code[0] != '\0' && strcmp(summaries[i].item_code, opt->item_code) != 0) continue;

        fprintf(fp, "\n  품목: [%s] %s\n", summaries[i].item_code, summaries[i].item_name);
        format_number(summaries[i].total_value, val_buf, sizeof(val_buf));
        fprintf(fp, "  총현재고: %d  가용: %d  안전재고: %d  재고금액: %s\n",
                summaries[i].total_on_hand, summaries[i].total_available,
                summaries[i].safety_stock, val_buf);
        fprintf(fp, "  %-8s %-20s %10s %10s %10s %12s %12s %15s\n",
                "창고", "창고명", "현재고", "할당", "가용", "최종입고", "최종출고", "재고금액");
        fprintf(fp, "  %.*s\n", REPORT_LINE_WIDTH - 4, "------------------------------------------------------------------------------------------------------------");
        g_line_no += 4;

        for (j = 0; j < summaries[i].wh_count; j++) {
            WAREHOUSE_STOCK *ws = &summaries[i].wh_stocks[j];

            if (opt && opt->wh_code[0] != '\0' && strcmp(ws->wh_code, opt->wh_code) != 0) continue;

            format_number(ws->total_value, val_buf, sizeof(val_buf));
            fprintf(fp, "  %-8s %-20s %10d %10d %10d %12s %12s %15s\n",
                    ws->wh_code, ws->wh_name,
                    ws->qty_on_hand, ws->qty_allocated, ws->qty_available,
                    ws->last_in_date[0] ? ws->last_in_date : "-",
                    ws->last_out_date[0] ? ws->last_out_date : "-",
                    val_buf);
            g_line_no++;
            check_page_break(fp, "[ 재 고 현 황 상 세 (계속) ]", opt ? opt->page_size : 60);
        }
    }

    fprintf(fp, "\n%.*s\n", REPORT_LINE_WIDTH, "====================================================================================================================================================================");
    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_report_txn_list - 입출고 내역 리포트
 ******************************************************************************/
int inv_report_txn_list(FILE *fp, INV_TRANSACTION *txns, int cnt,
                        const REPORT_OPTION *opt)
{
    int i;
    char amt_buf[20];
    double total_in = 0, total_out = 0;
    int in_cnt = 0, out_cnt = 0;

    if (fp == NULL || txns == NULL) return INV_ERR_PARAM;

    print_header(fp, "[ 입 출 고 내 역 ]", opt ? opt->page_size : 60);

    fprintf(fp, "%8s %-12s %-4s %-15s %-8s %-8s %10s %12s %15s %-20s\n",
            "순번", "일자", "유형", "품목코드", "창고", "대상창고", "수량", "단가", "금액", "LOT");
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "--------------------------------------------------------------------------------------------------------------------------------------------------------------------");
    g_line_no += 2;

    for (i = 0; i < cnt; i++) {
        /* 날짜 필터 */
        if (opt && opt->from_date[0] != '\0' && DATE_CMP(txns[i].txn_date, opt->from_date) < 0) continue;
        if (opt && opt->to_date[0] != '\0' && DATE_CMP(txns[i].txn_date, opt->to_date) > 0) continue;
        /* 품목 필터 */
        if (opt && opt->item_code[0] != '\0' && strcmp(txns[i].item_code, opt->item_code) != 0) continue;
        /* 창고 필터 */
        if (opt && opt->wh_code[0] != '\0' && strcmp(txns[i].wh_code, opt->wh_code) != 0) continue;

        format_number(txns[i].amount, amt_buf, sizeof(amt_buf));

        fprintf(fp, "%8d %-12s %-4s %-15s %-8s %-8s %10d %12.0f %15s %-20s\n",
                txns[i].txn_seq, txns[i].txn_date, txns[i].txn_type,
                txns[i].item_code, txns[i].wh_code,
                txns[i].to_wh_code[0] ? txns[i].to_wh_code : "-",
                txns[i].qty, txns[i].unit_price, amt_buf,
                txns[i].lot_no[0] ? txns[i].lot_no : "-");

        /* 입출고 집계 */
        if (strcmp(txns[i].txn_type, TXN_IN) == 0 || strcmp(txns[i].txn_type, TXN_RETURN) == 0) {
            total_in += txns[i].amount;
            in_cnt++;
        } else if (strcmp(txns[i].txn_type, TXN_OUT) == 0 || strcmp(txns[i].txn_type, TXN_SCRAP) == 0) {
            total_out += txns[i].amount;
            out_cnt++;
        }

        g_line_no++;
        check_page_break(fp, "[ 입 출 고 내 역 (계속) ]", opt ? opt->page_size : 60);
    }

    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "--------------------------------------------------------------------------------------------------------------------------------------------------------------------");
    format_number(total_in, amt_buf, sizeof(amt_buf));
    fprintf(fp, " 입고: %d건  %s원\n", in_cnt, amt_buf);
    format_number(total_out, amt_buf, sizeof(amt_buf));
    fprintf(fp, " 출고: %d건  %s원\n", out_cnt, amt_buf);
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "====================================================================================================================================================================");

    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_report_shortage - 부족 재고 리포트
 ******************************************************************************/
int inv_report_shortage(FILE *fp, STOCK_SUMMARY *summaries, int cnt)
{
    int i;
    int found = 0;

    if (fp == NULL || summaries == NULL) return INV_ERR_PARAM;

    print_header(fp, "[ 부 족 재 고 리 스 트 ]", 60);

    fprintf(fp, "%-15s %-30s %10s %10s %10s %10s\n",
            "품목코드", "품목명", "현재고", "안전재고", "부족수량", "발주잔량");
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "--------------------------------------------------------------------------------------------------------------------------------------------------------------------");

    for (i = 0; i < cnt; i++) {
        if (summaries[i].status_flag != 'S') continue;

        int shortage = summaries[i].safety_stock - summaries[i].total_available;
        fprintf(fp, "%-15s %-30s %10d %10d %10d %10d\n",
                summaries[i].item_code, summaries[i].item_name,
                summaries[i].total_on_hand, summaries[i].safety_stock,
                shortage > 0 ? shortage : 0,
                summaries[i].total_on_order);
        found++;
    }

    if (found == 0) {
        fprintf(fp, "  부족 재고 없음\n");
    }

    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "====================================================================================================================================================================");
    fprintf(fp, " 부족 품목: %d건\n", found);

    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_report_excess - 과잉 재고 리포트
 ******************************************************************************/
int inv_report_excess(FILE *fp, STOCK_SUMMARY *summaries, int cnt)
{
    int i;
    int found = 0;
    char val_buf[20];

    if (fp == NULL || summaries == NULL) return INV_ERR_PARAM;

    print_header(fp, "[ 과 잉 재 고 리 스 트 ]", 60);

    fprintf(fp, "%-15s %-30s %10s %10s %10s %15s\n",
            "품목코드", "품목명", "현재고", "최대재고", "초과수량", "초과금액");
    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "--------------------------------------------------------------------------------------------------------------------------------------------------------------------");

    for (i = 0; i < cnt; i++) {
        if (summaries[i].status_flag != 'O') continue;

        /* 최대재고 정보는 마스터에서 가져와야 하지만 여기서는 간이 계산 */
        int excess = summaries[i].total_on_hand - summaries[i].safety_stock * 3;  /* 안전재고 3배 초과시 */
        double excess_value = excess > 0 ? excess * summaries[i].avg_unit_cost : 0;

        format_number(excess_value, val_buf, sizeof(val_buf));
        fprintf(fp, "%-15s %-30s %10d %10d %10d %15s\n",
                summaries[i].item_code, summaries[i].item_name,
                summaries[i].total_on_hand,
                summaries[i].safety_stock * 3,
                excess > 0 ? excess : 0,
                val_buf);
        found++;
    }

    if (found == 0) {
        fprintf(fp, "  과잉 재고 없음\n");
    }

    fprintf(fp, "%.*s\n", REPORT_LINE_WIDTH, "====================================================================================================================================================================");
    fprintf(fp, " 과잉 품목: %d건\n", found);

    return INV_SUCCESS;
}

/*******************************************************************************
 * inv_generate_report - 리포트 생성 메인
 ******************************************************************************/
int inv_generate_report(const REPORT_OPTION *opt,
                        STOCK_SUMMARY *summaries, int summary_cnt,
                        INV_TRANSACTION *txns, int txn_cnt)
{
    FILE *fp;
    int rc = INV_SUCCESS;

    if (opt == NULL) return INV_ERR_PARAM;

    /* 출력 대상 결정 */
    if (opt->output_path[0] != '\0') {
        fp = fopen(opt->output_path, "w");
        if (fp == NULL) {
            INV_ERROR("Cannot open report file: %s", opt->output_path);
            return INV_ERR_FILE_WRITE;
        }
    } else {
        fp = stdout;
    }

    g_page_no = 0;
    g_line_no = 0;

    switch (opt->report_type) {
        case RPT_STOCK_SUMMARY:
            rc = inv_report_stock_summary(fp, summaries, summary_cnt, opt);
            break;
        case RPT_STOCK_DETAIL:
            rc = inv_report_stock_detail(fp, summaries, summary_cnt, opt);
            break;
        case RPT_TXN_LIST:
            rc = inv_report_txn_list(fp, txns, txn_cnt, opt);
            break;
        case RPT_SHORTAGE:
            rc = inv_report_shortage(fp, summaries, summary_cnt);
            break;
        case RPT_EXCESS:
            rc = inv_report_excess(fp, summaries, summary_cnt);
            break;
        default:
            INV_ERROR("Unknown report type: %d", opt->report_type);
            rc = INV_ERR_PARAM;
            break;
    }

    if (fp != stdout) {
        fclose(fp);
        INV_INFO("Report saved: %s (type=%d)", opt->output_path, opt->report_type);
    }

    return rc;
}
