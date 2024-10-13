@echo on
REM Stash changes in Git
git stash

REM Pull the latest changes with fast-forward
git pull --ff

REM Activate the virtual environment
call .venv\Scripts\activate

REM Install required packages
pip install -r requirements.txt

REM Run migrations
python manage.py migrate

pause
