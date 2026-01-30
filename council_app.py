# -*- coding: utf-8 -*-
"""
Council Watcher - FastAPI 앱

지방의회 회의록 비판 분석 자동화 시스템 API 서버

실행 방법:
    uvicorn council_app:app --reload --host 0.0.0.0 --port 8000

API 문서:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 환경 변수 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from council_watcher.api import router as council_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 이벤트 핸들러"""
    # 시작 시
    print("=" * 60)
    print("Council Watcher API 서버 시작")
    print("=" * 60)
    print(f"POCKETBASE_URL: {os.getenv('POCKETBASE_URL', 'Not set')}")
    print(f"GEMINI_API_KEY: {'설정됨' if os.getenv('GEMINI_API_KEY') else 'Not set'}")
    print()

    yield

    # 종료 시
    print("\nCouncil Watcher API 서버 종료")


app = FastAPI(
    title="Council Watcher API",
    description="""
## 지방의회 회의록 비판 분석 자동화 시스템

경기도 31개 시군구 + 경기도의회 회의록을 자동 수집하고,
AI로 비판적 이슈를 추출하여 기사 작성을 지원합니다.

### 주요 기능

- **크롤링**: 지방의회 회의록 자동 수집
- **파싱**: HWP/HTML 회의록 텍스트 추출
- **분석**: Gemini AI를 활용한 이슈 추출
- **저장**: PocketBase에 회의록/이슈 저장

### 사용 가능한 의회

- 용인특례시의회 (yongin)
- 수원시의회 (suwon)
- 성남시의회 (seongnam)
- 화성시의회 (hwaseong)
- 부천시의회 (bucheon)
- 고양시의회 (goyang)
- 안산시의회 (ansan)
- 경기도의회 (gg)
    """,
    version="0.1.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(council_router)


@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "service": "Council Watcher API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    pocketbase_ok = False
    gemini_ok = False

    # PocketBase 연결 테스트
    try:
        from council_watcher.db import PocketBaseClient
        client = PocketBaseClient()
        pocketbase_ok = client.authenticate()
        client.close()
    except Exception as e:
        print(f"PocketBase 연결 오류: {e}")

    # Gemini API 키 확인
    gemini_ok = bool(os.getenv("GEMINI_API_KEY"))

    return {
        "status": "healthy" if (pocketbase_ok and gemini_ok) else "degraded",
        "checks": {
            "pocketbase": "connected" if pocketbase_ok else "disconnected",
            "gemini_api_key": "configured" if gemini_ok else "missing"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
