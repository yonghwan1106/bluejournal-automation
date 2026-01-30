"""
Council Watcher - 크롤러 모듈

지방의회 회의록 크롤링을 담당합니다.
"""

from .base import BaseCrawler
from .standard import StandardCrawler

__all__ = ["BaseCrawler", "StandardCrawler"]
