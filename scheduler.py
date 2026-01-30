# -*- coding: utf-8 -*-
"""
Council Watcher - 스케줄러

정기적으로 회의록을 수집하고 분석하는 스케줄러

실행 방법:
    python scheduler.py

환경 변수:
    GEMINI_API_KEY: Gemini API 키
    POCKETBASE_URL: PocketBase URL
    POCKETBASE_ADMIN_EMAIL: PocketBase 관리자 이메일
    POCKETBASE_ADMIN_PASSWORD: PocketBase 관리자 비밀번호
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import yaml

# 환경 변수 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from council_watcher.crawler.standard import StandardCrawler
from council_watcher.crawler.kms import KMSCrawler
from council_watcher.analyzer.gemini_analyzer import GeminiAnalyzer
from council_watcher.db.pocketbase_client import PocketBaseClient


# 설정 경로
CONFIG_PATH = Path(__file__).parent / "council_watcher" / "config" / "councils.yaml"
PROMPTS_PATH = Path(__file__).parent / "council_watcher" / "config" / "prompts.yaml"


def load_config() -> dict:
    """설정 파일 로드"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_crawler(council_code: str, config: dict):
    """의회 시스템 타입에 맞는 크롤러 반환"""
    system_type = config.get("system_type", "standard")

    if system_type == "kms":
        return KMSCrawler(council_code, config)
    else:
        return StandardCrawler(council_code, config)


async def crawl_and_analyze_council(council_code: str, config: dict, limit: int = 5):
    """
    단일 의회 크롤링 및 분석 실행

    Args:
        council_code: 의회 코드
        config: 의회 설정
        limit: 가져올 회의록 개수
    """
    council_name = config.get("name", council_code)
    print(f"\n[{datetime.now():%Y-%m-%d %H:%M}] {council_name} 처리 시작")

    try:
        # 크롤러 초기화 및 실행
        crawler = get_crawler(council_code, config)
        meetings = await crawler.crawl_all(limit=limit)

        if not meetings:
            print(f"  → 새 회의록 없음")
            return

        print(f"  → {len(meetings)}개 회의록 발견")

        # DB 클라이언트 초기화
        db_client = PocketBaseClient()
        if not db_client.authenticate():
            print(f"  → DB 인증 실패")
            return

        # 분석기 초기화
        analyzer = GeminiAnalyzer(config_path=PROMPTS_PATH)

        # 각 회의록 처리
        new_count = 0
        issue_count = 0

        for meeting in meetings:
            # 중복 체크
            existing = db_client.get_meeting(
                council_code,
                meeting.title,
                meeting.meeting_date
            )

            if existing:
                continue

            # 회의록 저장
            meeting_data = {
                "council_code": meeting.council_code,
                "session": meeting.session,
                "meeting_type": meeting.meeting_type,
                "meeting_date": meeting.meeting_date.isoformat(),
                "title": meeting.title,
                "source_url": meeting.source_url,
                "raw_text": meeting.raw_text or ""
            }

            saved = db_client.create_meeting(meeting_data)
            if not saved:
                continue

            new_count += 1

            # AI 분석
            if meeting.raw_text and len(meeting.raw_text) > 100:
                result = analyzer.analyze(meeting.raw_text, council_name)

                if not result.error and result.issues:
                    saved_issues = db_client.save_analysis_result(saved["id"], result)
                    issue_count += len(saved_issues)
                    print(f"    - {meeting.title[:30]}... → {len(saved_issues)}개 이슈")

        db_client.close()
        print(f"  → 완료: 새 회의록 {new_count}개, 이슈 {issue_count}개")

    except Exception as e:
        print(f"  → 오류: {e}")


async def run_daily_job():
    """
    매일 실행되는 전체 의회 크롤링 작업
    """
    print("\n" + "=" * 60)
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 일일 회의록 수집 시작")
    print("=" * 60)

    config = load_config()
    councils = config.get("councils", {})

    for code, council_config in councils.items():
        if not council_config.get("is_active", False):
            continue

        await crawl_and_analyze_council(code, council_config, limit=5)

        # API 호출 제한 방지
        await asyncio.sleep(5)

    print("\n" + "=" * 60)
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 일일 회의록 수집 완료")
    print("=" * 60)


async def run_single_council(council_code: str, limit: int = 10):
    """
    단일 의회 수동 실행

    Args:
        council_code: 의회 코드
        limit: 회의록 개수
    """
    config = load_config()
    councils = config.get("councils", {})

    if council_code not in councils:
        print(f"알 수 없는 의회 코드: {council_code}")
        print(f"사용 가능한 코드: {list(councils.keys())}")
        return

    await crawl_and_analyze_council(council_code, councils[council_code], limit)


def main():
    """스케줄러 메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Council Watcher 스케줄러")
    parser.add_argument("--run-now", action="store_true",
                        help="즉시 전체 수집 실행")
    parser.add_argument("--council", type=str,
                        help="특정 의회만 수집 (예: yongin)")
    parser.add_argument("--limit", type=int, default=10,
                        help="수집할 회의록 개수 (기본: 10)")
    parser.add_argument("--daemon", action="store_true",
                        help="데몬 모드로 실행 (스케줄 기반)")

    args = parser.parse_args()

    print("=" * 60)
    print("Council Watcher - 스케줄러")
    print("=" * 60)
    print(f"POCKETBASE_URL: {os.getenv('POCKETBASE_URL', 'Not set')}")
    print(f"GEMINI_API_KEY: {'설정됨' if os.getenv('GEMINI_API_KEY') else 'Not set'}")
    print()

    if args.council:
        # 특정 의회만 즉시 실행
        print(f"[모드] {args.council} 의회 수집")
        asyncio.run(run_single_council(args.council, args.limit))

    elif args.run_now:
        # 전체 의회 즉시 실행
        print("[모드] 전체 의회 즉시 수집")
        asyncio.run(run_daily_job())

    elif args.daemon:
        # 데몬 모드 - 스케줄 기반 실행
        print("[모드] 데몬 모드 (스케줄 기반)")
        print("스케줄: 매일 06:00 전체 수집")
        print("종료하려면 Ctrl+C를 누르세요.\n")

        scheduler = AsyncIOScheduler()

        # 매일 새벽 6시 실행
        scheduler.add_job(
            run_daily_job,
            CronTrigger(hour=6, minute=0),
            id="daily_crawl",
            name="일일 회의록 수집"
        )

        scheduler.start()

        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            print("\n스케줄러 종료")
            scheduler.shutdown()

    else:
        # 도움말 출력
        parser.print_help()
        print("\n예시:")
        print("  python scheduler.py --run-now          # 전체 의회 즉시 수집")
        print("  python scheduler.py --council yongin   # 용인시의회만 수집")
        print("  python scheduler.py --daemon           # 스케줄 기반 데몬 실행")


if __name__ == "__main__":
    main()
