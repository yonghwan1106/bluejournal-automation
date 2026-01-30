"""
표준 지방의회 시스템 크롤러

대부분의 시군구 의회에서 사용하는 표준 시스템용 크롤러입니다.
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.async_api import async_playwright, Browser, Page

from .base import BaseCrawler, MeetingInfo


class StandardCrawler(BaseCrawler):
    """
    표준 지방의회 시스템 크롤러

    - 회의록 목록 페이지 크롤링
    - 상세 페이지 텍스트 추출
    - HWP 파일 다운로드
    """

    def __init__(self, council_code: str, config: dict):
        super().__init__(council_code, config)
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def _init_browser(self):
        """Playwright 브라우저 초기화"""
        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            # User-Agent 설정
            await self.page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

    async def _close_browser(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None

    async def get_recent_meetings(self, limit: int = 10) -> list[MeetingInfo]:
        """
        최근 회의록 목록 가져오기

        Args:
            limit: 가져올 최대 개수

        Returns:
            MeetingInfo 목록
        """
        await self._init_browser()
        meetings = []

        try:
            # 최근 회의록 페이지로 이동
            recent_url = self.build_url("recent")
            await self.page.goto(recent_url, wait_until="networkidle")
            await asyncio.sleep(1)  # 페이지 로드 대기

            # 테이블에서 회의록 목록 추출
            list_selector = self.selectors.get("list_table", "table tbody tr")
            rows = await self.page.query_selector_all(list_selector)

            for i, row in enumerate(rows[:limit]):
                try:
                    # 제목 추출
                    title_selector = self.selectors.get("title", "td.subject a")
                    title_elem = await row.query_selector(title_selector)
                    if not title_elem:
                        continue

                    title = await title_elem.inner_text()
                    title = title.strip()

                    # 링크 추출
                    href = await title_elem.get_attribute("href")
                    if href:
                        source_url = urljoin(self.base_url, href)
                    else:
                        source_url = ""

                    # 날짜 추출
                    date_selector = self.selectors.get("date", "td:nth-child(4)")
                    date_elem = await row.query_selector(date_selector)
                    meeting_date = datetime.now()
                    if date_elem:
                        date_text = await date_elem.inner_text()
                        date_text = date_text.strip()
                        # 다양한 날짜 형식 파싱
                        for fmt in ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]:
                            try:
                                meeting_date = datetime.strptime(date_text[:10], fmt)
                                break
                            except ValueError:
                                continue

                    # 회의 정보 생성
                    meeting = MeetingInfo(
                        council_code=self.council_code,
                        session=self.parse_session(title),
                        meeting_type=self.parse_meeting_type(title),
                        meeting_date=meeting_date,
                        title=title,
                        source_url=source_url
                    )
                    meetings.append(meeting)

                except Exception as e:
                    print(f"행 파싱 오류: {e}")
                    continue

        except Exception as e:
            print(f"회의록 목록 크롤링 오류: {e}")

        return meetings

    async def get_meeting_detail(self, meeting_info: MeetingInfo) -> MeetingInfo:
        """
        회의록 상세 정보 및 텍스트 추출

        Args:
            meeting_info: 회의 기본 정보

        Returns:
            raw_text가 채워진 MeetingInfo
        """
        await self._init_browser()

        try:
            # 상세 페이지로 이동
            await self.page.goto(meeting_info.source_url, wait_until="networkidle")
            await asyncio.sleep(1)

            # 본문 텍스트 추출
            content_selector = self.selectors.get("detail_content", "div.view_content")
            content_elem = await self.page.query_selector(content_selector)

            if content_elem:
                meeting_info.raw_text = await content_elem.inner_text()
            else:
                # 전체 본문에서 추출 시도
                meeting_info.raw_text = await self.page.inner_text("body")

            # 첨부파일 링크 추출
            file_selector = self.selectors.get("file_download", "a[href*='download']")
            file_links = await self.page.query_selector_all(file_selector)

            for link in file_links:
                href = await link.get_attribute("href")
                if href:
                    file_url = urljoin(self.base_url, href)
                    # HWP 파일만 추가
                    if ".hwp" in file_url.lower() or "download" in file_url.lower():
                        meeting_info.file_urls.append(file_url)

        except Exception as e:
            print(f"상세 페이지 크롤링 오류: {e}")

        return meeting_info

    async def download_file(self, file_url: str, download_dir: Path) -> Optional[Path]:
        """
        회의록 파일 다운로드

        Args:
            file_url: 파일 다운로드 URL
            download_dir: 저장 디렉토리

        Returns:
            다운로드된 파일 경로 또는 None
        """
        await self._init_browser()
        download_dir = Path(download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 다운로드 대기 설정
            async with self.page.expect_download() as download_info:
                await self.page.goto(file_url)

            download = await download_info.value

            # 파일 저장
            suggested_filename = download.suggested_filename
            file_path = download_dir / suggested_filename
            await download.save_as(file_path)

            return file_path

        except Exception as e:
            print(f"파일 다운로드 오류: {e}")
            # curl 대체 시도
            return await self._download_with_curl(file_url, download_dir)

    async def _download_with_curl(self, file_url: str, download_dir: Path) -> Optional[Path]:
        """curl을 사용한 대체 다운로드"""
        import subprocess

        # URL에서 파일명 추출
        parsed = urlparse(file_url)
        params = parse_qs(parsed.query)

        filename = "meeting.hwp"
        if "filename" in params:
            filename = params["filename"][0]
        elif "q_fileSn" in params:
            filename = f"meeting_{params['q_fileSn'][0]}.hwp"

        file_path = download_dir / filename

        try:
            result = subprocess.run(
                ["curl", "-k", "-o", str(file_path), file_url,
                 "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"],
                capture_output=True,
                timeout=60
            )

            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
            return None

        except Exception as e:
            print(f"curl 다운로드 오류: {e}")
            return None

    async def crawl_all(self, limit: int = 10, download_dir: Optional[Path] = None) -> list[MeetingInfo]:
        """
        전체 크롤링 프로세스 실행

        Args:
            limit: 최대 회의록 개수
            download_dir: 파일 다운로드 디렉토리 (None이면 다운로드 안함)

        Returns:
            완료된 MeetingInfo 목록
        """
        try:
            # 1. 회의록 목록 가져오기
            meetings = await self.get_recent_meetings(limit)
            print(f"{self.name}: {len(meetings)}개 회의록 발견")

            # 2. 각 회의록 상세 정보 가져오기
            for i, meeting in enumerate(meetings):
                print(f"  [{i+1}/{len(meetings)}] {meeting.title[:30]}...")
                meeting = await self.get_meeting_detail(meeting)

                # 3. 파일 다운로드 (옵션)
                if download_dir and meeting.file_urls:
                    council_dir = download_dir / self.council_code
                    for file_url in meeting.file_urls:
                        await self.download_file(file_url, council_dir)

                await asyncio.sleep(0.5)  # 서버 부하 방지

            return meetings

        finally:
            await self._close_browser()
