git stash
git pull --ff
source .venv/Scripts/activate
pip install -r requirements.txt
python3 manage.py migrate

