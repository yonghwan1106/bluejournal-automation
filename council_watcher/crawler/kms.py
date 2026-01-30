"""
경기도의회 KMS 시스템 크롤러

경기도의회 회의록관리시스템(KMS) 전용 크롤러입니다.
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, Page

from .base import BaseCrawler, MeetingInfo


class KMSCrawler(BaseCrawler):
    """
    경기도의회 KMS 시스템 크롤러

    - KMS 회의록 뷰어에서 텍스트 추출
    - HTML 기반 회의록 처리
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

        KMS 시스템의 최근 회의록 페이지에서 목록 추출
        """
        await self._init_browser()
        meetings = []

        try:
            recent_url = self.build_url("recent")
            await self.page.goto(recent_url, wait_until="networkidle")
            await asyncio.sleep(2)

            # KMS 테이블 구조 파싱
            list_selector = self.selectors.get("list_table", "table.tb_type01 tbody tr")
            rows = await self.page.query_selector_all(list_selector)

            for i, row in enumerate(rows[:limit]):
                try:
                    # 제목과 링크 추출
                    title_elem = await row.query_selector("td a")
                    if not title_elem:
                        continue

                    title = await title_elem.inner_text()
                    title = title.strip()

                    # onclick에서 회의록 ID 추출
                    onclick = await title_elem.get_attribute("onclick")
                    meeting_id = self._extract_meeting_id(onclick)

                    if meeting_id:
                        source_url = f"{self.base_url}/cms/mntsViewer.do?mntsId={meeting_id}"
                    else:
                        href = await title_elem.get_attribute("href")
                        source_url = urljoin(self.base_url, href) if href else ""

                    # 날짜 추출 (KMS는 보통 3번째 컬럼)
                    date_cells = await row.query_selector_all("td")
                    meeting_date = datetime.now()
                    if len(date_cells) >= 3:
                        date_text = await date_cells[2].inner_text()
                        date_text = date_text.strip()
                        for fmt in ["%Y-%m-%d", "%Y.%m.%d"]:
                            try:
                                meeting_date = datetime.strptime(date_text[:10], fmt)
                                break
                            except ValueError:
                                continue

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
                    print(f"KMS 행 파싱 오류: {e}")
                    continue

        except Exception as e:
            print(f"KMS 회의록 목록 크롤링 오류: {e}")

        return meetings

    def _extract_meeting_id(self, onclick: str) -> Optional[str]:
        """onclick 속성에서 회의록 ID 추출"""
        if not onclick:
            return None

        # 다양한 패턴 시도
        patterns = [
            r"mntsId['\"]?\s*[,:=]\s*['\"]?(\w+)",
            r"viewMnts\(['\"]?(\w+)",
            r"openViewer\(['\"]?(\w+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, onclick)
            if match:
                return match.group(1)

        return None

    async def get_meeting_detail(self, meeting_info: MeetingInfo) -> MeetingInfo:
        """
        KMS 뷰어에서 회의록 텍스트 추출

        KMS는 iframe 기반 뷰어를 사용하므로 별도 처리 필요
        """
        await self._init_browser()

        try:
            await self.page.goto(meeting_info.source_url, wait_until="networkidle")
            await asyncio.sleep(2)

            # KMS 뷰어는 여러 iframe을 사용할 수 있음
            # 메인 콘텐츠 영역 찾기
            content_selectors = [
                "div.view_content",
                "div.mnts_content",
                "div#mntsContent",
                "iframe[name='mntsViewer']",
            ]

            raw_text = ""

            for selector in content_selectors:
                try:
                    if "iframe" in selector:
                        # iframe 내부 콘텐츠 추출
                        frame = self.page.frame_locator(selector)
                        raw_text = await frame.locator("body").inner_text()
                    else:
                        elem = await self.page.query_selector(selector)
                        if elem:
                            raw_text = await elem.inner_text()

                    if raw_text and len(raw_text) > 100:
                        break
                except Exception:
                    continue

            # 텍스트가 없으면 전체 페이지에서 추출
            if not raw_text or len(raw_text) < 100:
                raw_text = await self.page.inner_text("body")

            meeting_info.raw_text = self._clean_kms_text(raw_text)

        except Exception as e:
            print(f"KMS 상세 페이지 크롤링 오류: {e}")

        return meeting_info

    def _clean_kms_text(self, text: str) -> str:
        """KMS 회의록 텍스트 정리"""
        if not text:
            return ""

        # 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', text)

        # 네비게이션 텍스트 제거
        remove_patterns = [
            r'이전\s*다음',
            r'목록으로',
            r'인쇄하기',
            r'처음으로',
        ]

        for pattern in remove_patterns:
            text = re.sub(pattern, '', text)

        return text.strip()

    async def download_file(self, file_url: str, download_dir: Path) -> Optional[Path]:
        """
        KMS는 HTML 뷰어 방식이므로 파일 다운로드 대신 텍스트 저장
        """
        # KMS는 파일 다운로드 대신 텍스트로 저장
        return None

    async def crawl_all(self, limit: int = 10, download_dir: Optional[Path] = None) -> list[MeetingInfo]:
        """전체 크롤링 프로세스 실행"""
        try:
            meetings = await self.get_recent_meetings(limit)
            print(f"{self.name}: {len(meetings)}개 회의록 발견")

            for i, meeting in enumerate(meetings):
                print(f"  [{i+1}/{len(meetings)}] {meeting.title[:30]}...")
                meeting = await self.get_meeting_detail(meeting)
                await asyncio.sleep(1)  # KMS 서버 부하 방지

            return meetings

        finally:
            await self._close_browser()
