"""
회의록 텍스트 청킹

발언자별, 안건별로 회의록 텍스트를 분할합니다.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import yaml


@dataclass
class Utterance:
    """발언 단위"""
    speaker: str
    role: str  # 의원, 위원장, 국장, 과장 등
    text: str
    start_pos: int = 0
    end_pos: int = 0


@dataclass
class Agenda:
    """안건 단위"""
    title: str
    utterances: list[Utterance] = field(default_factory=list)


@dataclass
class ChunkedMeeting:
    """청킹된 회의록"""
    original_text: str
    agendas: list[Agenda] = field(default_factory=list)
    utterances: list[Utterance] = field(default_factory=list)

    @property
    def total_utterances(self) -> int:
        """전체 발언 수"""
        count = len(self.utterances)
        for agenda in self.agendas:
            count += len(agenda.utterances)
        return count


class MeetingChunker:
    """
    회의록 텍스트 청킹 도구

    - 발언자별 분할
    - 안건별 분할
    - 역할(의원/공무원) 구분
    """

    # 기본 발언자 패턴
    DEFAULT_SPEAKER_PATTERNS = [
        r'○\s*([가-힣]{2,4})\s*의원',
        r'○\s*위원장\s*([가-힣]{2,4})',
        r'○\s*([가-힣]{2,4})\s*위원장',
        r'○\s*([가-힣]{2,4})\s*(부?시장|부?군수|부?구청장)',
        r'○\s*([가-힣]{2,4})\s*(국장|실장|과장|계장|담당|주무관)',
        r'◯\s*([가-힣]{2,4})\s*(의원|위원장|국장|과장)',
        r'◎\s*([가-힣]{2,4})\s*(의원|위원장)',
    ]

    # 기본 안건 패턴
    DEFAULT_AGENDA_PATTERNS = [
        r'제\s*\d+\s*호\s*의안[^\n]*',
        r'【[^】]+】',
        r'□\s*[가-힣]+[^\n]*',
        r'\d+\.\s*[가-힣]+\s*(안건|보고|심사)[^\n]*',
    ]

    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: prompts.yaml 경로 (커스텀 패턴 로드용)
        """
        self.speaker_patterns = self.DEFAULT_SPEAKER_PATTERNS.copy()
        self.agenda_patterns = self.DEFAULT_AGENDA_PATTERNS.copy()

        if config_path and config_path.exists():
            self._load_config(config_path)

    def _load_config(self, config_path: Path):
        """설정 파일에서 패턴 로드"""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            chunking = config.get("chunking", {})

            if "speaker_patterns" in chunking:
                self.speaker_patterns = chunking["speaker_patterns"]

            if "agenda_patterns" in chunking:
                self.agenda_patterns = chunking["agenda_patterns"]

        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")

    def chunk(self, text: str) -> ChunkedMeeting:
        """
        회의록 텍스트를 청킹

        Args:
            text: 원본 회의록 텍스트

        Returns:
            ChunkedMeeting 객체
        """
        result = ChunkedMeeting(original_text=text)

        # 1. 발언자별 분할
        result.utterances = self._chunk_by_speaker(text)

        # 2. 안건별 분할 (발언자 청킹 결과 포함)
        result.agendas = self._chunk_by_agenda(text, result.utterances)

        return result

    def _chunk_by_speaker(self, text: str) -> list[Utterance]:
        """발언자별로 텍스트 분할"""
        utterances = []

        # 모든 발언자 패턴으로 위치 찾기
        speaker_positions = []

        for pattern in self.speaker_patterns:
            for match in re.finditer(pattern, text):
                speaker = match.group(1)
                role = self._extract_role(match.group(0))
                speaker_positions.append({
                    "speaker": speaker,
                    "role": role,
                    "start": match.start(),
                    "end": match.end(),
                    "full_match": match.group(0)
                })

        # 위치순 정렬
        speaker_positions.sort(key=lambda x: x["start"])

        # 발언 단위로 분할
        for i, pos in enumerate(speaker_positions):
            # 다음 발언자까지의 텍스트
            start = pos["end"]
            if i + 1 < len(speaker_positions):
                end = speaker_positions[i + 1]["start"]
            else:
                end = len(text)

            utterance_text = text[start:end].strip()

            if utterance_text:
                utterance = Utterance(
                    speaker=pos["speaker"],
                    role=pos["role"],
                    text=utterance_text,
                    start_pos=pos["start"],
                    end_pos=end
                )
                utterances.append(utterance)

        return utterances

    def _extract_role(self, match_text: str) -> str:
        """매칭된 텍스트에서 역할 추출"""
        match_text = match_text.lower()

        if "의원" in match_text:
            return "의원"
        elif "위원장" in match_text:
            return "위원장"
        elif "시장" in match_text or "군수" in match_text or "구청장" in match_text:
            return "단체장"
        elif "국장" in match_text or "실장" in match_text:
            return "국장"
        elif "과장" in match_text:
            return "과장"
        elif "계장" in match_text or "담당" in match_text or "주무관" in match_text:
            return "담당자"
        else:
            return "기타"

    def _chunk_by_agenda(self, text: str, utterances: list[Utterance]) -> list[Agenda]:
        """안건별로 텍스트 분할"""
        agendas = []

        # 안건 패턴으로 위치 찾기
        agenda_positions = []

        for pattern in self.agenda_patterns:
            for match in re.finditer(pattern, text):
                agenda_positions.append({
                    "title": match.group(0).strip(),
                    "start": match.start(),
                    "end": match.end()
                })

        # 위치순 정렬
        agenda_positions.sort(key=lambda x: x["start"])

        # 각 안건에 해당하는 발언 할당
        for i, pos in enumerate(agenda_positions):
            start = pos["start"]
            if i + 1 < len(agenda_positions):
                end = agenda_positions[i + 1]["start"]
            else:
                end = len(text)

            # 해당 범위의 발언 찾기
            agenda_utterances = [
                u for u in utterances
                if start <= u.start_pos < end
            ]

            agenda = Agenda(
                title=pos["title"],
                utterances=agenda_utterances
            )
            agendas.append(agenda)

        return agendas

    def get_speaker_stats(self, chunked: ChunkedMeeting) -> dict:
        """발언 통계 계산"""
        stats = {
            "total_utterances": chunked.total_utterances,
            "by_role": {},
            "by_speaker": {},
        }

        all_utterances = chunked.utterances.copy()
        for agenda in chunked.agendas:
            all_utterances.extend(agenda.utterances)

        for utterance in all_utterances:
            # 역할별 통계
            if utterance.role not in stats["by_role"]:
                stats["by_role"][utterance.role] = 0
            stats["by_role"][utterance.role] += 1

            # 발언자별 통계
            key = f"{utterance.speaker}({utterance.role})"
            if key not in stats["by_speaker"]:
                stats["by_speaker"][key] = 0
            stats["by_speaker"][key] += 1

        return stats

    def find_confrontations(self, chunked: ChunkedMeeting) -> list[tuple[Utterance, Utterance]]:
        """
        의원-공무원 대치 상황 찾기

        연속된 발언에서 의원과 공무원이 교대로 발언하는 패턴 추출
        """
        confrontations = []
        all_utterances = chunked.utterances.copy()

        council_roles = {"의원", "위원장"}
        official_roles = {"단체장", "국장", "과장", "담당자"}

        for i in range(len(all_utterances) - 1):
            curr = all_utterances[i]
            next_u = all_utterances[i + 1]

            # 의원 → 공무원 또는 공무원 → 의원 패턴
            if (curr.role in council_roles and next_u.role in official_roles) or \
               (curr.role in official_roles and next_u.role in council_roles):
                confrontations.append((curr, next_u))

        return confrontations
