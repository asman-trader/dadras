# 🚀 راهنمای سریع: سیستم تحلیل پرونده

## 📌 شروع سریع (5 دقیقه)

### گام 1: جمع‌آوری اطلاعات

```javascript
// فراخوانی endpoint گفتگو
const response = await fetch('/case/conversation/next', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    case_title: 'عنوان پرونده',
    case_type: 'civil',
    case_info: {},
    conversation_history: [],
    user_answer: 'پاسخ کاربر'
  })
});

const data = await response.json();
// data.question → سوال بعدی
// data.complete → آیا تمام شد؟
// data.smart_questions → سوالات تکمیلی
```

### گام 2: تحلیل جامع

```javascript
// فراخوانی endpoint تحلیل جامع
const analysis = await fetch('/case/comprehensive-analysis', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    case_info: {
      case_title: 'مطالبه وجه',
      case_type: 'commercial',
      client_name: 'علی محمدی',
      incident_description: 'شرح ماجرا...',
      // ... سایر اطلاعات
    },
    include_ai: true  // استفاده از AI
  })
});

const result = await analysis.json();
// result.ai_analysis → تحلیل هوشمند
// result.relevant_laws → قوانین مرتبط
// result.outcome_prediction → پیش‌بینی نتایج
// result.smart_questions → سوالات تکمیلی
```

## 🎯 API Endpoints

### 1️⃣ گفتگو برای جمع‌آوری اطلاعات
```
POST /case/conversation/next
```

**ورودی:**
```json
{
  "case_title": "عنوان پرونده",
  "case_type": "civil",
  "case_info": {},
  "conversation_history": [],
  "user_answer": "پاسخ کاربر",
  "current_question_id": "greeting"
}
```

**خروجی (در حین گفتگو):**
```json
{
  "ok": true,
  "complete": false,
  "question": "سوال بعدی",
  "question_id": "contact",
  "case_info": { ... }
}
```

**خروجی (پایان گفتگو):**
```json
{
  "ok": true,
  "complete": true,
  "summary": { ... },
  "summary_text": "خلاصه کامل...",
  "detected_type": "commercial",
  "smart_questions": ["سوال 1", "سوال 2"],
  "next_step": "comprehensive_analysis"
}
```

### 2️⃣ تحلیل جامع پرونده
```
POST /case/comprehensive-analysis
```

**ورودی:**
```json
{
  "case_info": {
    "case_title": "عنوان",
    "case_type": "criminal",
    "incident_description": "شرح ماجرا...",
    "available_documents": "مدارک موجود...",
    // ... سایر اطلاعات
  },
  "include_ai": true
}
```

**خروجی:**
```json
{
  "ok": true,
  "base_analysis": {
    "current_stage": { "name": "قبل از شکایت" },
    "urgent_actions": ["اقدام 1", "اقدام 2"],
    "strategy": "استراتژی پیشنهادی...",
    "risks": ["ریسک 1"],
    "opportunities": ["فرصت 1"]
  },
  "ai_analysis": "تحلیل کامل توسط AI...",
  "relevant_laws": "**قانون:** قانون مدنی\n**مواد:**...",
  "outcome_prediction": "احتمال موفقیت: 75%...",
  "prediction_score": 75,
  "smart_questions": ["سوال 1", "سوال 2"],
  "next_actions": ["گام 1", "گام 2"],
  "checklist": [
    {"id": 1, "task": "کار 1", "status": "pending", "priority": "high"}
  ],
  "summary": {
    "case_title": "...",
    "has_ai_analysis": true,
    "has_laws": true,
    "has_prediction": true
  }
}
```

### 3️⃣ دریافت سوالات تکمیلی
```
POST /case/smart-questions
```

**ورودی:**
```json
{
  "case_info": {
    "case_type": "family",
    "incident_description": "شرح..."
  }
}
```

**خروجی:**
```json
{
  "ok": true,
  "questions": [
    "آیا فرزند دارید؟",
    "آیا مهریه پرداخت شده؟",
    "آیا توافق قبلی وجود دارد؟"
  ]
}
```

## 💡 مثال‌های عملی

### مثال 1: پرونده کامل

```javascript
// 1. شروع گفتگو
let caseInfo = {};
let conversationHistory = [];

// حلقه گفتگو
while (true) {
  const response = await fetch('/case/conversation/next', {
    method: 'POST',
    body: JSON.stringify({
      case_title: 'مطالبه وجه چک',
      case_info: caseInfo,
      conversation_history: conversationHistory,
      user_answer: userInput
    })
  });
  
  const data = await response.json();
  
  if (data.complete) {
    // گفتگو تمام شد
    console.log('خلاصه:', data.summary_text);
    console.log('سوالات تکمیلی:', data.smart_questions);
    caseInfo = data.case_info;
    break;
  } else {
    // نمایش سوال بعدی
    console.log('سوال:', data.question);
    // دریافت پاسخ کاربر
    userInput = await getUserInput();
    caseInfo = data.case_info;
  }
}

// 2. تحلیل جامع
const analysisResponse = await fetch('/case/comprehensive-analysis', {
  method: 'POST',
  body: JSON.stringify({
    case_info: caseInfo,
    include_ai: true
  })
});

const analysis = await analysisResponse.json();

console.log('تحلیل AI:', analysis.ai_analysis);
console.log('قوانین:', analysis.relevant_laws);
console.log('پیش‌بینی:', analysis.outcome_prediction);
console.log('امتیاز موفقیت:', analysis.prediction_score);
```

### مثال 2: تحلیل سریع (بدون گفتگو)

```javascript
// اگر اطلاعات پرونده از قبل وجود دارد
const quickAnalysis = await fetch('/case/comprehensive-analysis', {
  method: 'POST',
  body: JSON.stringify({
    case_info: {
      case_title: 'طلاق توافقی',
      case_type: 'family',
      complaint_side: 'خواهان',
      case_stage: 'قبل از طرح شکایت',
      incident_description: 'تمایل به طلاق توافقی...',
      available_documents: 'عقدنامه، توافقنامه',
      case_goal: 'اخذ طلاق به صورت توافقی'
    },
    include_ai: true
  })
});

const result = await quickAnalysis.json();
// استفاده از نتایج...
```

### مثال 3: فقط سوالات تکمیلی

```javascript
const questionsResponse = await fetch('/case/smart-questions', {
  method: 'POST',
  body: JSON.stringify({
    case_info: {
      case_type: 'criminal',
      incident_description: 'کلاهبرداری اینترنتی...'
    }
  })
});

const { questions } = await questionsResponse.json();
questions.forEach(q => console.log('❓', q));
```

## 🔧 تنظیمات

### فعال‌سازی AI

در فایل `.env` یا `data/config.json`:

```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
USE_DEEPSEEK=1
```

### غیرفعال کردن AI (Fallback Mode)

```javascript
// در فراخوانی API
{
  "case_info": { ... },
  "include_ai": false  // استفاده از الگوریتم‌های کلاسیک
}
```

## ⚡ نکات بهینه‌سازی

### 1. کش کردن نتایج

```javascript
// ذخیره نتایج تحلیل
const cacheKey = `analysis_${caseInfo.case_id}`;
localStorage.setItem(cacheKey, JSON.stringify(analysis));

// بازیابی
const cached = localStorage.getItem(cacheKey);
if (cached) {
  analysis = JSON.parse(cached);
}
```

### 2. نمایش تدریجی

```javascript
// نمایش اطلاعات به تدریج (بهتر برای UX)
fetch('/case/comprehensive-analysis', { ... })
  .then(res => res.json())
  .then(data => {
    // نمایش تحلیل پایه
    showBaseAnalysis(data.base_analysis);
    
    // نمایش تحلیل AI (ممکن است کمی طول بکشد)
    if (data.ai_analysis) {
      showAIAnalysis(data.ai_analysis);
    }
    
    // نمایش سایر بخش‌ها
    showLaws(data.relevant_laws);
    showPrediction(data.outcome_prediction);
  });
```

### 3. مدیریت خطا

```javascript
try {
  const response = await fetch('/case/comprehensive-analysis', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  const data = await response.json();
  
  if (!data.ok) {
    throw new Error(data.error || 'خطای ناشناخته');
  }
  
  // استفاده از data
  
} catch (error) {
  console.error('خطا در تحلیل:', error);
  // نمایش پیغام به کاربر
  showError('متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید.');
  
  // Fallback: استفاده از تحلیل بدون AI
  // ...
}
```

## 📊 نمونه پاسخ کامل

```json
{
  "ok": true,
  "base_analysis": {
    "current_stage": {
      "name": "قبل از شکایت",
      "actions": ["بررسی اولیه", "جمع‌آوری مدارک", "تنظیم دادخواست"],
      "documents": ["دادخواست", "ضمائم", "محاسبه خسارت"]
    },
    "urgent_actions": [
      "📝 تنظیم دادخواست",
      "📄 جمع‌آوری مدارک",
      "💰 محاسبه خسارت و هزینه"
    ],
    "strategy": "**استراتژی تهاجمی:**\n• جمع‌آوری حداکثر مدارک...",
    "risks": ["⚠️ عدم وجود مدارک کافی"],
    "opportunities": ["✅ وجود مدارک و مستندات"]
  },
  "ai_analysis": "**نقاط قوت پرونده:**\n1. وجود مستندات قوی...\n\n**نقاط ضعف:**\n1. عدم ثبت رسمی...",
  "relevant_laws": "**قانون:** قانون تجارت\n**مواد مرتبط:**\n- ماده 310: صدور چک...",
  "outcome_prediction": "**احتمال موفقیت کامل:** 75%\nبا توجه به...",
  "prediction_score": 75,
  "smart_questions": [
    "آیا چک دارای تاریخ سررسید بود؟",
    "آیا مبلغ چک مطابق قرارداد است؟",
    "آیا گواهی عدم پرداخت دریافت کرده‌اید؟"
  ],
  "next_actions": [
    "📝 **گام 1:** تنظیم دادخواست با جزئیات کامل",
    "📎 **گام 2:** جمع‌آوری و مرتب‌سازی تمام مدارک"
  ],
  "checklist": [
    {"id": 1, "task": "جمع‌آوری کامل مدارک", "status": "pending", "priority": "high"},
    {"id": 2, "task": "تنظیم دادخواست", "status": "pending", "priority": "high"}
  ],
  "summary": {
    "case_title": "مطالبه وجه چک",
    "case_type": "commercial",
    "stage": "قبل از شکایت",
    "has_ai_analysis": true,
    "has_laws": true,
    "has_prediction": true
  }
}
```

## 🎯 چک‌لیست توسعه

برای استفاده در Frontend:

- [ ] پیاده‌سازی UI گفتگو
- [ ] نمایش تدریجی نتایج تحلیل
- [ ] ذخیره‌سازی اطلاعات در localStorage
- [ ] مدیریت خطاها
- [ ] نمایش چک‌لیست اقدامات
- [ ] دکمه‌های اقدام سریع
- [ ] Export گزارش PDF
- [ ] اشتراک‌گذاری نتایج

## ❓ سوالات متداول

**Q: آیا بدون API کی AI کار می‌کند؟**  
A: بله، سیستم Fallback دارد و با الگوریتم‌های کلاسیک کار می‌کند.

**Q: چگونه دقت تحلیل را بهبود دهم؟**  
A: اطلاعات کامل‌تری در `incident_description` وارد کنید و `available_documents` را دقیق ذکر کنید.

**Q: آیا می‌توان فقط بخشی از تحلیل را دریافت کرد؟**  
A: خیر، endpoint جامع همه بخش‌ها را بر می‌گرداند. برای سوالات می‌توانید از `/case/smart-questions` استفاده کنید.

**Q: چگونه عملکرد را بهینه کنم؟**  
A: از کش استفاده کنید و نتایج را در localStorage ذخیره کنید. همچنین `include_ai: false` برای سرعت بیشتر.

---

**آماده برای شروع؟** 🚀

```bash
# راه‌اندازی سرور
python app.py

# تست API
curl -X POST http://localhost:5000/case/comprehensive-analysis \
  -H "Content-Type: application/json" \
  -d '{"case_info": {...}, "include_ai": true}'
```

**موفق باشید!** 🎉

