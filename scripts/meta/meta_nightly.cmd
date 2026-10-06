@echo off
REM ============================================================================
REM meta_nightly.cmd - ночной прогон Meta-Cycle (Windows Task Scheduler, 02:30)
REM ----------------------------------------------------------------------------
REM W7: цикл сна (M5-M10) -> один такт демона -> liveness в лог.
REM ВАЖНО (W13, TD-DEV-*): убрать --simulate из cycle, когда появится sleep_git
REM (W1). Сейчас sleep_git НЕТ -> без --simulate cycle упадёт. Держим --simulate
REM до W1 и снимаем его вместе с TD-DEV-* (W13).
REM Лог: .meta_state\meta_nightly_<date>.log
REM ============================================================================
set PY=E:\opencode_harness_portable\.venv\Scripts\python.exe
set META=E:\opencode_harness_portable\scripts\meta
set STATE=E:\opencode_harness_portable\.meta_state
set LOG=%STATE%\meta_nightly.log
(
echo === nightly %DATE% %TIME% ===
"%PY%" "%META%\sleep_integration.py" cycle --task nightly --branches "fix/RULE_REL_01,fix/RULE_CMP_01,fix/RULE_EPI_02" --orchestrator code-orchestrator --no-git --simulate
if errorlevel 1 exit /b 1
"%PY%" "%META%\meta_daemon.py" --once --orchestrator code-orchestrator --state-dir "%STATE%"
if errorlevel 1 exit /b 1
"%PY%" "%META%\sleep_integration.py" liveness --state-dir "%STATE%" --orchestrator code-orchestrator
if errorlevel 1 exit /b 1
) > "%LOG%" 2>&1
exit /b 0
