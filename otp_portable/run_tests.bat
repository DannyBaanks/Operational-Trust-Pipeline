@echo off
REM OTP Portable — Windows test script
REM Usage: run_tests.bat

echo ========================================
echo OTP Portable %OTP_VERSION% — Windows Tests
echo ========================================
echo.

echo --- Build ---
cl /nologo /W4 /WX /std:c89 /Fe:otp.exe otp_portable.c
if %ERRORLEVEL% neq 0 (
    echo BUILD FAILED
    exit /b 1
)
echo Build OK
echo.

echo --- Doctor ---
otp.exe doctor
echo.

echo --- Version ---
otp.exe version
echo.

echo --- Run dispatch.csv ---
otp.exe run test_fixtures\dispatch.csv
echo.

echo ========================================
echo All tests passed
echo ========================================
