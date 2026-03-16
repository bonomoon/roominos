# ============================================
# Makefile for SETTLE_BAT / RPT_DAILY
# 일일정산 배치 프로그램 빌드
# 작성자: 홍길동
# 작성일: 2008.03.15
#
# 사용법:
#   make all       - 전체 빌드
#   make settle    - SETTLE_BAT만 빌드
#   make rpt       - RPT_DAILY만 빌드
#   make clean     - 정리
#
# 환경변수:
#   ORACLE_HOME    - Oracle 설치 경로
#   PROC_HOME      - Pro*C 설치 경로 (기본: $ORACLE_HOME/bin)
# ============================================

# Oracle 환경
ORACLE_HOME ?= /oracle/product/12.2.0
PROC        = $(ORACLE_HOME)/bin/proc
CC          = gcc
# CC        = cc    # HP-UX 에서는 이거 씀
# CC        = xlc   # AIX 에서는 이거

# 컴파일 옵션
CFLAGS      = -g -O2 -Wall
# CFLAGS    = -g -O0        # 디버그시 최적화 끔
INCLUDES    = -I$(ORACLE_HOME)/precomp/public \
              -I$(ORACLE_HOME)/rdbms/public \
              -Isrc
LIBS        = -L$(ORACLE_HOME)/lib \
              -lclntsh -lsql12 \
              -lm -lpthread

# Pro*C 옵션
PROCFLAGS   = include=$(ORACLE_HOME)/precomp/public \
              include=src \
              code=ANSI_C \
              parse=NONE \
              sqlcheck=SEMANTICS \
              userid=$(ORACLE_UID)/$(ORACLE_PWD)@$(ORACLE_SID)
# 2016년에 SQLCHECK를 SEMANTICS로 바꿨는데
# DB 접속 안되면 SYNTAX로 해야함
# PROCFLAGS 에 sqlcheck=SYNTAX 로 변경

# 소스/타겟
SRCDIR      = src
SETTLE_PC   = $(SRCDIR)/SETTLE_BAT.pc
SETTLE_C    = $(SRCDIR)/SETTLE_BAT.c
SETTLE_O    = $(SRCDIR)/SETTLE_BAT.o
SETTLE_BIN  = SETTLE_BAT

RPT_PC      = $(SRCDIR)/RPT_DAILY.pc
RPT_C       = $(SRCDIR)/RPT_DAILY.c
RPT_O       = $(SRCDIR)/RPT_DAILY.o
RPT_BIN     = RPT_DAILY

# ============================================
# 타겟
# ============================================
.PHONY: all settle rpt clean

all: settle rpt

settle: $(SETTLE_BIN)

rpt: $(RPT_BIN)

# SETTLE_BAT 빌드
$(SETTLE_BIN): $(SETTLE_O)
	$(CC) $(CFLAGS) -o $@ $< $(LIBS)
	@echo "=== SETTLE_BAT 빌드 완료 ==="

$(SETTLE_O): $(SETTLE_C)
	$(CC) $(CFLAGS) $(INCLUDES) -c -o $@ $<

$(SETTLE_C): $(SETTLE_PC) $(SRCDIR)/common_def.h
	$(PROC) iname=$< oname=$@ $(PROCFLAGS)

# RPT_DAILY 빌드
$(RPT_BIN): $(RPT_O)
	$(CC) $(CFLAGS) -o $@ $< $(LIBS)
	@echo "=== RPT_DAILY 빌드 완료 ==="

$(RPT_O): $(RPT_C)
	$(CC) $(CFLAGS) $(INCLUDES) -c -o $@ $<

$(RPT_C): $(RPT_PC) $(SRCDIR)/common_def.h
	$(PROC) iname=$< oname=$@ $(PROCFLAGS)

clean:
	rm -f $(SRCDIR)/*.c $(SRCDIR)/*.o $(SRCDIR)/*.lis
	rm -f $(SETTLE_BIN) $(RPT_BIN)
	@echo "=== clean 완료 ==="

# 참고: make deploy 는 운영서버에 배포하는 타겟인데
# 요즘은 Jenkins에서 해서 안씀
# deploy:
#	cp $(SETTLE_BIN) /app/batch/bin/
#	cp $(RPT_BIN) /app/batch/bin/
#	chmod 755 /app/batch/bin/SETTLE_BAT
#	chmod 755 /app/batch/bin/RPT_DAILY
