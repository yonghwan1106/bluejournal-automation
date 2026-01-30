"""
HWP 파일 파서

pyhwpx와 olefile을 사용하여 HWP 파일에서 텍스트를 추출합니다.
"""

import os
from pathlib import Path
from typing import Optional


class HWPParser:
    """
    HWP 파일 텍스트 추출기

    pyhwpx를 1차로 시도하고, 실패 시 olefile로 폴백합니다.
    """

    @staticmethod
    def extract_text(file_path: str | Path) -> Optional[str]:
        """
        HWP 파일에서 텍스트 추출

        Args:
            file_path: HWP 파일 경로

        Returns:
            추출된 텍스트 또는 None
        """
        file_path = Path(file_path)

        if not file_path.exists():
            print(f"파일이 존재하지 않습니다: {file_path}")
            return None

        # 1차: pyhwpx 시도
        text = HWPParser._extract_with_pyhwpx(file_path)
        if text and len(text) > 50:
            return text

        # 2차: olefile 폴백
        text = HWPParser._extract_with_olefile(file_path)
        if text:
            return text

        return None

    @staticmethod
    def _extract_with_pyhwpx(file_path: Path) -> Optional[str]:
        """pyhwpx를 사용한 텍스트 추출"""
        try:
            import pyhwpx

            hwp = pyhwpx.Hwp(file_path)
            text = hwp.get_text()
            hwp.close()
            return text

        except ImportError:
            print("pyhwpx가 설치되지 않았습니다.")
            return None
        except Exception as e:
            print(f"pyhwpx 추출 오류: {e}")
            return None

    @staticmethod
    def _extract_with_olefile(file_path: Path) -> Optional[str]:
        """olefile을 사용한 텍스트 추출 (폴백)"""
        try:
            import olefile

            ole = olefile.OleFileIO(str(file_path))

            # PrvText 스트림에서 텍스트 추출
            if ole.exists("PrvText"):
                prvtext = ole.openstream("PrvText")
                data = prvtext.read()

                # UTF-16 LE 디코딩 시도
                try:
                    text = data.decode("utf-16-le", errors="ignore")
                except Exception:
                    text = data.decode("cp949", errors="ignore")

                ole.close()
                return HWPParser._clean_text(text)

            # BodyText 섹션에서 추출 시도
            text_parts = []
            for entry in ole.listdir():
                entry_path = "/".join(entry)
                if "BodyText" in entry_path or "Section" in entry_path:
                    try:
                        stream = ole.openstream(entry)
                        data = stream.read()
                        # 바이너리에서 텍스트 추출 시도
                        decoded = data.decode("utf-16-le", errors="ignore")
                        # 인쇄 가능 문자만 추출
                        clean = "".join(c for c in decoded if c.isprintable() or c in "\n\r\t")
                        if len(clean) > 10:
                            text_parts.append(clean)
                    except Exception:
                        continue

            ole.close()

            if text_parts:
                return HWPParser._clean_text("\n".join(text_parts))

            return None

        except ImportError:
            print("olefile이 설치되지 않았습니다.")
            return None
        except Exception as e:
            print(f"olefile 추출 오류: {e}")
            return None

    @staticmethod
    def _clean_text(text: str) -> str:
        """추출된 텍스트 정리"""
        if not text:
            return ""

        # NULL 문자 제거
        text = text.replace("\x00", "")

        # 연속된 공백/줄바꿈 정리
        import re
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        # 앞뒤 공백 제거
        text = text.strip()

        return text

    @staticmethod
    def extract_from_directory(directory: str | Path) -> dict[str, str]:
        """
        디렉토리 내 모든 HWP 파일에서 텍스트 추출

        Args:
            directory: HWP 파일이 있는 디렉토리

        Returns:
            {파일명: 텍스트} 딕셔너리
        """
        directory = Path(directory)
        results = {}

        hwp_files = list(directory.glob("*.hwp")) + list(directory.glob("*.hwpx"))

        for hwp_file in hwp_files:
            text = HWPParser.extract_text(hwp_file)
            if text:
                results[hwp_file.name] = text

        return results
