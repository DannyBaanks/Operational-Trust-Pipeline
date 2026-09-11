#!/bin/sh
# OTP Portable — Unix test script
# Usage: ./run_tests.sh

set -e

echo "========================================"
echo "OTP Portable — Unix Tests"
echo "========================================"
echo ""

echo "--- Build ---"
cc -O2 -Wall -Wextra -pedantic -std=c89 -o otp otp_portable.c
echo "Build OK"
echo ""

echo "--- Doctor ---"
./otp doctor
echo ""

echo "--- Version ---"
./otp version
echo ""

echo "--- Run dispatch.csv ---"
./otp run test_fixtures/dispatch.csv
echo ""

echo "========================================"
echo "All tests passed"
echo "========================================"
