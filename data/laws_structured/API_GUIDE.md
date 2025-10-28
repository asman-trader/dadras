# 🔌 راهنمای API سیستم قوانین

راهنمای استفاده از API های Flask برای دسترسی به قوانین.

## 📡 Endpoints موجود

### 1. دریافت فهرست کلی قوانین

```http
GET /api/laws
```

**پاسخ:**
```json
{
  "success": true,
  "data": {
    "total_laws": 1,
    "laws": [...]
  }
}
```

**مثال Python:**
```python
import requests

response = requests.get('http://localhost:5000/api/laws')
data = response.json()
print(f"تعداد قوانین: {data['data']['total_laws']}")
```

---

### 2. دریافت اطلاعات یک قانون خاص

```http
GET /api/laws/{law_code}
```

**پارامترها:**
- `law_code`: کد قانون (مثل `civil_law`)

**مثال:**
```python
response = requests.get('http://localhost:5000/api/laws/civil_law')
law = response.json()
print(law['data']['title'])  # قانون مدنی
```

---

### 3. دریافت مواد یک بخش

```http
GET /api/laws/{law_code}/sections/{section_code}
```

**پارامترها:**
- `law_code`: کد قانون
- `section_code`: کد بخش (مثل `transactions`)

**مثال:**
```python
response = requests.get('http://localhost:5000/api/laws/civil_law/sections/transactions')
articles = response.json()
for article in articles['data']:
    print(f"ماده {article['article_number']}: {article['title']}")
```

---

### 4. دریافت یک ماده خاص

```http
GET /api/laws/{law_code}/articles/{article_number}
```

**مثال:**
```python
response = requests.get('http://localhost:5000/api/laws/civil_law/articles/183')
article = response.json()
print(article['data']['text'])
```

---

### 5. جستجو در قوانین

```http
POST /api/laws/search
Content-Type: application/json
```

**Body:**
```json
{
  "query": "عقد",
  "law_code": "civil_law",
  "section_code": "transactions",
  "limit": 10
}
```

**مثال:**
```python
search_data = {
    "query": "مالکیت",
    "limit": 5
}
response = requests.post('http://localhost:5000/api/laws/search', json=search_data)
results = response.json()

for result in results['data']:
    print(f"ماده {result['article_number']}: {result['title']}")
    print(f"امتیاز: {result['score']}")
```

---

### 6. جستجو براساس تگ

```http
GET /api/laws/tags/{tag}
```

**مثال:**
```python
response = requests.get('http://localhost:5000/api/laws/tags/عقد')
articles = response.json()
print(f"یافت شد: {len(articles['data'])} ماده")
```

---

### 7. دریافت مواد مرتبط

```http
GET /api/laws/{law_code}/articles/{article_number}/related
```

**مثال:**
```python
response = requests.get('http://localhost:5000/api/laws/civil_law/articles/183/related')
related = response.json()
for article in related['data']:
    print(f"ماده {article['article_number']}: {article['title']}")
```

---

## 🔍 جستجوی پیشرفته (RAG)

### Semantic Search با Embedding

```http
POST /api/laws/semantic-search
Content-Type: application/json
```

**Body:**
```json
{
  "query": "در چه شرایطی یک عقد باطل است؟",
  "top_k": 5,
  "min_score": 0.7
}
```

**مثال:**
```python
query_data = {
    "query": "حقوق و تکالیف مالک چیست؟",
    "top_k": 3
}
response = requests.post('http://localhost:5000/api/laws/semantic-search', json=query_data)
results = response.json()

for result in results['data']:
    print(f"\n📄 ماده {result['article_number']}")
    print(f"📊 امتیاز: {result['score']:.2f}")
    print(f"📝 {result['explanation']}")
```

---

## 💡 نمونه کدهای کاربردی

### 1. دریافت context برای LLM

```python
def get_law_context(law_code, article_numbers):
    """دریافت متن کامل چند ماده برای ارسال به LLM"""
    context = []
    
    for num in article_numbers:
        response = requests.get(f'/api/laws/{law_code}/articles/{num}')
        if response.status_code == 200:
            article = response.json()['data']
            context.append(f"""
ماده {article['article_number']}: {article['title']}
{article['text']}

توضیح: {article['explanation']}
""")
    
    return "\n---\n".join(context)

# استفاده
context = get_law_context('civil_law', [183, 184, 185])
print(context)
```

---

### 2. Cache کردن قوانین پرکاربرد

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_article(law_code, article_number):
    """دریافت ماده با cache"""
    response = requests.get(f'/api/laws/{law_code}/articles/{article_number}')
    return response.json()

# بار اول از سرور می‌گیرد
article = get_cached_article('civil_law', 183)

# بار دوم از cache استفاده می‌کند
article = get_cached_article('civil_law', 183)  # سریع‌تر!
```

---

### 3. جستجوی چندگانه موازی

```python
from concurrent.futures import ThreadPoolExecutor

def search_multiple_tags(tags):
    """جستجوی موازی در چند تگ"""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(requests.get, f'/api/laws/tags/{tag}'): tag 
            for tag in tags
        }
        
        results = {}
        for future in futures:
            tag = futures[future]
            response = future.result()
            results[tag] = response.json()['data']
        
        return results

# استفاده
tags = ['عقد', 'مالکیت', 'معامله']
all_results = search_multiple_tags(tags)

for tag, articles in all_results.items():
    print(f"{tag}: {len(articles)} ماده")
```

---

## 🛡️ Error Handling

تمام API ها ساختار خطای یکسانی دارند:

```json
{
  "success": false,
  "error": "توضیح خطا",
  "code": "ERROR_CODE"
}
```

**نمونه کد:**
```python
def safe_api_call(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        return {"success": False, "error": "زمان انتظار تمام شد"}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}
```

---

## 📊 Rate Limiting

- **حد مجاز**: 100 درخواست در دقیقه
- **Header**: `X-RateLimit-Remaining`
- **پاسخ 429**: بیش از حد درخواست

**بررسی rate limit:**
```python
response = requests.get('/api/laws')
remaining = response.headers.get('X-RateLimit-Remaining')
print(f"درخواست باقیمانده: {remaining}")
```

---

## 🔐 Authentication

برای API های عمومی احتیاج به authentication نیست، اما برای API های ادمین:

```python
headers = {
    'Authorization': f'Bearer {access_token}'
}
response = requests.post('/api/admin/laws', headers=headers, json=data)
```

---

## 📝 نمونه کامل: ساخت چت‌بات قانونی

```python
import requests
from typing import List, Dict

class LawBot:
    def __init__(self, base_url='http://localhost:5000'):
        self.base_url = base_url
    
    def ask(self, question: str) -> str:
        """پرسش از چت‌بات"""
        # 1. جستجوی معنایی
        search_response = requests.post(
            f'{self.base_url}/api/laws/semantic-search',
            json={'query': question, 'top_k': 3}
        )
        articles = search_response.json()['data']
        
        # 2. ساخت context
        context = self._build_context(articles)
        
        # 3. ارسال به LLM
        llm_response = self._ask_llm(question, context)
        
        return llm_response
    
    def _build_context(self, articles: List[Dict]) -> str:
        parts = []
        for article in articles:
            parts.append(f"""
ماده {article['article_number']}: {article['title']}
{article['text']}
{article['explanation']}
""")
        return "\n---\n".join(parts)
    
    def _ask_llm(self, question: str, context: str) -> str:
        # ارسال به API LLM (مثل OpenAI یا مدل محلی)
        prompt = f"""
براساس قوانین زیر به سوال پاسخ بده:

{context}

سوال: {question}
پاسخ:
"""
        # ... کد ارسال به LLM
        return "پاسخ از LLM"

# استفاده
bot = LawBot()
answer = bot.ask("عقد چیست؟")
print(answer)
```

---

**نسخه API**: 1.0.0  
**آخرین به‌روزرسانی**: 1404/08/06

