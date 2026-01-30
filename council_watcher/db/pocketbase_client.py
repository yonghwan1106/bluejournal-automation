"""
PocketBase 클라이언트

회의록 및 분석 결과를 PocketBase에 저장/조회합니다.
"""

import os
from datetime import datetime
from typing import Optional
from dataclasses import asdict

import httpx


class PocketBaseClient:
    """
    PocketBase REST API 클라이언트

    컬렉션:
    - councils: 의회 정보
    - meetings: 회의 정보
    - issues: 분석된 이슈
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        admin_email: Optional[str] = None,
        admin_password: Optional[str] = None
    ):
        """
        Args:
            base_url: PocketBase URL (없으면 환경변수에서 로드)
            admin_email: 관리자 이메일
            admin_password: 관리자 비밀번호
        """
        self.base_url = base_url or os.getenv("POCKETBASE_URL", "http://158.247.210.200:8090")
        self.admin_email = admin_email or os.getenv("POCKETBASE_ADMIN_EMAIL")
        self.admin_password = admin_password or os.getenv("POCKETBASE_ADMIN_PASSWORD")

        self.token: Optional[str] = None
        self.client = httpx.Client(timeout=30.0)

    def _get_headers(self) -> dict:
        """인증 헤더 반환"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = self.token
        return headers

    def authenticate(self) -> bool:
        """관리자 인증"""
        if not self.admin_email or not self.admin_password:
            print("관리자 계정 정보가 없습니다.")
            return False

        try:
            response = self.client.post(
                f"{self.base_url}/api/admins/auth-with-password",
                json={
                    "identity": self.admin_email,
                    "password": self.admin_password
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                return True
            else:
                print(f"인증 실패: {response.text}")
                return False

        except Exception as e:
            print(f"인증 오류: {e}")
            return False

    # ========== Councils ==========

    def get_council(self, code: str) -> Optional[dict]:
        """의회 정보 조회"""
        try:
            response = self.client.get(
                f"{self.base_url}/api/collections/councils/records",
                params={"filter": f'code="{code}"'},
                headers=self._get_headers()
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                return items[0] if items else None

        except Exception as e:
            print(f"의회 조회 오류: {e}")

        return None

    def upsert_council(self, council_data: dict) -> Optional[dict]:
        """의회 정보 생성/수정"""
        existing = self.get_council(council_data.get("code", ""))

        try:
            if existing:
                # 수정
                response = self.client.patch(
                    f"{self.base_url}/api/collections/councils/records/{existing['id']}",
                    json=council_data,
                    headers=self._get_headers()
                )
            else:
                # 생성
                response = self.client.post(
                    f"{self.base_url}/api/collections/councils/records",
                    json=council_data,
                    headers=self._get_headers()
                )

            if response.status_code in [200, 201]:
                return response.json()
            else:
                print(f"의회 저장 오류: {response.text}")

        except Exception as e:
            print(f"의회 저장 오류: {e}")

        return None

    # ========== Meetings ==========

    def get_meeting(self, council_code: str, title: str, meeting_date: datetime) -> Optional[dict]:
        """회의 정보 조회 (중복 체크용)"""
        try:
            date_str = meeting_date.strftime("%Y-%m-%d")
            filter_str = f'council_code="{council_code}" && title~"{title[:30]}" && meeting_date>="{date_str}"'

            response = self.client.get(
                f"{self.base_url}/api/collections/meetings/records",
                params={"filter": filter_str},
                headers=self._get_headers()
            )

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                return items[0] if items else None

        except Exception as e:
            print(f"회의 조회 오류: {e}")

        return None

    def create_meeting(self, meeting_data: dict) -> Optional[dict]:
        """회의 정보 저장"""
        # meeting_date를 ISO 형식으로 변환
        if isinstance(meeting_data.get("meeting_date"), datetime):
            meeting_data["meeting_date"] = meeting_data["meeting_date"].isoformat()

        try:
            response = self.client.post(
                f"{self.base_url}/api/collections/meetings/records",
                json=meeting_data,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"회의 저장 오류: {response.text}")

        except Exception as e:
            print(f"회의 저장 오류: {e}")

        return None

    def get_meetings(
        self,
        council_code: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict]:
        """회의 목록 조회"""
        try:
            params = {
                "perPage": limit,
                "page": (offset // limit) + 1,
                "sort": "-meeting_date"
            }

            if council_code:
                params["filter"] = f'council_code="{council_code}"'

            response = self.client.get(
                f"{self.base_url}/api/collections/meetings/records",
                params=params,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("items", [])

        except Exception as e:
            print(f"회의 목록 조회 오류: {e}")

        return []

    # ========== Issues ==========

    def create_issue(self, issue_data: dict) -> Optional[dict]:
        """이슈 저장"""
        try:
            response = self.client.post(
                f"{self.base_url}/api/collections/issues/records",
                json=issue_data,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"이슈 저장 오류: {response.text}")

        except Exception as e:
            print(f"이슈 저장 오류: {e}")

        return None

    def get_issues(
        self,
        meeting_id: Optional[str] = None,
        severity: Optional[str] = None,
        is_used: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict]:
        """이슈 목록 조회"""
        try:
            params = {
                "perPage": limit,
                "page": (offset // limit) + 1,
                "sort": "-created"
            }

            filters = []
            if meeting_id:
                filters.append(f'meeting="{meeting_id}"')
            if severity:
                filters.append(f'severity="{severity}"')
            if is_used is not None:
                filters.append(f'is_used={str(is_used).lower()}')

            if filters:
                params["filter"] = " && ".join(filters)

            response = self.client.get(
                f"{self.base_url}/api/collections/issues/records",
                params=params,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("items", [])

        except Exception as e:
            print(f"이슈 목록 조회 오류: {e}")

        return []

    def update_issue(self, issue_id: str, update_data: dict) -> Optional[dict]:
        """이슈 수정"""
        try:
            response = self.client.patch(
                f"{self.base_url}/api/collections/issues/records/{issue_id}",
                json=update_data,
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"이슈 수정 오류: {response.text}")

        except Exception as e:
            print(f"이슈 수정 오류: {e}")

        return None

    def mark_issue_used(self, issue_id: str) -> Optional[dict]:
        """이슈를 기사화됨으로 표시"""
        return self.update_issue(issue_id, {"is_used": True})

    # ========== 유틸리티 ==========

    def save_analysis_result(self, meeting_id: str, analysis_result) -> list[dict]:
        """분석 결과를 이슈로 저장"""
        saved_issues = []

        for issue in analysis_result.issues:
            issue_data = {
                "meeting": meeting_id,
                "severity": issue.severity,
                "topic": issue.topic,
                "conflict_summary": issue.conflict_summary,
                "key_quote": issue.key_quote,
                "speakers": issue.speakers if isinstance(issue.speakers, str) else ",".join(issue.speakers),
                "fact_check_point": issue.fact_check_point,
                "related_budget": issue.related_budget,
                "article_angle": issue.article_angle,
                "is_used": False
            }

            saved = self.create_issue(issue_data)
            if saved:
                saved_issues.append(saved)

        return saved_issues

    def close(self):
        """클라이언트 종료"""
        self.client.close()
