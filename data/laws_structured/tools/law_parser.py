#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
پارسر قدرتمند برای تبدیل فایل‌های TXT قوانین به JSON
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class LawParser:
    """کلاس پارسر قوانین"""
    
    def __init__(self):
        self.current_article = None
        self.articles = []
        
        # الگوهای regex برای شناسایی بخش‌های مختلف
        self.patterns = {
            'article_number': [
                r'ماده[\s\u200c]*(\d+)',  # ماده 183
                r'ماده[\s\u200c]*[‌\s]*(\d+)',  # با فواصل مختلف
                r'تبصره[\s\u200c]*(\d+)',  # تبصره‌ها
            ],
            'text_start': [
                r'^ماده\s*:',
                r'^متن\s*:',
                r'^قانون\s*:',
            ],
            'explanation_start': [
                r'^شرح\s*:',
                r'^توضیح\s*:',
                r'^تفسیر\s*:',
            ],
            'example_start': [
                r'^مثال\s*:',
                r'^نمونه\s*:',
                r'^مصداق\s*:',
            ],
            'keypoints_start': [
                r'^نکات\s*کلیدی\s*:',
                r'^نکات\s*مهم\s*:',
                r'^موارد\s*مهم\s*:',
            ],
            'tags_start': [
                r'^برچسب\s*:',
                r'^برچسب‌ها\s*:',
                r'^تگ\s*:',
                r'^تگ‌ها\s*:',
            ],
            'references_start': [
                r'^منابع\s*:',
                r'^مراجع\s*:',
                r'^ارجاعات\s*:',
            ]
        }
    
    def parse_file(self, file_path: str, law_code: str, category: str = None) -> List[Dict]:
        """پارس یک فایل قانونی"""
        
        try:
            # تلاش برای خواندن با encoding های مختلف
            content = self._read_file_safe(file_path)
            
            # تمیز کردن متن
            content = self._clean_text(content)
            
            # پارس کردن
            self.articles = []
            lines = content.split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # شناسایی شروع ماده جدید
                article_num = self._extract_article_number(line)
                if article_num:
                    # ذخیره ماده قبلی
                    if self.current_article:
                        self._finalize_article()
                    
                    # شروع ماده جدید
                    self.current_article = {
                        'article_number': article_num,
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
                
                # پردازش محتوای ماده
                elif self.current_article:
                    self._process_line(line, lines, i)
                
                i += 1
            
            # ذخیره آخرین ماده
            if self.current_article:
                self._finalize_article()
            
            return self.articles
            
        except Exception as e:
            print(f"❌ خطا در پارس فایل: {e}")
            return []
    
    def _read_file_safe(self, file_path: str) -> str:
        """خواندن فایل با encoding های مختلف"""
        encodings = ['utf-8', 'utf-8-sig', 'cp1256', 'windows-1256', 'iso-8859-6']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    # بررسی اینکه متن معقول است
                    if len(content) > 0 and not all(c == '؟' or c == '?' for c in content[:100]):
                        return content
            except (UnicodeDecodeError, FileNotFoundError):
                continue
        
        raise ValueError(f"نمی‌توان فایل را با encoding های معمول خواند")
    
    def _clean_text(self, text: str) -> str:
        """تمیز کردن و نرمال‌سازی متن"""
        # حذف کاراکترهای اضافی
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        
        # نرمال‌سازی فاصله‌ها
        text = re.sub(r'[\u200c\u200d\u200e\u200f]+', '\u200c', text)  # نیم‌فاصله
        text = re.sub(r'[ \t]+', ' ', text)  # فاصله‌های متعدد
        
        # نرمال‌سازی اعداد فارسی و عربی
        persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
        arabic_to_english = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
        text = text.translate(persian_to_english).translate(arabic_to_english)
        
        # حذف خطوط خالی متعدد
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    def _extract_article_number(self, line: str) -> Optional[int]:
        """استخراج شماره ماده از خط"""
        for pattern in self.patterns['article_number']:
            match = re.search(pattern, line)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
    
    def _process_line(self, line: str, all_lines: List[str], index: int):
        """پردازش یک خط از محتوا"""
        if not line:
            return
        
        # متن ماده
        if self._matches_any(line, self.patterns['text_start']):
            self.current_article['text'] = self._extract_content(line)
        
        # شرح و توضیح
        elif self._matches_any(line, self.patterns['explanation_start']):
            self.current_article['explanation'] = self._extract_content(line)
        
        # مثال‌ها
        elif self._matches_any(line, self.patterns['example_start']):
            examples = self._extract_content(line)
            self.current_article['examples'] = self._split_examples(examples)
        
        # نکات کلیدی
        elif self._matches_any(line, self.patterns['keypoints_start']):
            # خواندن نکات از خطوط بعدی
            keypoints = self._read_list_items(all_lines, index + 1)
            self.current_article['key_points'] = keypoints
        
        # برچسب‌ها
        elif self._matches_any(line, self.patterns['tags_start']):
            tags = self._extract_content(line)
            self.current_article['tags'] = self._extract_tags(tags)
        
        # منابع
        elif self._matches_any(line, self.patterns['references_start']):
            ref = self._extract_content(line)
            if ref:
                self.current_article['references'].append(ref)
        
        # اگر خطی با dash شروع شود، احتمالاً نکته کلیدی است
        elif line.startswith('-') or line.startswith('•') or line.startswith('–'):
            point = line[1:].strip()
            if point:
                self.current_article['key_points'].append(point)
        
        # اگر هیچکدام نبود، به متن اصلی اضافه کن
        elif not self.current_article['text']:
            self.current_article['text'] = line
        elif not self.current_article['explanation']:
            self.current_article['explanation'] = line
    
    def _matches_any(self, line: str, patterns: List[str]) -> bool:
        """بررسی اینکه آیا خط با هر یک از الگوها مطابقت دارد"""
        for pattern in patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return True
        return False
    
    def _extract_content(self, line: str) -> str:
        """استخراج محتوا بعد از : یا نقطه"""
        # حذف label (قبل از :)
        if ':' in line:
            content = line.split(':', 1)[1].strip()
        else:
            content = line.strip()
        return content
    
    def _split_examples(self, text: str) -> List[str]:
        """تقسیم مثال‌ها"""
        separators = [' یا ', ' و ', '،', '؛']
        examples = [text]
        
        for sep in separators:
            new_examples = []
            for ex in examples:
                new_examples.extend([e.strip() for e in ex.split(sep) if e.strip()])
            examples = new_examples
        
        return examples[:5]  # حداکثر 5 مثال
    
    def _extract_tags(self, text: str) -> List[str]:
        """استخراج تگ‌ها"""
        # حذف # از ابتدا
        tags = []
        for tag in text.split():
            tag = tag.strip().replace('#', '').replace('_', ' ')
            if tag:
                tags.append(tag)
        return tags
    
    def _read_list_items(self, lines: List[str], start_index: int) -> List[str]:
        """خواندن آیتم‌های لیست از خطوط بعدی"""
        items = []
        i = start_index
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # اگر با dash یا bullet شروع شود
            if line.startswith('-') or line.startswith('•') or line.startswith('–'):
                items.append(line[1:].strip())
                i += 1
            else:
                break
        
        return items
    
    def _finalize_article(self):
        """نهایی‌سازی و ذخیره ماده"""
        if not self.current_article:
            return
        
        # اگر عنوان خالی است، از کلمات اول متن استفاده کن
        if not self.current_article['title'] and self.current_article['text']:
            words = self.current_article['text'].split()[:5]
            self.current_article['title'] = ' '.join(words) + '...'
        
        # اگر توضیح خالی است، از متن استفاده کن
        if not self.current_article['explanation'] and self.current_article['text']:
            self.current_article['explanation'] = self.current_article['text'][:200] + '...'
        
        # اگر تگ‌ها خالی است، تگ‌های پیش‌فرض اضافه کن
        if not self.current_article['tags']:
            self.current_article['tags'] = self._auto_generate_tags()
        
        # اضافه کردن به لیست
        self.articles.append(self.current_article.copy())
        self.current_article = None
    
    def _auto_generate_tags(self) -> List[str]:
        """تولید خودکار تگ‌ها براساس محتوا"""
        tags = []
        text = (self.current_article.get('text', '') + ' ' + 
                self.current_article.get('explanation', '')).lower()
        
        # کلمات کلیدی رایج
        keywords = {
            'عقد': 'عقد',
            'معامله': 'معامله',
            'ملک': 'مالکیت',
            'مالک': 'مالکیت',
            'خرید': 'خرید_فروش',
            'فروش': 'خرید_فروش',
            'اجاره': 'اجاره',
            'وکالت': 'وکالت',
            'قرارداد': 'قرارداد',
            'تعهد': 'تعهد',
            'ضمان': 'ضمان',
            'رهن': 'رهن',
            'ازدواج': 'ازدواج',
            'طلاق': 'طلاق',
            'ارث': 'ارث',
            'شرکت': 'شرکت',
            'سهام': 'سهام',
            'چک': 'اوراق_تجاری',
            'سفته': 'اوراق_تجاری',
        }
        
        for word, tag in keywords.items():
            if word in text:
                tags.append(tag)
        
        # اگر تگی پیدا نشد، تگ category را اضافه کن
        if not tags:
            tags.append(self.current_article.get('category', 'عمومی'))
        
        return list(set(tags))[:5]  # حداکثر 5 تگ یونیک
    
    def save_to_json(self, output_file: str, articles: List[Dict]):
        """ذخیره مواد در فایل JSON"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        
        print(f"✅ ذخیره شد: {output_path.name} ({len(articles)} ماده)")
    
    def parse_and_save(self, input_file: str, output_dir: str, 
                       law_code: str, category: str = None, chunk_size: int = 20):
        """پارس و ذخیره با تقسیم به chunk ها"""
        
        print(f"📄 در حال پارس: {input_file}")
        articles = self.parse_file(input_file, law_code, category)
        
        if not articles:
            print("⚠️  هیچ ماده‌ای یافت نشد!")
            return
        
        print(f"✅ {len(articles)} ماده پارس شد")
        
        # تقسیم به chunk ها
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i in range(0, len(articles), chunk_size):
            chunk = articles[i:i + chunk_size]
            start = chunk[0]['article_number']
            end = chunk[-1]['article_number']
            
            filename = f"articles_{start:03d}-{end:03d}.json"
            self.save_to_json(output_path / filename, chunk)


def main():
    """تست پارسر"""
    parser = LawParser()
    
    # مثال استفاده
    # parser.parse_and_save(
    #     input_file='data/laws/moamlat.txt',
    #     output_dir='data/laws_structured/civil_law/transactions',
    #     law_code='civil_law',
    #     category='معاملات'
    # )
    
    print("پارسر قوانین آماده است.")
    print("\nنمونه استفاده:")
    print("""
parser = LawParser()
parser.parse_and_save(
    input_file='path/to/law.txt',
    output_dir='data/laws_structured/law_name/section',
    law_code='law_code',
    category='category_name'
)
    """)


if __name__ == '__main__':
    main()

