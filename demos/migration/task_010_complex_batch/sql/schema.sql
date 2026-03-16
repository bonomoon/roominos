/* ============================================= */
/* 스키마 : 일일정산 배치 관련 테이블              */
/* 작성자 : 홍길동                                */
/* 작성일 : 2008.03.15                            */
/* 수정이력:                                      */
/*   2010.06 이과장 - TB_PROMO_RATE 추가          */
/*   2013.05 김대리 - TB_FEE_MST 추가             */
/*   2015.11 박사원 - 휴면계좌 관련 컬럼 추가     */
/*   2018.09 박과장 - NEW_ACCT_TYPE 컬럼 추가     */
/*   2019.04 정대리 - TB_ACCT_LIMIT 추가          */
/*   2020.02 최주임 - TB_COVID_EXEMPT 추가        */
/*   2022.08 정대리 - TB_LIMIT_OVER_LOG 추가      */
/* ============================================= */


-- ==============================================
-- 계좌 마스터
-- ==============================================
CREATE TABLE TB_ACCT_MST (
    ACCT_NO         VARCHAR2(20)    NOT NULL,   -- 계좌번호 (PK)
    ACCT_NM         VARCHAR2(100),              -- 계좌명/고객명
    BR_CD           VARCHAR2(4)     NOT NULL,   -- 영업점코드
    CUST_NO         VARCHAR2(20),               -- 고객번호
    ACCT_STAT       NUMBER(1)       DEFAULT 1,  -- 계좌상태 1:정상 2:정지 3:휴면 4:동결 9:해지
    ACCT_TYPE       NUMBER(2)       NOT NULL,   -- 계좌유형 1:보통예금 2:적금 3:정기예금 4:자유적금 5:기업당좌 6:외화 7:비대면 8:청약 9:기타
    PRODUCT_CD      VARCHAR2(10),               -- 상품코드
    BAL_AMT         NUMBER(18,2)    DEFAULT 0,  -- 잔액
    AVAIL_AMT       NUMBER(18,2)    DEFAULT 0,  -- 가용잔액
    HOLD_AMT        NUMBER(18,2)    DEFAULT 0,  -- 보류금액
    OPEN_DT         VARCHAR2(8)     NOT NULL,   -- 개설일자 YYYYMMDD
    CLOSE_DT        VARCHAR2(8),                -- 해지일자
    LAST_TXN_DT     VARCHAR2(8),                -- 최종거래일
    FEE_EXEMPT_YN   NUMBER(1)       DEFAULT 0,  -- 수수료면제 0:N 1:Y
    NEW_ACCT_TYPE   NUMBER(2),                  -- 신규계좌유형 (2018.09 박과장)
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_ACCT_MST PRIMARY KEY (ACCT_NO)
);

CREATE INDEX IDX_ACCT_MST_01 ON TB_ACCT_MST (BR_CD, ACCT_STAT);
CREATE INDEX IDX_ACCT_MST_02 ON TB_ACCT_MST (ACCT_STAT, OPEN_DT);
CREATE INDEX IDX_ACCT_MST_03 ON TB_ACCT_MST (CUST_NO);
CREATE INDEX IDX_ACCT_MST_04 ON TB_ACCT_MST (PRODUCT_CD);
-- IDX_ACCT_MST_05 삭제됨 (2017.03 - 사용안함)


-- ==============================================
-- 고객 마스터
-- ==============================================
CREATE TABLE TB_CUST_MST (
    CUST_NO         VARCHAR2(20)    NOT NULL,   -- 고객번호 (PK)
    CUST_NM         VARCHAR2(100),              -- 고객명
    CUST_GRADE      NUMBER(1)       DEFAULT 5,  -- 등급 1:VIP 2:GOLD 3:SILVER 4:BRONZE 5:NORMAL
    CUST_TYPE       VARCHAR2(2),                -- 고객유형 01:개인 02:법인
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_CUST_MST PRIMARY KEY (CUST_NO)
);

CREATE INDEX IDX_CUST_MST_01 ON TB_CUST_MST (CUST_GRADE);


-- ==============================================
-- 상품 마스터
-- ==============================================
CREATE TABLE TB_PRODUCT_MST (
    PRODUCT_CD      VARCHAR2(10)    NOT NULL,   -- 상품코드 (PK)
    PRODUCT_NM      VARCHAR2(100),              -- 상품명
    PRODUCT_TYPE    VARCHAR2(2),                -- 상품유형
    BASE_RATE       NUMBER(7,4)     DEFAULT 0,  -- 기본금리
    SPC_RATE        NUMBER(7,4)     DEFAULT 0,  -- 우대금리
    MIN_BAL         NUMBER(18,2)    DEFAULT 0,  -- 최소가입금액
    MAX_BAL         NUMBER(18,2),               -- 최대가입금액
    USE_YN          VARCHAR2(1)     DEFAULT 'Y',
    START_DT        VARCHAR2(8),                -- 판매시작일
    END_DT          VARCHAR2(8),                -- 판매종료일
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_PRODUCT_MST PRIMARY KEY (PRODUCT_CD)
);


-- ==============================================
-- 영업점 마스터
-- ==============================================
CREATE TABLE TB_BRANCH_MST (
    BR_CD           VARCHAR2(4)     NOT NULL,   -- 영업점코드 (PK)
    BR_NM           VARCHAR2(50)    NOT NULL,   -- 영업점명
    PARENT_BR_CD    VARCHAR2(4),                -- 상위영업점코드
    BR_LEVEL        NUMBER(1)       DEFAULT 3,  -- 레벨 1:본부 2:지역본부 3:영업점
    REGION_CD       VARCHAR2(4),                -- 지역코드
    USE_YN          VARCHAR2(1)     DEFAULT 'Y',
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_BRANCH_MST PRIMARY KEY (BR_CD)
);

CREATE INDEX IDX_BRANCH_MST_01 ON TB_BRANCH_MST (PARENT_BR_CD);


-- ==============================================
-- 거래내역
-- ==============================================
CREATE TABLE TB_TXN_HIST (
    ACCT_NO         VARCHAR2(20)    NOT NULL,
    TXN_DT          VARCHAR2(8)     NOT NULL,
    TXN_SEQ         NUMBER(10)      NOT NULL,
    TXN_TYPE        VARCHAR2(2)     NOT NULL,   -- 01:입금 02:이체입금 03:출금 04:이체출금
    TXN_AMT         NUMBER(18,2)    NOT NULL,
    BF_BAL          NUMBER(18,2),               -- 거래전잔액
    AF_BAL          NUMBER(18,2),               -- 거래후잔액
    BR_CD           VARCHAR2(4),
    CHANNEL         VARCHAR2(2),                -- 01:창구 02:ATM 03:인터넷 04:모바일
    REG_DT          DATE            DEFAULT SYSDATE,
    CONSTRAINT PK_TXN_HIST PRIMARY KEY (ACCT_NO, TXN_DT, TXN_SEQ)
);

CREATE INDEX IDX_TXN_HIST_01 ON TB_TXN_HIST (TXN_DT, ACCT_NO);
CREATE INDEX IDX_TXN_HIST_02 ON TB_TXN_HIST (ACCT_NO, TXN_DT, TXN_TYPE);


-- ==============================================
-- 수수료 마스터
-- 2013.05 김대리 추가
-- ==============================================
CREATE TABLE TB_FEE_MST (
    PRODUCT_CD      VARCHAR2(10)    NOT NULL,
    FEE_SEQ         NUMBER(5)       NOT NULL,
    FEE_TYPE        VARCHAR2(2),                -- 01:잔액기반 02:건수기반 03:유지수수료
    FEE_RATE        NUMBER(7,4)     DEFAULT 0,  -- 수수료율 (%)
    FREE_TXN_CNT    NUMBER(5)       DEFAULT 0,  -- 무료거래건수
    MAINT_FEE       NUMBER(10,2)    DEFAULT 0,  -- 월 유지수수료 (원)
    USE_YN          VARCHAR2(1)     DEFAULT 'Y',
    START_DT        VARCHAR2(8)     NOT NULL,
    END_DT          VARCHAR2(8),
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_FEE_MST PRIMARY KEY (PRODUCT_CD, FEE_SEQ)
);


-- ==============================================
-- 프로모션 금리
-- 2010.06 이과장 추가
-- ==============================================
CREATE TABLE TB_PROMO_RATE (
    ACCT_NO         VARCHAR2(20)    NOT NULL,
    PROMO_SEQ       NUMBER(5)       NOT NULL,
    PROMO_RATE      NUMBER(7,4),                -- 프로모션 추가금리
    START_DT        VARCHAR2(8)     NOT NULL,
    END_DT          VARCHAR2(8)     NOT NULL,
    USE_YN          VARCHAR2(1)     DEFAULT 'Y',
    PROMO_NM        VARCHAR2(100),              -- 프로모션명
    REG_DT          DATE            DEFAULT SYSDATE,
    CONSTRAINT PK_PROMO_RATE PRIMARY KEY (ACCT_NO, PROMO_SEQ)
);

CREATE INDEX IDX_PROMO_RATE_01 ON TB_PROMO_RATE (ACCT_NO, START_DT, END_DT);


-- ==============================================
-- 계좌 한도
-- 2019.04 정대리 추가
-- ==============================================
CREATE TABLE TB_ACCT_LIMIT (
    ACCT_NO         VARCHAR2(20)    NOT NULL,   -- 계좌번호 (PK)
    LIMIT_AMT       NUMBER(18,2)    NOT NULL,   -- 한도금액
    LIMIT_TYPE      VARCHAR2(2)     DEFAULT '01', -- 01:잔액한도 02:거래한도
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_ACCT_LIMIT PRIMARY KEY (ACCT_NO)
);


-- ==============================================
-- 코로나 감면 설정
-- 2020.02 최주임 추가
-- ==============================================
CREATE TABLE TB_COVID_EXEMPT (
    EXEMPT_SEQ      NUMBER(5)       NOT NULL,   -- 순번 (PK)
    EXEMPT_RATE     NUMBER(5,2),                -- 감면율 (%)
    START_DT        VARCHAR2(8)     NOT NULL,
    END_DT          VARCHAR2(8)     NOT NULL,
    USE_YN          VARCHAR2(1)     DEFAULT 'Y',
    DESCRIPTION     VARCHAR2(200),
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_COVID_EXEMPT PRIMARY KEY (EXEMPT_SEQ)
);


-- ==============================================
-- 정산 내역 (건별)
-- ==============================================
CREATE TABLE TB_SETTLE_HIST (
    ACCT_NO         VARCHAR2(20)    NOT NULL,
    SETTLE_DT       VARCHAR2(8)     NOT NULL,
    SETTLE_SEQ      NUMBER(10)      NOT NULL,
    SETTLE_TYPE     VARCHAR2(2)     NOT NULL,   -- 01:이자 02:수수료 03:세금 04:위약금
    SETTLE_AMT      NUMBER(18,2)    NOT NULL,
    BF_BAL          NUMBER(18,2),               -- 정산전잔액
    AF_BAL          NUMBER(18,2),               -- 정산후잔액
    REG_DT          DATE            DEFAULT SYSDATE,
    CONSTRAINT PK_SETTLE_HIST PRIMARY KEY (ACCT_NO, SETTLE_DT, SETTLE_SEQ)
);

CREATE INDEX IDX_SETTLE_HIST_01 ON TB_SETTLE_HIST (SETTLE_DT, SETTLE_TYPE);
CREATE INDEX IDX_SETTLE_HIST_02 ON TB_SETTLE_HIST (ACCT_NO, SETTLE_DT, SETTLE_TYPE);


-- ==============================================
-- 정산 일지 (일별 집계)
-- ==============================================
CREATE TABLE TB_SETTLE_DAILY (
    ACCT_NO         VARCHAR2(20)    NOT NULL,
    SETTLE_DT       VARCHAR2(8)     NOT NULL,
    INT_AMT         NUMBER(18,2)    DEFAULT 0,  -- 이자금액
    FEE_AMT         NUMBER(18,2)    DEFAULT 0,  -- 수수료
    TAX_AMT         NUMBER(18,2)    DEFAULT 0,  -- 세금
    SETTLE_AMT      NUMBER(18,2)    DEFAULT 0,  -- 정산금액 (이자-세금-수수료)
    BAL_AMT         NUMBER(18,2)    DEFAULT 0,  -- 정산후잔액
    ACCT_TYPE       NUMBER(2),
    BR_CD           VARCHAR2(4),
    CUST_GRADE      NUMBER(1),
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_SETTLE_DAILY PRIMARY KEY (ACCT_NO, SETTLE_DT)
);

CREATE INDEX IDX_SETTLE_DAILY_01 ON TB_SETTLE_DAILY (SETTLE_DT, BR_CD);
CREATE INDEX IDX_SETTLE_DAILY_02 ON TB_SETTLE_DAILY (SETTLE_DT, ACCT_TYPE);
CREATE INDEX IDX_SETTLE_DAILY_03 ON TB_SETTLE_DAILY (SETTLE_DT, CUST_GRADE);


-- ==============================================
-- 배치 제어 테이블
-- ==============================================
CREATE TABLE TB_BATCH_CTL (
    BATCH_ID        VARCHAR2(30)    NOT NULL,   -- 배치ID (PK)
    BATCH_DT        VARCHAR2(8)     NOT NULL,   -- 배치일자 (PK)
    BATCH_STAT      VARCHAR2(1)     DEFAULT 'R', -- R:대기 P:처리중 C:완료 E:에러
    START_DT        DATE,                       -- 시작시각
    END_DT          DATE,                       -- 종료시각
    TOTAL_CNT       NUMBER(10)      DEFAULT 0,
    SUCC_CNT        NUMBER(10)      DEFAULT 0,
    ERR_CNT         NUMBER(10)      DEFAULT 0,
    REG_DT          DATE            DEFAULT SYSDATE,
    UPD_DT          DATE,
    CONSTRAINT PK_BATCH_CTL PRIMARY KEY (BATCH_ID, BATCH_DT)
);


-- ==============================================
-- 배치 에러 로그
-- ==============================================
CREATE TABLE TB_BATCH_ERR_LOG (
    BATCH_ID        VARCHAR2(30)    NOT NULL,
    BATCH_DT        VARCHAR2(8)     NOT NULL,
    ACCT_NO         VARCHAR2(20),
    ERR_MSG         VARCHAR2(500),
    ERR_CD          NUMBER(5),
    REG_DT          DATE            DEFAULT SYSDATE
);

CREATE INDEX IDX_BATCH_ERR_01 ON TB_BATCH_ERR_LOG (BATCH_ID, BATCH_DT);
CREATE INDEX IDX_BATCH_ERR_02 ON TB_BATCH_ERR_LOG (ACCT_NO, BATCH_DT);


-- ==============================================
-- 한도초과 로그
-- 2022.08 정대리 추가
-- ==============================================
CREATE TABLE TB_LIMIT_OVER_LOG (
    ACCT_NO         VARCHAR2(20)    NOT NULL,
    CHECK_DT        VARCHAR2(8)     NOT NULL,
    BAL_AMT         NUMBER(18,2),
    LIMIT_AMT       NUMBER(18,2),
    OVER_AMT        NUMBER(18,2),
    REG_DT          DATE            DEFAULT SYSDATE,
    CONSTRAINT PK_LIMIT_OVER_LOG PRIMARY KEY (ACCT_NO, CHECK_DT)
);

CREATE INDEX IDX_LIMIT_OVER_01 ON TB_LIMIT_OVER_LOG (CHECK_DT);


-- ==============================================
-- 시퀀스 (순번 채번용 -- 코드에서 MAX+1 쓰지만
-- 원래는 시퀀스 써야함. 만들어는 놨음)
-- ==============================================
CREATE SEQUENCE SQ_TXN_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE SQ_SETTLE_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;


-- ==============================================
-- 코멘트
-- ==============================================
COMMENT ON TABLE TB_ACCT_MST IS '계좌마스터';
COMMENT ON COLUMN TB_ACCT_MST.ACCT_NO IS '계좌번호';
COMMENT ON COLUMN TB_ACCT_MST.ACCT_STAT IS '계좌상태(1:정상,2:정지,3:휴면,4:동결,9:해지)';
COMMENT ON COLUMN TB_ACCT_MST.ACCT_TYPE IS '계좌유형(1:보통예금,2:적금,3:정기예금,4:자유적금,5:기업당좌,6:외화,7:비대면,8:청약,9:기타)';
COMMENT ON COLUMN TB_ACCT_MST.NEW_ACCT_TYPE IS '신규계좌유형-2018.09추가(41:자유적금신형,42:자유적금특판)';

COMMENT ON TABLE TB_CUST_MST IS '고객마스터';
COMMENT ON TABLE TB_PRODUCT_MST IS '상품마스터';
COMMENT ON TABLE TB_BRANCH_MST IS '영업점마스터';

COMMENT ON TABLE TB_TXN_HIST IS '거래내역';
COMMENT ON COLUMN TB_TXN_HIST.TXN_TYPE IS '거래유형(01:입금,02:이체입금,03:출금,04:이체출금)';

COMMENT ON TABLE TB_FEE_MST IS '수수료마스터';
COMMENT ON TABLE TB_PROMO_RATE IS '프로모션금리';

COMMENT ON TABLE TB_SETTLE_HIST IS '정산내역(건별)';
COMMENT ON COLUMN TB_SETTLE_HIST.SETTLE_TYPE IS '정산유형(01:이자,02:수수료,03:세금,04:위약금)';

COMMENT ON TABLE TB_SETTLE_DAILY IS '정산일지(일별집계)';
COMMENT ON TABLE TB_BATCH_CTL IS '배치제어테이블';
COMMENT ON COLUMN TB_BATCH_CTL.BATCH_STAT IS '배치상태(R:대기,P:처리중,C:완료,E:에러)';
COMMENT ON TABLE TB_COVID_EXEMPT IS '코로나감면설정-2020.02추가';
COMMENT ON TABLE TB_LIMIT_OVER_LOG IS '한도초과로그-2022.08추가';
COMMENT ON TABLE TB_ACCT_LIMIT IS '계좌한도-2019.04추가';
COMMENT ON TABLE TB_BATCH_ERR_LOG IS '배치에러로그';


-- ==============================================
-- 참조 데이터
-- ==============================================

-- 영업점 마스터 (트리구조)
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('0000', '본부', NULL, 1, NULL, 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('1000', '수도권본부', '0000', 2, '01', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('2000', '영남본부', '0000', 2, '02', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('3000', '호남본부', '0000', 2, '03', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('1001', '강남지점', '1000', 3, '01', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('1002', '서초지점', '1000', 3, '01', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('1003', '여의도지점', '1000', 3, '01', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('2001', '부산지점', '2000', 3, '02', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('2002', '대구지점', '2000', 3, '02', 'Y');
INSERT INTO TB_BRANCH_MST (BR_CD, BR_NM, PARENT_BR_CD, BR_LEVEL, REGION_CD, USE_YN)
    VALUES ('3001', '광주지점', '3000', 3, '03', 'Y');

-- 코로나 감면 설정
INSERT INTO TB_COVID_EXEMPT (EXEMPT_SEQ, EXEMPT_RATE, START_DT, END_DT, USE_YN, DESCRIPTION)
    VALUES (1, 30.00, '20200301', '20201231', 'Y', '코로나19 1차 수수료 감면');
INSERT INTO TB_COVID_EXEMPT (EXEMPT_SEQ, EXEMPT_RATE, START_DT, END_DT, USE_YN, DESCRIPTION)
    VALUES (2, 20.00, '20210101', '20211231', 'Y', '코로나19 2차 수수료 감면');
INSERT INTO TB_COVID_EXEMPT (EXEMPT_SEQ, EXEMPT_RATE, START_DT, END_DT, USE_YN, DESCRIPTION)
    VALUES (3, 10.00, '20220101', '20231231', 'Y', '코로나19 3차 수수료 감면 (축소)');

COMMIT;
