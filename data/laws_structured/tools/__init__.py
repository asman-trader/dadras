"""
ابزارهای مدیریت سیستم قوانین دادرس
"""

__version__ = '1.0.0'
__author__ = 'تیم دادرس'

from .law_parser import LawParser
from .batch_processor import BatchProcessor

__all__ = ['LawParser', 'BatchProcessor']

