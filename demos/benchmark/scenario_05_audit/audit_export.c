/*******************************************************************************
 * audit_export.c - 감사 로그 내보내기 (순수 C)
 *
 * 작성일: 2011-04-15
 * 수정일: 2016-02-20  최과장 - CSV 포맷 개선 (RFC4180 준수)
 * 수정일: 2019-10-10  김대리 - XML 내보내기 추가
 * 수정일: 2022-05-01  박사원 - 고정폭 리포트 추가
 *
 * 순수 C - DB 접근 없음
 * 감사 로그를 CSV / XML / 고정폭 텍스트로 내보내기
 ******************************************************************************/

#include "audit_types.h"

/* 전역 카운터 */
static int g_export_count = 0;

/* 2016-02-20 사용안함 - 예전 CSV 구분자 */
/* #define OLD_CSV_DELIM '|' */

/*******************************************************************************
 * audit_escape_csv - CSV 이스케이프 처리
 *
 * RFC 4180 규격:
 * - 콤마, 쌍따옴표, 개행이 포함된 필드는 쌍따옴표로 감싼다
 * - 쌍따옴표는 두개로 이스케이프 (" -> "")
 ******************************************************************************/
void audit_escape_csv(const char *src, char *dst, int dst_len)
{
    int need_quote = 0;
    int si, di;
    const char *p;

    if (src == NULL || dst == NULL || dst_len <= 0) {
        if (dst && dst_len > 0) dst[0] = '\0';
        return;
    }

    /* 이스케이프 필요 여부 체크 */
    for (p = src; *p; p++) {
        if (*p == CSV_DELIMITER || *p == CSV_QUOTE || *p == '\n' || *p == '\r') {
            need_quote = 1;
            break;
        }
    }

    if (!need_quote) {
        strncpy(dst, src, dst_len - 1);
        dst[dst_len - 1] = '\0';
        return;
    }

    di = 0;
    if (di < dst_len - 1) dst[di++] = CSV_QUOTE;

    for (si = 0; src[si] && di < dst_len - 2; si++) {
        if (src[si] == CSV_QUOTE) {
            if (di < dst_len - 3) {
                dst[di++] = CSV_QUOTE;
                dst[di++] = CSV_QUOTE;
            }
        } else {
            dst[di++] = src[si];
        }
    }

    if (di < dst_len - 1) dst[di++] = CSV_QUOTE;
    dst[di] = '\0';
}

/*******************************************************************************
 * audit_escape_xml - XML 이스케이프 처리
 *
 * &  -> &amp;
 * <  -> &lt;
 * >  -> &gt;
 * "  -> &quot;
 * '  -> &apos;
 ******************************************************************************/
void audit_escape_xml(const char *src, char *dst, int dst_len)
{
    int si, di;

    if (src == NULL || dst == NULL || dst_len <= 0) {
        if (dst && dst_len > 0) dst[0] = '\0';
        return;
    }

    di = 0;
    for (si = 0; src[si] && di < dst_len - 7; si++) {
        switch (src[si]) {
            case '&':
                dst[di++] = '&'; dst[di++] = 'a'; dst[di++] = 'm'; dst[di++] = 'p'; dst[di++] = ';';
                break;
            case '<':
                dst[di++] = '&'; dst[di++] = 'l'; dst[di++] = 't'; dst[di++] = ';';
                break;
            case '>':
                dst[di++] = '&'; dst[di++] = 'g'; dst[di++] = 't'; dst[di++] = ';';
                break;
            case '"':
                dst[di++] = '&'; dst[di++] = 'q'; dst[di++] = 'u'; dst[di++] = 'o'; dst[di++] = 't'; dst[di++] = ';';
                break;
            case '\'':
                dst[di++] = '&'; dst[di++] = 'a'; dst[di++] = 'p'; dst[di++] = 'o'; dst[di++] = 's'; dst[di++] = ';';
                break;
            default:
                dst[di++] = src[si];
                break;
        }
    }
    dst[di] = '\0';
}

/*******************************************************************************
 * audit_export_csv - CSV 형식 내보내기
 ******************************************************************************/
int audit_export_csv(FILE *fp, AUDIT_RECORD *records, int cnt,
                     const EXPORT_OPTION *opt)
{
    int i;
    char esc_buf[1024];

    if (fp == NULL || records == NULL) return AUDIT_ERR_PARAM;

    /* 헤더 */
    if (opt == NULL || opt->include_header) {
        fprintf(fp, "AUDIT_SEQ%cEVENT_TYPE%cEVENT_DATE%cEVENT_TIME%c"
                    "SEVERITY%cUSER_ID%cUSER_NAME%cIP_ADDR%c"
                    "TABLE_NAME%cCOLUMN_NAME%cOLD_VALUE%cNEW_VALUE%c"
                    "ACTION_DESC%cRESULT%cSESSION_ID%c"
                    "MENU_ID%cSCREEN_ID%cAFFECTED_ROWS\n",
                CSV_DELIMITER, CSV_DELIMITER, CSV_DELIMITER, CSV_DELIMITER,
                CSV_DELIMITER, CSV_DELIMITER, CSV_DELIMITER, CSV_DELIMITER,
                CSV_DELIMITER, CSV_DELIMITER, CSV_DELIMITER, CSV_DELIMITER,
                CSV_DELIMITER, CSV_DELIMITER, CSV_DELIMITER,
                CSV_DELIMITER, CSV_DELIMITER);
    }

    for (i = 0; i < cnt; i++) {
        AUDIT_RECORD *r = &records[i];

        fprintf(fp, "%ld%c", r->audit_seq, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->event_type, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->event_date, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->event_time, CSV_DELIMITER);
        fprintf(fp, "%c%c", r->severity, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->user_id, CSV_DELIMITER);

        audit_escape_csv(r->user_name, esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%c", esc_buf, CSV_DELIMITER);

        fprintf(fp, "%s%c", r->ip_addr, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->table_name, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->column_name, CSV_DELIMITER);

        audit_escape_csv(r->old_value, esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%c", esc_buf, CSV_DELIMITER);

        audit_escape_csv(r->new_value, esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%c", esc_buf, CSV_DELIMITER);

        audit_escape_csv(r->action_desc, esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%c", esc_buf, CSV_DELIMITER);

        fprintf(fp, "%c%c", r->result, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->session_id, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->menu_id, CSV_DELIMITER);
        fprintf(fp, "%s%c", r->screen_id, CSV_DELIMITER);
        fprintf(fp, "%d\n", r->affected_rows);

        g_export_count++;
    }

    return AUDIT_SUCCESS;
}

/*******************************************************************************
 * audit_export_xml - XML 형식 내보내기
 ******************************************************************************/
int audit_export_xml(FILE *fp, AUDIT_RECORD *records, int cnt,
                     const EXPORT_OPTION *opt)
{
    int i;
    char esc_buf[2048];
    const char *enc;

    if (fp == NULL || records == NULL) return AUDIT_ERR_PARAM;

    enc = (opt && opt->encoding[0]) ? opt->encoding : "UTF-8";

    /* XML 헤더 */
    fprintf(fp, "<?xml version=\"1.0\" encoding=\"%s\"?>\n", enc);
    fprintf(fp, "<AuditLogs count=\"%d\">\n", cnt);

    for (i = 0; i < cnt; i++) {
        AUDIT_RECORD *r = &records[i];

        fprintf(fp, "%s<AuditRecord seq=\"%ld\">\n", XML_INDENT, r->audit_seq);
        fprintf(fp, "%s%s<EventType>%s</EventType>\n", XML_INDENT, XML_INDENT, r->event_type);

        audit_escape_xml(audit_event_name(r->event_type), esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%s<EventName>%s</EventName>\n", XML_INDENT, XML_INDENT, esc_buf);

        fprintf(fp, "%s%s<EventDate>%s</EventDate>\n", XML_INDENT, XML_INDENT, r->event_date);
        fprintf(fp, "%s%s<EventTime>%s</EventTime>\n", XML_INDENT, XML_INDENT, r->event_time);
        fprintf(fp, "%s%s<Severity>%s</Severity>\n", XML_INDENT, XML_INDENT, audit_severity_name(r->severity));

        audit_escape_xml(r->user_id, esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%s<UserId>%s</UserId>\n", XML_INDENT, XML_INDENT, esc_buf);

        audit_escape_xml(r->user_name, esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%s<UserName>%s</UserName>\n", XML_INDENT, XML_INDENT, esc_buf);

        fprintf(fp, "%s%s<IpAddr>%s</IpAddr>\n", XML_INDENT, XML_INDENT, r->ip_addr);
        fprintf(fp, "%s%s<TableName>%s</TableName>\n", XML_INDENT, XML_INDENT, r->table_name);

        if (r->column_name[0] && r->column_name[0] != ' ') {
            fprintf(fp, "%s%s<ColumnName>%s</ColumnName>\n", XML_INDENT, XML_INDENT, r->column_name);
        }

        if (r->old_value[0] && r->old_value[0] != ' ') {
            audit_escape_xml(r->old_value, esc_buf, sizeof(esc_buf));
            fprintf(fp, "%s%s<OldValue>%s</OldValue>\n", XML_INDENT, XML_INDENT, esc_buf);
        }

        if (r->new_value[0] && r->new_value[0] != ' ') {
            audit_escape_xml(r->new_value, esc_buf, sizeof(esc_buf));
            fprintf(fp, "%s%s<NewValue>%s</NewValue>\n", XML_INDENT, XML_INDENT, esc_buf);
        }

        audit_escape_xml(r->action_desc, esc_buf, sizeof(esc_buf));
        fprintf(fp, "%s%s<ActionDesc>%s</ActionDesc>\n", XML_INDENT, XML_INDENT, esc_buf);

        fprintf(fp, "%s%s<Result>%c</Result>\n", XML_INDENT, XML_INDENT, r->result);
        fprintf(fp, "%s%s<SessionId>%s</SessionId>\n", XML_INDENT, XML_INDENT, r->session_id);

        if (r->menu_id[0] && r->menu_id[0] != ' ') {
            fprintf(fp, "%s%s<MenuId>%s</MenuId>\n", XML_INDENT, XML_INDENT, r->menu_id);
        }
        if (r->screen_id[0] && r->screen_id[0] != ' ') {
            fprintf(fp, "%s%s<ScreenId>%s</ScreenId>\n", XML_INDENT, XML_INDENT, r->screen_id);
        }
        if (r->affected_rows > 0) {
            fprintf(fp, "%s%s<AffectedRows>%d</AffectedRows>\n", XML_INDENT, XML_INDENT, r->affected_rows);
        }

        fprintf(fp, "%s</AuditRecord>\n", XML_INDENT);
        g_export_count++;
    }

    fprintf(fp, "</AuditLogs>\n");

    return AUDIT_SUCCESS;
}

/*******************************************************************************
 * audit_export_fixed - 고정폭 텍스트 내보내기
 ******************************************************************************/
int audit_export_fixed(FILE *fp, AUDIT_RECORD *records, int cnt,
                       const EXPORT_OPTION *opt)
{
    int i;
    int page_cnt = 0;
    int page_size = (opt && opt->page_size > 0) ? opt->page_size : PAGE_SIZE;

    if (fp == NULL || records == NULL) return AUDIT_ERR_PARAM;

    for (i = 0; i < cnt; i++) {
        AUDIT_RECORD *r = &records[i];

        /* 페이지 헤더 */
        if (i % page_size == 0) {
            page_cnt++;
            if (i > 0) fprintf(fp, "\f");  /* 페이지 넘김 */
            fprintf(fp, "==========================================================================================================================================\n");
            fprintf(fp, "  감 사 로 그 리 포 트                                                                                        Page: %d\n", page_cnt);
            fprintf(fp, "==========================================================================================================================================\n");
            fprintf(fp, "%10s %-4s %-12s %-8s %-5s %-15s %-15s %-30s %c %-30s\n",
                    "순번", "유형", "일자", "시각", "등급", "사용자", "IP주소", "테이블", ' ', "행위설명");
            fprintf(fp, "------------------------------------------------------------------------------------------------------------------------------------------\n");
        }

        fprintf(fp, "%10ld %-4s %-12s %-8s %-5s %-15s %-15s %-30s %c %-30.30s\n",
                r->audit_seq, r->event_type,
                r->event_date, r->event_time,
                audit_severity_name(r->severity),
                r->user_id, r->ip_addr,
                r->table_name, r->result,
                r->action_desc);

        /* 변경 내역이 있으면 부가 라인 출력 */
        if (r->old_value[0] && r->old_value[0] != ' ') {
            fprintf(fp, "%10s %-4s   변경전: %-60.60s\n", "", "", r->old_value);
            fprintf(fp, "%10s %-4s   변경후: %-60.60s\n", "", "", r->new_value);
        }

        g_export_count++;
    }

    /* 푸터 */
    fprintf(fp, "==========================================================================================================================================\n");
    fprintf(fp, "  총 %d 건 출력 완료\n", cnt);
    fprintf(fp, "==========================================================================================================================================\n");

    return AUDIT_SUCCESS;
}

/*******************************************************************************
 * audit_export - 내보내기 메인 (디스패치)
 ******************************************************************************/
int audit_export(const EXPORT_OPTION *opt, AUDIT_RECORD *records, int cnt)
{
    FILE *fp;
    int rc;

    AUD_CHECK_NULL(opt);
    AUD_CHECK_NULL(records);

    if (cnt <= 0) {
        AUD_WARN("No records to export");
        return AUDIT_SUCCESS;
    }

    /* 파일 열기 */
    if (opt->output_path[0] != '\0') {
        fp = fopen(opt->output_path, "w");
        if (fp == NULL) {
            AUD_ERROR("Cannot open export file: %s", opt->output_path);
            return AUDIT_ERR_FILE_OPEN;
        }
    } else {
        fp = stdout;
    }

    g_export_count = 0;

    switch (opt->format) {
        case EXPORT_CSV:
            rc = audit_export_csv(fp, records, cnt, opt);
            break;
        case EXPORT_XML:
            rc = audit_export_xml(fp, records, cnt, opt);
            break;
        case EXPORT_FIXED:
            rc = audit_export_fixed(fp, records, cnt, opt);
            break;
        default:
            AUD_ERROR("Unknown export format: %d", opt->format);
            rc = AUDIT_ERR_FILE_FORMAT;
            break;
    }

    if (fp != stdout) {
        fclose(fp);
    }

    if (rc == AUDIT_SUCCESS) {
        AUD_INFO("Export completed: %d records, format=%d, file=%s",
                 g_export_count, opt->format,
                 opt->output_path[0] ? opt->output_path : "(stdout)");
    }

    return rc;
}
