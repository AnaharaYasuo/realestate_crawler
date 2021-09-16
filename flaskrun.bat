@echo off
set api_url=%1
@echo on
@echo %api_url%
@echo off

start /b curl %api_url%

exit
