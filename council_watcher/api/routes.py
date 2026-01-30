"""
FastAPI 라우터

회의록 크롤링 및 분석 API 엔드포인트
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

import yaml

from ..crawler.standard import StandardCrawler
from ..crawler.kms import KMSCrawler
from ..parser.hwp_parser import HWPParser
from ..parser.chunker import MeetingChunker
from ..analyzer.gemini_analyzer import GeminiAnalyzer
from ..db.pocketbase_client import PocketBaseClient


router = APIRouter(prefix="/api/council", tags=["council-watcher"])

# 설정 로드
CONFIG_PATH = Path(__file__).parent.parent / "config" / "councils.yaml"
PROMPTS_PATH = Path(__file__).parent.parent / "config" / "prompts.yaml"


def load_council_config(council_code: str) -> dict:
    """의회 설정 로드"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    councils = config.get("councils", {})
    if council_code not in councils:
        raise HTTPException(status_code=404, detail=f"의회 코드를 찾을 수 없습니다: {council_code}")

    return councils[council_code]


def get_crawler(council_code: str, config: dict):
    """의회 시스템 타입에 맞는 크롤러 반환"""
    system_type = config.get("system_type", "standard")

    if system_type == "kms":
        return KMSCrawler(council_code, config)
    else:
        return StandardCrawler(council_code, config)


# ========== Request/Response Models ==========

class CrawlResponse(BaseModel):
    success: bool
    council_code: str
    council_name: str
    meetings_found: int
    meetings: list[dict] = []
    message: str = ""


class AnalyzeResponse(BaseModel):
    success: bool
    meeting_id: str
    issues_found: int
    issues: list[dict] = []
    summary: str = ""
    message: str = ""


class IssueResponse(BaseModel):
    id: str
    meeting_id: str
    severity: str
    topic: str
    conflict_summary: str
    key_quote: str
    fact_check_point: str
    is_used: bool
    created: str


# ========== Endpoints ==========

@router.get("/councils")
async def list_councils():
    """활성화된 의회 목록 조회"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        councils = []
        for code, data in config.get("councils", {}).items():
            if data.get("is_active", False):
                councils.append({
                    "code": code,
                    "name": data.get("name", code),
                    "system_type": data.get("system_type", "standard"),
                    "base_url": data.get("base_url", "")
                })

        return {"councils": councils, "total": len(councils)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl/{council_code}", response_model=CrawlResponse)
async def crawl_council(
    council_code: str,
    limit: int = Query(default=10, ge=1, le=50),
    save_to_db: bool = Query(default=True)
):
    """
    특정 의회 회의록 크롤링

    - council_code: 의회 코드 (예: yongin, suwon, gg)
    - limit: 가져올 최대 회의록 개수
    - save_to_db: PocketBase에 저장 여부
    """
    try:
        config = load_council_config(council_code)
        crawler = get_crawler(council_code, config)

        # 크롤링 실행
        meetings = await crawler.crawl_all(limit=limit)

        meetings_data = []
        db_client = None

        if save_to_db:
            db_client = PocketBaseClient()
            db_client.authenticate()

        for meeting in meetings:
            meeting_dict = {
                "council_code": meeting.council_code,
                "session": meeting.session,
                "meeting_type": meeting.meeting_type,
                "meeting_date": meeting.meeting_date.isoformat(),
                "title": meeting.title,
                "source_url": meeting.source_url,
                "raw_text_length": len(meeting.raw_text) if meeting.raw_text else 0
            }

            if save_to_db and db_client:
                # 중복 체크
                existing = db_client.get_meeting(
                    council_code,
                    meeting.title,
                    meeting.meeting_date
                )

                if not existing:
                    db_data = {
                        "council_code": meeting.council_code,
                        "session": meeting.session,
                        "meeting_type": meeting.meeting_type,
                        "meeting_date": meeting.meeting_date.isoformat(),
                        "title": meeting.title,
                        "source_url": meeting.source_url,
                        "raw_text": meeting.raw_text or ""
                    }
                    saved = db_client.create_meeting(db_data)
                    if saved:
                        meeting_dict["id"] = saved.get("id")
                        meeting_dict["saved"] = True
                else:
                    meeting_dict["id"] = existing.get("id")
                    meeting_dict["saved"] = False
                    meeting_dict["message"] = "이미 존재하는 회의록"

            meetings_data.append(meeting_dict)

        if db_client:
            db_client.close()

        return CrawlResponse(
            success=True,
            council_code=council_code,
            council_name=config.get("name", council_code),
            meetings_found=len(meetings),
            meetings=meetings_data,
            message=f"{len(meetings)}개 회의록 수집 완료"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/{meeting_id}", response_model=AnalyzeResponse)
async def analyze_meeting(
    meeting_id: str,
    save_to_db: bool = Query(default=True)
):
    """
    특정 회의록 AI 분석

    - meeting_id: PocketBase meetings 컬렉션의 레코드 ID
    - save_to_db: 분석 결과를 issues 컬렉션에 저장 여부
    """
    try:
        # DB에서 회의록 조회
        db_client = PocketBaseClient()
        db_client.authenticate()

        # 회의록 조회 (직접 API 호출)
        response = db_client.client.get(
            f"{db_client.base_url}/api/collections/meetings/records/{meeting_id}",
            headers=db_client._get_headers()
        )

        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="회의록을 찾을 수 없습니다.")

        meeting = response.json()
        raw_text = meeting.get("raw_text", "")

        if not raw_text or len(raw_text) < 100:
            raise HTTPException(status_code=400, detail="분석할 텍스트가 없습니다.")

        # AI 분석 실행
        analyzer = GeminiAnalyzer(config_path=PROMPTS_PATH)
        council_name = meeting.get("council_code", "")
        result = analyzer.analyze(raw_text, council_name)

        if result.error:
            raise HTTPException(status_code=500, detail=result.error)

        # 결과 저장
        issues_data = []
        if save_to_db:
            saved_issues = db_client.save_analysis_result(meeting_id, result)
            for issue in saved_issues:
                issues_data.append({
                    "id": issue.get("id"),
                    "severity": issue.get("severity"),
                    "topic": issue.get("topic"),
                    "conflict_summary": issue.get("conflict_summary"),
                    "key_quote": issue.get("key_quote"),
                    "fact_check_point": issue.get("fact_check_point")
                })
        else:
            for issue in result.issues:
                issues_data.append({
                    "severity": issue.severity,
                    "topic": issue.topic,
                    "conflict_summary": issue.conflict_summary,
                    "key_quote": issue.key_quote,
                    "fact_check_point": issue.fact_check_point
                })

        db_client.close()

        return AnalyzeResponse(
            success=True,
            meeting_id=meeting_id,
            issues_found=len(result.issues),
            issues=issues_data,
            summary=result.summary,
            message=f"{len(result.issues)}개 이슈 발견"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues")
async def list_issues(
    council_code: Optional[str] = None,
    severity: Optional[str] = None,
    is_used: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    분석된 이슈 목록 조회

    - council_code: 의회 코드로 필터링 (선택)
    - severity: 중요도로 필터링 (상/중/하)
    - is_used: 기사화 여부로 필터링
    """
    try:
        db_client = PocketBaseClient()
        db_client.authenticate()

        issues = db_client.get_issues(
            severity=severity,
            is_used=is_used,
            limit=limit,
            offset=offset
        )

        db_client.close()

        return {
            "issues": issues,
            "total": len(issues),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues/{issue_id}")
async def get_issue(issue_id: str):
    """이슈 상세 조회"""
    try:
        db_client = PocketBaseClient()
        db_client.authenticate()

        response = db_client.client.get(
            f"{db_client.base_url}/api/collections/issues/records/{issue_id}",
            headers=db_client._get_headers()
        )

        db_client.close()

        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다.")

        return response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/issues/{issue_id}/mark-used")
async def mark_issue_used(issue_id: str):
    """이슈를 기사화됨으로 표시"""
    try:
        db_client = PocketBaseClient()
        db_client.authenticate()

        result = db_client.mark_issue_used(issue_id)
        db_client.close()

        if not result:
            raise HTTPException(status_code=404, detail="이슈를 찾을 수 없습니다.")

        return {"success": True, "issue_id": issue_id, "is_used": True}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meetings")
async def list_meetings(
    council_code: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """저장된 회의록 목록 조회"""
    try:
        db_client = PocketBaseClient()
        db_client.authenticate()

        meetings = db_client.get_meetings(
            council_code=council_code,
            limit=limit,
            offset=offset
        )

        db_client.close()

        return {
            "meetings": meetings,
            "total": len(meetings),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl-and-analyze/{council_code}")
async def crawl_and_analyze(
    council_code: str,
    background_tasks: BackgroundTasks,
    limit: int = Query(default=5, ge=1, le=20)
):
    """
    크롤링 + 분석 일괄 실행 (백그라운드)

    크롤링 후 각 회의록을 자동으로 AI 분석합니다.
    """
    try:
        config = load_council_config(council_code)

        async def process_task():
            crawler = get_crawler(council_code, config)
            meetings = await crawler.crawl_all(limit=limit)

            db_client = PocketBaseClient()
            db_client.authenticate()
            analyzer = GeminiAnalyzer(config_path=PROMPTS_PATH)

            results = []
            for meeting in meetings:
                # 저장
                db_data = {
                    "council_code": meeting.council_code,
                    "session": meeting.session,
                    "meeting_type": meeting.meeting_type,
                    "meeting_date": meeting.meeting_date.isoformat(),
                    "title": meeting.title,
                    "source_url": meeting.source_url,
                    "raw_text": meeting.raw_text or ""
                }
                saved = db_client.create_meeting(db_data)

                if saved and meeting.raw_text:
                    # 분석
                    result = analyzer.analyze(meeting.raw_text, config.get("name", ""))
                    if not result.error:
                        db_client.save_analysis_result(saved["id"], result)
                        results.append({
                            "meeting_id": saved["id"],
                            "title": meeting.title,
                            "issues_found": len(result.issues)
                        })

            db_client.close()
            return results

        # 백그라운드로 실행
        background_tasks.add_task(process_task)

        return {
            "success": True,
            "message": f"{council_code} 크롤링 및 분석 작업이 시작되었습니다.",
            "council_name": config.get("name", council_code),
            "limit": limit
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
