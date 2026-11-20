@echo off
title Push Sales Grading Module ke GitHub
color 0A
cls
echo ======================================================================
echo          MENGIRIM MODUL SALES GRADING KE GITHUB
echo ======================================================================
echo Target Repo: https://github.com/hrdastongraphindo-arch/grading-sales.git
echo.
cd /d "C:\Users\Aston Graphindo\.gemini\antigravity\scratch\sales_grading_triwulan_github"

echo Menjalankan: git push -u origin main ...
echo.
git push -u origin main

if %ERRORLEVEL% equ 0 (
    echo.
    echo ======================================================================
    echo [BERHASIL!] Seluruh file dan modul telah berhasil di-upload ke GitHub!
    echo.
    echo Silakan buka tab Chrome Anda di:
    echo https://github.com/hrdastongraphindo-arch/grading-sales
    echo lalu tekan Refresh (F5).
    echo ======================================================================
) else (
    echo.
    echo ======================================================================
    echo [PERHATIAN] Jika tadi muncul popup login dari GitHub / browser:
    echo Silakan klik "Sign in with your browser" dan izinkan akses.
    echo Lalu ulangi jalankan file ini sekali lagi.
    echo ======================================================================
)

echo.
pause
