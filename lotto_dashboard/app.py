import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    # 항상 8080 포트로 실행 (환경변수 PORT 있으면 우선)
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
