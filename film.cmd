@echo off
rem Launcher of the film tool (.claude/skills/film/scripts/film.py): film new <nom>, film liste, film --help
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0.claude\skills\film\scripts\film.py" %*
) else (
  python "%~dp0.claude\skills\film\scripts\film.py" %*
)
exit /b %errorlevel%
