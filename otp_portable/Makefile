# OTP Portable — Makefile
# Usage: make            (build)
#        make test       (build + test)
#        make clean      (remove build artifacts)
#        make doctor     (show feature discovery)
#
# Cross-compile:
#   make CC=gcc          (GCC)
#   make CC=clang        (Clang)
#   make CC=tcc          (Tiny C Compiler)
#   make CC=cl           (MSVC)
#   make CFLAGS="-DOTP_HAVE_SOCKETS=1"   (enable sockets)

CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra -pedantic -std=c89
LDFLAGS ?=

# Feature flags (uncomment to enable)
# CFLAGS += -DOTP_HAVE_SQLITE=1
# CFLAGS += -DOTP_HAVE_SOCKETS=1
# CFLAGS += -DOTP_HAVE_TLS=1

# Source
SRC = otp_portable.c
OUT = otp

.PHONY: all test clean doctor fixtures

all: $(OUT)

$(OUT): $(SRC) otp_portable.h
	$(CC) $(CFLAGS) $(LDFLAGS) -o $(OUT) $(SRC)
	@echo "Built: $(OUT)"

doctor: $(OUT)
	./$(OUT) doctor

test: $(OUT) fixtures
	@echo "=== Running OTP Portable tests ==="
	@echo ""
	@echo "--- Doctor ---"
	./$(OUT) doctor
	@echo ""
	@echo "--- Version ---"
	./$(OUT) version
	@echo ""
	@echo "--- Run dispatch.csv ---"
	./$(OUT) run test_fixtures/dispatch.csv
	@echo ""
	@echo "=== All tests passed ==="

fixtures:
	@mkdir -p test_fixtures
	@echo "TRIP_NUMBER,LS_LEG_ID,LS_EXPECTED_DATE,DELIVER_BY,LS_LAST_FB_STATUS_DATE,STATUS" > test_fixtures/dispatch.csv
	@echo "TRIP-001,LEG-001A,2026-09-10T14:00:00Z,2026-09-10T14:30:00Z,2026-09-10T13:55:00Z,IN_TRANSIT" >> test_fixtures/dispatch.csv
	@echo "TRIP-001,LEG-001B,2026-09-10T15:00:00Z,2026-09-10T15:30:00Z,2026-09-10T14:55:00Z,IN_TRANSIT" >> test_fixtures/dispatch.csv
	@echo "TRIP-002,LEG-002A,2026-09-10T16:00:00Z,2026-09-10T16:30:00Z,2026-09-10T15:55:00Z,DELIVERED" >> test_fixtures/dispatch.csv

clean:
	rm -f $(OUT) $(OUT).exe *.o *.obj
	@echo "Cleaned"
