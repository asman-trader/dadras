#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اسکریپت اعتبارسنجی فایل‌های JSON قوانین
"""

import json
import glob
from pathlib import Path
from typing import List, Dict

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    print("⚠️  jsonschema نصب نیست. برای اعتبارسنجی کامل نصب کنید:")
    print("   pip install jsonschema")


class LawValidator:
    """کلاس اعتبارسنجی فایل‌های قانونی"""
    
    def __init__(self, base_path='data/laws_structured'):
        self.base_path = Path(base_path)
        self.schema = None
        self.errors = []
        self.warnings = []
        
        # بارگذاری schema
        schema_file = self.base_path / 'schema.json'
        if schema_file.exists():
            with open(schema_file, 'r', encoding='utf-8') as f:
                self.schema = json.load(f)
    
    def validate_all(self) -> Dict:
        """اعتبارسنجی تمام فایل‌های JSON"""
        print("🔍 شروع اعتبارسنجی...\n")
        
        results = {
            'total_files': 0,
            'valid_files': 0,
            'invalid_files': 0,
            'total_articles': 0,
            'errors': [],
            'warnings': []
        }
        
        # یافتن تمام فایل‌های articles
        article_files = list(self.base_path.glob('*/*/articles_*.json'))
        results['total_files'] = len(article_files)
        
        for file_path in article_files:
            file_result = self.validate_file(file_path)
            
            if file_result['valid']:
                results['valid_files'] += 1
                results['total_articles'] += file_result['article_count']
                print(f"✅ {file_path.relative_to(self.base_path)} - {file_result['article_count']} ماده")
            else:
                results['invalid_files'] += 1
                print(f"❌ {file_path.relative_to(self.base_path)}")
                results['errors'].extend(file_result['errors'])
        
        # اعتبارسنجی metadata files
        metadata_files = list(self.base_path.glob('*/metadata.json'))
        for file_path in metadata_files:
            if self.validate_metadata(file_path):
                print(f"✅ {file_path.relative_to(self.base_path)}")
            else:
                print(f"❌ {file_path.relative_to(self.base_path)}")
        
        # اعتبارسنجی index.json
        index_file = self.base_path / 'index.json'
        if index_file.exists():
            if self.validate_index(index_file):
                print(f"✅ index.json")
            else:
                print(f"❌ index.json")
        
        return results
    
    def validate_file(self, file_path: Path) -> Dict:
        """اعتبارسنجی یک فایل"""
        result = {
            'valid': True,
            'article_count': 0,
            'errors': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                articles = json.load(f)
            
            if not isinstance(articles, list):
                result['valid'] = False
                result['errors'].append(f"{file_path.name}: فایل باید آرایه‌ای از مواد باشد")
                return result
            
            result['article_count'] = len(articles)
            
            # اعتبارسنجی با schema
            if JSONSCHEMA_AVAILABLE and self.schema:
                try:
                    jsonschema.validate(articles, self.schema)
                except jsonschema.ValidationError as e:
                    result['valid'] = False
                    result['errors'].append(f"{file_path.name}: {e.message}")
            
            # بررسی دستی فیلدهای الزامی
            for i, article in enumerate(articles):
                errors = self._validate_article(article, i+1)
                if errors:
                    result['valid'] = False
                    result['errors'].extend([f"{file_path.name}: {e}" for e in errors])
            
        except json.JSONDecodeError as e:
            result['valid'] = False
            result['errors'].append(f"{file_path.name}: خطای JSON - {e}")
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"{file_path.name}: {str(e)}")
        
        return result
    
    def _validate_article(self, article: Dict, index: int) -> List[str]:
        """اعتبارسنجی یک ماده"""
        errors = []
        
        # فیلدهای الزامی
        required = ['article_number', 'title', 'text', 'explanation', 'tags', 'category', 'status']
        for field in required:
            if field not in article:
                errors.append(f"ماده {index}: فیلد '{field}' الزامی است")
        
        # بررسی نوع داده‌ها
        if 'article_number' in article and not isinstance(article['article_number'], int):
            errors.append(f"ماده {index}: article_number باید عدد باشد")
        
        if 'tags' in article and not isinstance(article['tags'], list):
            errors.append(f"ماده {index}: tags باید آرایه باشد")
        
        # بررسی طول متن
        if 'text' in article and len(article['text']) < 10:
            errors.append(f"ماده {index}: متن ماده خیلی کوتاه است")
        
        # بررسی status
        valid_statuses = ['active', 'deprecated', 'modified', 'repealed']
        if 'status' in article and article['status'] not in valid_statuses:
            errors.append(f"ماده {index}: status نامعتبر است")
        
        return errors
    
    def validate_metadata(self, file_path: Path) -> bool:
        """اعتبارسنجی فایل metadata"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            required = ['code', 'title', 'sections', 'status']
            for field in required:
                if field not in metadata:
                    print(f"  ⚠️  فیلد '{field}' موجود نیست")
                    return False
            
            return True
        except Exception as e:
            print(f"  ❌ خطا: {e}")
            return False
    
    def validate_index(self, file_path: Path) -> bool:
        """اعتبارسنجی فایل index"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            required = ['version', 'laws', 'categories', 'statistics']
            for field in required:
                if field not in index:
                    print(f"  ⚠️  فیلد '{field}' موجود نیست")
                    return False
            
            return True
        except Exception as e:
            print(f"  ❌ خطا: {e}")
            return False
    
    def print_summary(self, results: Dict):
        """چاپ خلاصه نتایج"""
        print("\n" + "="*60)
        print("📊 خلاصه اعتبارسنجی")
        print("="*60)
        print(f"تعداد کل فایل‌ها: {results['total_files']}")
        print(f"✅ معتبر: {results['valid_files']}")
        print(f"❌ نامعتبر: {results['invalid_files']}")
        print(f"📝 تعداد کل مواد: {results['total_articles']}")
        
        if results['errors']:
            print(f"\n❌ خطاها ({len(results['errors'])}):")
            for error in results['errors'][:10]:  # نمایش 10 خطای اول
                print(f"  - {error}")
            if len(results['errors']) > 10:
                print(f"  ... و {len(results['errors']) - 10} خطای دیگر")
        
        print("="*60)


def main():
    """تابع اصلی"""
    validator = LawValidator()
    results = validator.validate_all()
    validator.print_summary(results)
    
    if results['invalid_files'] > 0:
        exit(1)
    else:
        print("\n✨ تمام فایل‌ها معتبر هستند!")
        exit(0)


if __name__ == '__main__':
    main()

