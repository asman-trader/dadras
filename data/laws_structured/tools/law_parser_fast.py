#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نسخه بهینه‌شده پارسر قوانین با سرعت بالا
- استفاده از generators برای مدیریت حافظه
- Compiled regex patterns برای سرعت
- Lazy evaluation
- Memory-efficient processing
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Generator
from datetime import datetime
from functools import lru_cache
import mmap


class FastLawParser:
    """کلاس پارسر بهینه‌شده قوانین"""
    
    def __init__(self):
        self.current_article = None
        
        # Compile regex patterns یکبار برای سرعت بیشتر
        self._compile_patterns()
        
        # Cache برای encoding detection
        self._encoding_cache = {}
    
    def _compile_patterns(self):
        """کامپایل الگوهای regex برای سرعت"""
        self.compiled_patterns = {
            'article_number': [
                re.compile(r'ماده[\s\u200c]*(\d+)', re.UNICODE),
                re.compile(r'تبصره[\s\u200c]*(\d+)', re.UNICODE),
            ],
            'text_start': re.compile(r'^(ماده|متن|قانون)\s*:', re.UNICODE | re.IGNORECASE),
            'explanation_start': re.compile(r'^(شرح|توضیح|تفسیر)\s*:', re.UNICODE | re.IGNORECASE),
            'example_start': re.compile(r'^(مثال|نمونه|مصداق)\s*:', re.UNICODE | re.IGNORECASE),
            'keypoints_start': re.compile(r'^نکات\s*(کلیدی|مهم)\s*:', re.UNICODE | re.IGNORECASE),
            'tags_start': re.compile(r'^(برچسب|تگ)[\s\u200c]*:?', re.UNICODE | re.IGNORECASE),
            'list_item': re.compile(r'^[\-•–]\s*', re.UNICODE),
        }
        
        # الگوهای تمیزکاری
        self.clean_patterns = {
            'newlines': re.compile(r'\r\n|\r', re.UNICODE),
            'spaces': re.compile(r'[ \t]+', re.UNICODE),
            'multi_newlines': re.compile(r'\n{3,}', re.UNICODE),
            'persian_nums': str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'),
            'arabic_nums': str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'),
        }
    
    @lru_cache(maxsize=128)
    def _detect_encoding(self, file_path: str) -> str:
        """تشخیص encoding با cache"""
        encodings = ['utf-8', 'utf-8-sig', 'cp1256', 'windows-1256']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1024)  # تست با 1KB اول
                    return encoding
            except (UnicodeDecodeError, FileNotFoundError):
                continue
        
        return 'utf-8'  # default
    
    def parse_file_fast(self, file_path: str, law_code: str, 
                        category: str = None) -> Generator[Dict, None, None]:
        """پارس سریع با generator برای صرفه‌جویی حافظه"""
        
        encoding = self._detect_encoding(file_path)
        
        try:
            with open(file_path, 'r', encoding=encoding, buffering=8192) as f:
                # استفاده از generator برای خواندن خط به خط
                lines = self._clean_lines_generator(f)
                
                current_article = None
                buffer = []
                
                for line in lines:
                    # شناسایی شروع ماده جدید
                    article_num = self._extract_article_number_fast(line)
                    
                    if article_num:
                        # yield ماده قبلی
                        if current_article:
                            yield self._finalize_article_fast(
                                current_article, law_code, category
                            )
                        
                        # شروع ماده جدید
                        current_article = {
                            'number': article_num,
                            'lines': []
                        }
                        buffer = []
                    
                    elif current_article:
                        buffer.append(line)
                    
                    # yield هر 50 خط برای جلوگیری از پر شدن حافظه
                    if len(buffer) >= 50:
                        current_article['lines'].extend(buffer)
                        buffer = []
                
                # آخرین ماده
                if current_article:
                    if buffer:
                        current_article['lines'].extend(buffer)
                    yield self._finalize_article_fast(
                        current_article, law_code, category
                    )
                    
        except Exception as e:
            print(f"❌ خطا در پارس: {e}")
            return
    
    def _clean_lines_generator(self, file_handle) -> Generator[str, None, None]:
        """تمیزکاری خطوط با generator"""
        for line in file_handle:
            # تمیزکاری سریع
            line = self.clean_patterns['newlines'].sub('\n', line)
            line = self.clean_patterns['spaces'].sub(' ', line)
            line = line.translate(self.clean_patterns['persian_nums'])
            line = line.translate(self.clean_patterns['arabic_nums'])
            line = line.strip()
            
            if line:
                yield line
    
    def _extract_article_number_fast(self, line: str) -> Optional[int]:
        """استخراج سریع شماره ماده"""
        for pattern in self.compiled_patterns['article_number']:
            match = pattern.search(line)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
    
    def _finalize_article_fast(self, article_data: Dict, 
                               law_code: str, category: str) -> Dict:
        """نهایی‌سازی سریع ماده"""
        
        lines = article_data['lines']
        article = {
            'article_number': article_data['number'],
            'title': '',
            'text': '',
            'explanation': '',
            'examples': [],
            'key_points': [],
            'tags': [],
            'related_articles': [],
            'references': [],
            'category': category or 'عمومی',
            'subcategory': '',
            'status': 'active',
            'last_modified': datetime.now().strftime('%Y/%m/%d')
        }
        
        # پردازش سریع خطوط
        current_section = 'text'
        
        for line in lines:
            if not line:
                continue
            
            # تشخیص سریع نوع خط
            if self.compiled_patterns['text_start'].match(line):
                article['text'] = self._extract_content(line)
                current_section = 'text'
            
            elif self.compiled_patterns['explanation_start'].match(line):
                article['explanation'] = self._extract_content(line)
                current_section = 'explanation'
            
            elif self.compiled_patterns['example_start'].match(line):
                examples = self._extract_content(line)
                article['examples'] = self._split_examples_fast(examples)
            
            elif self.compiled_patterns['tags_start'].match(line):
                tags = self._extract_content(line)
                article['tags'] = self._extract_tags_fast(tags)
            
            elif self.compiled_patterns['list_item'].match(line):
                point = self.compiled_patterns['list_item'].sub('', line)
                if point:
                    article['key_points'].append(point)
            
            else:
                # اضافه به بخش فعلی
                if current_section == 'text' and not article['text']:
                    article['text'] = line
                elif not article['explanation']:
                    article['explanation'] = line
        
        # تولید عنوان و تگ در صورت نیاز
        if not article['title'] and article['text']:
            article['title'] = ' '.join(article['text'].split()[:7]) + '...'
        
        if not article['tags']:
            article['tags'] = self._auto_generate_tags_fast(article)
        
        return article
    
    @staticmethod
    def _extract_content(line: str) -> str:
        """استخراج محتوا بعد از :"""
        if ':' in line:
            return line.split(':', 1)[1].strip()
        return line.strip()
    
    @staticmethod
    def _split_examples_fast(text: str) -> List[str]:
        """تقسیم سریع مثال‌ها"""
        # استفاده از regex برای سرعت
        examples = re.split(r'[،؛]|\s+یا\s+|\s+و\s+', text)
        return [ex.strip() for ex in examples if ex.strip()][:5]
    
    @staticmethod
    def _extract_tags_fast(text: str) -> List[str]:
        """استخراج سریع تگ‌ها"""
        tags = text.replace('#', '').replace('_', ' ').split()
        return [tag.strip() for tag in tags if tag.strip()][:10]
    
    @lru_cache(maxsize=1000)
    def _auto_generate_tags_fast(self, article_tuple) -> List[str]:
        """تولید خودکار تگ‌ها با cache"""
        # تبدیل article به tuple برای cache
        text = (article_tuple.get('text', '') + ' ' + 
                article_tuple.get('explanation', '')).lower()
        
        # لیست کلمات کلیدی
        keywords = {
            'عقد': 'عقد', 'معامله': 'معامله', 'ملک': 'مالکیت',
            'مالک': 'مالکیت', 'خرید': 'خرید_فروش', 'فروش': 'خرید_فروش',
            'اجاره': 'اجاره', 'وکالت': 'وکالت', 'قرارداد': 'قرارداد',
            'تعهد': 'تعهد', 'ضمان': 'ضمان', 'رهن': 'رهن',
        }
        
        tags = set()
        for word, tag in keywords.items():
            if word in text:
                tags.add(tag)
        
        return list(tags)[:5] if tags else [article_tuple.get('category', 'عمومی')]
    
    def parse_and_save_fast(self, input_file: str, output_dir: str,
                           law_code: str, category: str = None,
                           chunk_size: int = 20):
        """پارس و ذخیره با سرعت بالا"""
        
        print(f"⚡ پارس سریع: {input_file}")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # استفاده از generator برای صرفه‌جویی حافظه
        article_generator = self.parse_file_fast(input_file, law_code, category)
        
        chunk = []
        chunk_start = None
        total_articles = 0
        
        for article in article_generator:
            if chunk_start is None:
                chunk_start = article['article_number']
            
            chunk.append(article)
            total_articles += 1
            
            # ذخیره chunk
            if len(chunk) >= chunk_size:
                self._save_chunk_fast(chunk, output_path, chunk_start)
                chunk = []
                chunk_start = None
        
        # ذخیره آخرین chunk
        if chunk:
            self._save_chunk_fast(chunk, output_path, chunk_start)
        
        print(f"✅ {total_articles} ماده پردازش شد")
    
    @staticmethod
    def _save_chunk_fast(chunk: List[Dict], output_dir: Path, start_num: int):
        """ذخیره سریع chunk"""
        end_num = chunk[-1]['article_number']
        filename = f"articles_{start_num:03d}-{end_num:03d}.json"
        output_file = output_dir / filename
        
        # استفاده از write به جای dump برای سرعت
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2, separators=(',', ':'))
        
        print(f"  ✅ {filename} ({len(chunk)} ماده)")


class MemoryMappedParser(FastLawParser):
    """پارسر با استفاده از memory mapping برای فایل‌های بزرگ"""
    
    def parse_large_file(self, file_path: str, law_code: str,
                        category: str = None) -> Generator[Dict, None, None]:
        """پارس فایل‌های بزرگ با memory mapping"""
        
        try:
            with open(file_path, 'r+b') as f:
                # استفاده از mmap برای دسترسی سریع
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped:
                    # تبدیل به text
                    content = mmapped.read().decode('utf-8', errors='ignore')
                    
                    # پردازش با generator
                    lines = content.split('\n')
                    
                    current_article = None
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        article_num = self._extract_article_number_fast(line)
                        
                        if article_num:
                            if current_article:
                                yield self._finalize_article_fast(
                                    current_article, law_code, category
                                )
                            
                            current_article = {
                                'number': article_num,
                                'lines': []
                            }
                        
                        elif current_article:
                            current_article['lines'].append(line)
                    
                    if current_article:
                        yield self._finalize_article_fast(
                            current_article, law_code, category
                        )
        
        except Exception as e:
            print(f"❌ خطا در memory-mapped parsing: {e}")


def main():
    """تست پارسر سریع"""
    import time
    
    parser = FastLawParser()
    
    print("🚀 تست پارسر سریع\n")
    
    sample_file = '../../laws/sample.txt'
    
    if Path(sample_file).exists():
        start = time.time()
        
        articles_count = 0
        for article in parser.parse_file_fast(sample_file, 'test', 'test'):
            articles_count += 1
            print(f"  • ماده {article['article_number']}")
        
        elapsed = time.time() - start
        
        print(f"\n✅ {articles_count} ماده در {elapsed:.3f} ثانیه")
        print(f"⚡ سرعت: {articles_count/elapsed:.1f} ماده/ثانیه")
    else:
        print("❌ فایل نمونه یافت نشد")


if __name__ == '__main__':
    main()

