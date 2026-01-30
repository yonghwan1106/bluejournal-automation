"""
Google Gemini API 분석기

회의록 텍스트를 분석하여 비판적 이슈를 추출합니다.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class Issue:
    """분석된 이슈"""
    severity: str  # 상, 중, 하
    topic: str
    conflict_summary: str
    key_quote: str
    speakers: list[str] = field(default_factory=list)
    fact_check_point: str = ""
    related_budget: str = ""
    article_angle: str = ""


@dataclass
class AnalysisResult:
    """분석 결과"""
    issues: list[Issue] = field(default_factory=list)
    summary: str = ""
    notable_absence: str = ""
    raw_response: str = ""
    error: Optional[str] = None


class GeminiAnalyzer:
    """
    Google Gemini API를 사용한 회의록 분석기

    무료 티어: 일일 1,500회 요청
    """

    def __init__(self, api_key: Optional[str] = None, config_path: Optional[Path] = None):
        """
        Args:
            api_key: Gemini API 키 (없으면 환경변수에서 로드)
            config_path: prompts.yaml 경로
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

        self.model = None
        self.system_prompt = ""
        self.output_format = ""

        # 설정 로드
        if config_path and config_path.exists():
            self._load_config(config_path)
        else:
            self._set_default_prompts()

        # Gemini 모델 초기화
        self._init_model()

    def _init_model(self):
        """Gemini 모델 초기화"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)

            # Gemini 2.0 Flash 사용 (빠르고 무료)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.95,
                    "max_output_tokens": 8192,
                }
            )
        except ImportError:
            raise ImportError("google-generativeai 패키지를 설치해주세요.")

    def _load_config(self, config_path: Path):
        """설정 파일에서 프롬프트 로드"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            analysis = config.get("analysis", {})
            self.system_prompt = analysis.get("system_prompt", "")
            self.output_format = analysis.get("output_format", "")

        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
            self._set_default_prompts()

    def _set_default_prompts(self):
        """기본 프롬프트 설정"""
        self.system_prompt = """당신은 날카로운 비판 의식을 가진 탐사보도 전문 기자입니다.
제공된 지방의회 회의록 텍스트를 분석하여, 행정부(시청/도청)의 실책이나 갈등 상황을 찾아내세요.

다음 기준에 해당하는 내용을 우선적으로 추출하십시오:
1. 질타 및 추궁: 의원이 공무원에게 언성을 높이거나, 자료 미비/답변 불성실을 지적하는 부분
2. 사업 지연 및 실패: 당초 계획보다 늦어지거나 예산이 증액된 사업
3. 특혜 의혹: 수의계약이나 특정 업체 선정에 대한 의문 제기
4. 시민 불편: 민원이 반복되는데 해결되지 않고 있는 사안
5. 예산 낭비: 불필요한 지출이나 중복 투자 의혹
6. 안전 문제: 시민 안전과 관련된 미비점이나 사고 우려"""

        self.output_format = """출력 형식 (반드시 유효한 JSON으로 응답):
{
  "issues": [
    {
      "severity": "상/중/하",
      "topic": "안건 핵심 키워드",
      "conflict_summary": "누가 무엇을 문제 삼았는지 1문장",
      "key_quote": "가장 날카로웠던 발언 (발언자 포함)",
      "speakers": ["발언자1", "발언자2"],
      "fact_check_point": "추가 취재 포인트",
      "related_budget": "관련 예산 (있는 경우, 없으면 빈 문자열)",
      "article_angle": "기사화할 경우 추천 앵글"
    }
  ],
  "summary": "회의 전체 분위기 1-2문장 요약",
  "notable_absence": "특이사항 (예: 답변 거부, 자료 미제출 등, 없으면 빈 문자열)"
}"""

    def analyze(self, text: str, council_name: str = "") -> AnalysisResult:
        """
        회의록 텍스트 분석

        Args:
            text: 회의록 텍스트
            council_name: 의회명 (컨텍스트용)

        Returns:
            AnalysisResult 객체
        """
        if not text or len(text) < 100:
            return AnalysisResult(error="분석할 텍스트가 너무 짧습니다.")

        # 텍스트가 너무 길면 분할
        max_chars = 100000  # Gemini 컨텍스트 제한 고려
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[텍스트가 너무 길어 일부만 분석합니다]"

        # 프롬프트 구성
        prompt = self._build_prompt(text, council_name)

        try:
            # Gemini API 호출
            response = self.model.generate_content(prompt)

            if not response.text:
                return AnalysisResult(error="API 응답이 비어있습니다.")

            # JSON 파싱
            return self._parse_response(response.text)

        except Exception as e:
            return AnalysisResult(error=f"API 호출 오류: {str(e)}")

    def _build_prompt(self, text: str, council_name: str) -> str:
        """분석 프롬프트 구성"""
        context = f"[{council_name} 회의록]" if council_name else "[지방의회 회의록]"

        prompt = f"""{self.system_prompt}

{context}

{self.output_format}

분석할 회의록 텍스트:
---
{text}
---

위 회의록을 분석하여 JSON 형식으로 응답해주세요. 반드시 유효한 JSON만 출력하세요."""

        return prompt

    def _parse_response(self, response_text: str) -> AnalysisResult:
        """API 응답 파싱"""
        result = AnalysisResult(raw_response=response_text)

        try:
            # JSON 블록 추출
            json_text = response_text

            # ```json ... ``` 블록이 있으면 추출
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    json_text = response_text[start:end]
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end > start:
                    json_text = response_text[start:end]

            json_text = json_text.strip()

            # JSON 파싱
            data = json.loads(json_text)

            # 이슈 파싱
            for issue_data in data.get("issues", []):
                issue = Issue(
                    severity=issue_data.get("severity", "중"),
                    topic=issue_data.get("topic", ""),
                    conflict_summary=issue_data.get("conflict_summary", ""),
                    key_quote=issue_data.get("key_quote", ""),
                    speakers=issue_data.get("speakers", []),
                    fact_check_point=issue_data.get("fact_check_point", ""),
                    related_budget=issue_data.get("related_budget", ""),
                    article_angle=issue_data.get("article_angle", "")
                )
                result.issues.append(issue)

            result.summary = data.get("summary", "")
            result.notable_absence = data.get("notable_absence", "")

        except json.JSONDecodeError as e:
            result.error = f"JSON 파싱 오류: {str(e)}"
        except Exception as e:
            result.error = f"응답 파싱 오류: {str(e)}"

        return result

    def analyze_chunked(self, chunks: list[str], council_name: str = "") -> list[AnalysisResult]:
        """
        청크 단위로 분석

        Args:
            chunks: 분할된 텍스트 리스트
            council_name: 의회명

        Returns:
            AnalysisResult 리스트
        """
        results = []
        for i, chunk in enumerate(chunks):
            print(f"청크 {i+1}/{len(chunks)} 분석 중...")
            result = self.analyze(chunk, council_name)
            results.append(result)

        return results

    def merge_results(self, results: list[AnalysisResult]) -> AnalysisResult:
        """
        여러 분석 결과를 하나로 병합

        Args:
            results: AnalysisResult 리스트

        Returns:
            병합된 AnalysisResult
        """
        merged = AnalysisResult()

        for result in results:
            if result.error:
                continue

            merged.issues.extend(result.issues)

            if result.summary:
                merged.summary += f" {result.summary}"

            if result.notable_absence:
                merged.notable_absence += f" {result.notable_absence}"

        # 중복 제거 및 중요도 정렬
        merged.issues = self._deduplicate_issues(merged.issues)
        merged.issues.sort(key=lambda x: {"상": 0, "중": 1, "하": 2}.get(x.severity, 2))

        return merged

    def _deduplicate_issues(self, issues: list[Issue]) -> list[Issue]:
        """유사한 이슈 중복 제거"""
        seen_topics = set()
        unique_issues = []

        for issue in issues:
            # 토픽 기반 간단한 중복 체크
            topic_key = issue.topic[:10] if issue.topic else ""
            if topic_key not in seen_topics:
                seen_topics.add(topic_key)
                unique_issues.append(issue)

        return unique_issues
