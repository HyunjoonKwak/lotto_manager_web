# Flask Starter

## Quickstart

로컬 실행:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

- App factory: `app.create_app`
- Dev server: `http://127.0.0.1:5000`
- Health: `GET /health`

## Config

기본값은 개발용 설정입니다. 배포 시 `SECRET_KEY`를 환경 변수 또는 별도 설정으로 교체하세요.
