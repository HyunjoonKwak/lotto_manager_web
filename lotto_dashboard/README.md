# Lotto Dashboard (Flask)

동행복권(로또 6/45) 데이터 수집/분석/추천 및 1등 당첨점 조회.

## 설치 요약 (NAS 터미널)
```bash
ROOT="/volume1/code_work/lotto_dashboard"
mkdir -p "$ROOT"
python3 -m venv "$ROOT/.venv"
source "$ROOT/.venv/bin/activate"
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
python scripts/update_data.py --fetch-all
export FLASK_APP=app
flask run --host=0.0.0.0 --port=8000
```
