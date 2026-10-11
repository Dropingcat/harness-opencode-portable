@echo off
REM ============================================================================
REM meta_nightly.cmd - ночной прогон Meta-Cycle (Windows Task Scheduler, 02:30)
REM ----------------------------------------------------------------------------
REM W7: цикл сна (M5-M10) -> один такт демона -> liveness в лог.
REM W13 (RUD-7): --simulate СНЯТ — sleep_git.py теперь реальный (W13-T1 закрыл
REM дыры-1/2: конфликтные ветки KEEP, рефлексия в отчёте). Ночной прогон
REM гитирует сны по-настоящему (simulated:false, проверяется W13-T4).
REM W13-r2 (TD-W13-3): целевую ветку НЕ задаём жёстко — run_sleep_cycle сам
REM резолвит стабильную ветку (master > develop > main) через
REM sleep_git.resolve_default_target. Сон НЕ вливается в feature-ветку разработки.
REM W13-r2 (TD-W13-2): ночной task_id содержит дату (nightly-YYYYMMDD) — каждый
REM прогон уникален, baseline-тег/ветки/отчёт не конфликтуют с прошлой ночью.
REM Отчёт сна пишется в .runs\sleep_reports\<task>.json (sleep_git.write_report);
REM конфликтные уроки -> .l2_memory\ + .runs\sleep_reports\conflicts_<date>.json.
REM Лог: .meta_state\meta_nightly_<date>.log
REM ============================================================================
set PY=E:\opencode_harness_portable\.venv\Scripts\python.exe
set META=E:\opencode_harness_portable\scripts\meta
set STATE=E:\opencode_harness_portable\.meta_state
set LOG=%STATE%\meta_nightly.log
for /f "tokens=1-3 delims=/- " %%a in ('echo %DATE%') do set NIGHTLY_TASK=nightly-%%a%%b%%c
(
echo === nightly %DATE% %TIME% ===
"%PY%" "%META%\sleep_integration.py" cycle --task-id "%NIGHTLY_TASK%" --branches "fix/RULE_REL_01,fix/RULE_CMP_01,fix/RULE_EPI_02" --orchestrator code-orchestrator --no-git
if errorlevel 1 exit /b 1
"%PY%" "%META%\meta_daemon.py" --once --orchestrator code-orchestrator --state-dir "%STATE%"
if errorlevel 1 exit /b 1
"%PY%" "%META%\sleep_integration.py" liveness --state-dir "%STATE%" --orchestrator code-orchestrator
if errorlevel 1 exit /b 1
) > "%LOG%" 2>&1
exit /b 0
