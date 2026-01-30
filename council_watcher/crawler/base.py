"""
크롤러 추상 클래스 - 모든 의회 크롤러의 기본 인터페이스
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from pathlib import Path


@dataclass
class MeetingInfo:
    """회의 정보 데이터 클래스"""
    council_code: str
    session: int  # 회기
    meeting_type: str  # 본회의, 상임위, 특별위
    meeting_date: datetime
    title: str
    source_url: str
    file_urls: list[str] = None
    raw_text: Optional[str] = None

    def __post_init__(self):
        if self.file_urls is None:
            self.file_urls = []


class BaseCrawler(ABC):
    """
    크롤러 추상 기본 클래스

    모든 의회별 크롤러는 이 클래스를 상속받아 구현합니다.
    """

    def __init__(self, council_code: str, config: dict):
        """
        Args:
            council_code: 의회 코드 (예: 'yongin', 'suwon')
            config: councils.yaml에서 로드한 의회별 설정
        """
        self.council_code = council_code
        self.config = config
        self.name = config.get("name", council_code)
        self.base_url = config.get("base_url", "")
        self.endpoints = config.get("endpoints", {})
        self.selectors = config.get("selectors", {})
        self.file_format = config.get("file_format", "hwp")

    @abstractmethod
    async def get_recent_meetings(self, limit: int = 10) -> list[MeetingInfo]:
        """
        최근 회의록 목록 가져오기

        Args:
            limit: 가져올 최대 개수

        Returns:
            MeetingInfo 목록
        """
        pass

    @abstractmethod
    async def get_meeting_detail(self, meeting_info: MeetingInfo) -> MeetingInfo:
        """
        회의록 상세 정보 가져오기

        Args:
            meeting_info: 회의 기본 정보

        Returns:
            raw_text가 채워진 MeetingInfo
        """
        pass

    @abstractmethod
    async def download_file(self, file_url: str, download_dir: Path) -> Optional[Path]:
        """
        회의록 파일 다운로드

        Args:
            file_url: 파일 다운로드 URL
            download_dir: 저장 디렉토리

        Returns:
            다운로드된 파일 경로 또는 None
        """
        pass

    def build_url(self, endpoint_key: str, **params) -> str:
        """
        엔드포인트 키로 전체 URL 생성

        Args:
            endpoint_key: endpoints 딕셔너리의 키
            **params: URL 파라미터

        Returns:
            완전한 URL
        """
        endpoint = self.endpoints.get(endpoint_key, "")
        url = f"{self.base_url}{endpoint}"

        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        return url

    def parse_meeting_type(self, text: str) -> str:
        """
        텍스트에서 회의 유형 파싱

        Args:
            text: 회의 제목 또는 설명

        Returns:
            회의 유형 (본회의, 상임위, 특별위, 기타)
        """
        text = text.lower()

        if "본회의" in text:
            return "본회의"
        elif "특별위" in text or "특위" in text:
            return "특별위"
        elif "위원회" in text or "상임위" in text:
            return "상임위"
        else:
            return "기타"

    def parse_session(self, text: str) -> int:
        """
        텍스트에서 회기 번호 추출

        Args:
            text: 회의 제목

        Returns:
            회기 번호 (추출 실패 시 0)
        """
        import re
        match = re.search(r'제?\s*(\d+)\s*회', text)
        if match:
            return int(match.group(1))
        return 0
