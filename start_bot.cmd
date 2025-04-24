@echo off
echo Fixing dependencies...
pip uninstall -y googletrans
pip uninstall -y translate

echo Installing compatible packages...
pip install -r requirements.txt

echo.
echo Starting bot...
python bot.py 