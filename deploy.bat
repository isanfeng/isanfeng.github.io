@echo off
start /WAIT jekyll build exit
echo "start to move site"
start /WAIT python .\mv_site.py
cd ..
cd .\isanfeng.github.io\
@REM pause