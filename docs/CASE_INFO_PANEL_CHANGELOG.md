# 📋 Changelog - پنل اطلاعات پرونده

## 🎉 نسخه 1.0.0 - اکتبر 2025

### ✨ ویژگی‌های جدید

#### 1. پنل اطلاعات زنده در سمت راست
- ✅ اضافه شدن ستون ثابت در سمت راست با 8 فیلد اطلاعاتی
- ✅ نمایش خودکار برای پرونده‌ها
- ✅ مخفی شدن خودکار برای چت‌های عادی
- ✅ Responsive design (فقط در صفحات بزرگ‌تر از 1600px)

#### 2. استخراج خودکار اطلاعات با AI
- ✅ Endpoint جدید `/api/extract-case-info` برای استخراج اطلاعات
- ✅ استفاده از DeepSeek AI برای تشخیص و استخراج
- ✅ ادغام هوشمند اطلاعات جدید با اطلاعات فعلی
- ✅ به‌روزرسانی خودکار بعد از هر پاسخ AI

#### 3. Context-Aware AI
- ✅ ارسال اطلاعات پرونده به AI در هر سوال
- ✅ اضافه کردن context پرونده به prompt
- ✅ پاسخ‌های شخصی‌سازی شده بر اساس اطلاعات پرونده
- ✅ توجه AI به موکل، طرف مقابل و مرحله پرونده

#### 4. طراحی UI پیشرفته
- ✅ رنگ‌بندی یکپارچه با theme برنامه
- ✅ Badge زنده برای نمایش به‌روزرسانی خودکار
- ✅ Highlight فیلدهای مهم
- ✅ انیمیشن fadeInOut برای indicator
- ✅ Scrollbar سفارشی

### 🔧 تغییرات Backend

#### `app.py`
```diff
+ @app.post('/api/extract-case-info')
+ def extract_case_info():
+     # استخراج خودکار اطلاعات از پیام AI

@app.post('/ask')
def ask_endpoint():
+   case_info = data.get('case_info', {})
-   ok, ds_text = _deepseek_chat(question, rag_context, thinking_time, role)
+   ok, ds_text = _deepseek_chat(question, rag_context, thinking_time, role, case_info)

- def _deepseek_chat(question: str, context: str, thinking_time: int = 0, role: str = 'default'):
+ def _deepseek_chat(question: str, context: str, thinking_time: int = 0, role: str = 'default', case_info: dict = None):
+   # اضافه کردن اطلاعات پرونده به prompt
```

### 🎨 تغییرات Frontend

#### `templates/index.html`

**CSS:**
```diff
+ /* پنل اطلاعات پرونده در سمت راست */
+ #caseInfoPanel { ... }
+ .case-info-header { ... }
+ .case-info-section { ... }
+ @keyframes fadeInOut { ... }

@media (min-width: 1600px) {
+   body.case-info-active main {
+     padding-right: 312px;
+   }
}
```

**HTML:**
```diff
+ <!-- پنل اطلاعات پرونده سمت راست -->
+ <div id="caseInfoPanel">
+   <div class="case-info-header">...</div>
+   <div id="caseInfoContent">...</div>
+ </div>
```

**JavaScript:**
```diff
+ function updateCaseInfoPanel(caseInfo) { ... }
+ function hideCaseInfoPanel() { ... }
+ function getCaseTypeLabel(type) { ... }
+ function getComplaintSideLabel(side) { ... }
+ function getCaseStageLabel(stage) { ... }
+ async function extractInfoFromAIResponse(aiMessage, currentCaseInfo) { ... }

function refreshTimelineFromLocalStorage(caseId) {
    updateVerticalTimeline(caseInfo);
+   updateCaseInfoPanel(caseInfo);
}

function updateTimelineVisibility(chatTitle) {
    if(chatTitle && chatTitle.startsWith('📁')){
        refreshTimelineFromLocalStorage(currentChatId);
    } else {
        hideVerticalTimeline();
+       hideCaseInfoPanel();
    }
}

async function ask() {
+   // اضافه کردن اطلاعات پرونده به سوال
+   let requestBody = {question:text, thinking_time: selectedThinkingTime, role: selectedRole};
+   if(selectedRole === 'lawyer' && currentChatId){
+     const caseInfoJson = localStorage.getItem(`case_info_${currentChatId}`);
+     if(caseInfoJson){
+       requestBody.case_info = JSON.parse(caseInfoJson);
+     }
+   }
    
+   // استخراج خودکار اطلاعات بعد از پاسخ AI
+   if(selectedRole === 'lawyer' && currentChatId){
+     const updatedInfo = await extractInfoFromAIResponse(j.answer, currentCaseInfo);
+     if(updatedInfo){
+       localStorage.setItem(`case_info_${currentChatId}`, JSON.stringify(updatedInfo));
+       updateCaseInfoPanel(updatedInfo);
+       updateVerticalTimeline(updatedInfo);
+     }
+   }
}
```

### 📊 فیلدهای پنل اطلاعات

| فیلد | نام فارسی | data-field |
|------|----------|------------|
| موکل | client_name | `client_name` |
| نوع پرونده | case_type | `case_type` |
| طرف مقابل | opponent_name | `opponent_name` |
| موقعیت | complaint_side | `complaint_side` |
| مرحله | case_stage | `case_stage` |
| شماره پرونده | case_number | `case_number` |
| هدف | case_goal | `case_goal` |
| مدارک | available_documents | `available_documents` |

### 🔐 امنیت

- ✅ Validation ورودی‌های کاربر
- ✅ استفاده از API key محرمانه برای DeepSeek
- ✅ Timeout برای درخواست‌های AI (15 ثانیه)
- ✅ Error handling کامل
- ✅ ذخیره محلی در localStorage (بدون ارسال به سرور در این نسخه)

### ⚡ بهینه‌سازی

- ✅ استخراج اطلاعات به صورت async و بدون مسدود کردن UI
- ✅ Cache اطلاعات در localStorage
- ✅ Lazy loading پنل (فقط برای پرونده‌ها)
- ✅ Responsive breakpoints بهینه

### 📱 سازگاری

| دستگاه | وضعیت پنل |
|--------|-----------|
| Desktop (>1600px) | ✅ نمایش کامل |
| Laptop (1280-1599px) | ❌ مخفی |
| Tablet | ❌ مخفی |
| Mobile | ❌ مخفی |

### 🐛 رفع باگ‌ها

- ✅ رفع مشکل نمایش همزمان با timeline
- ✅ رفع مشکل overlap با محتوای اصلی
- ✅ رفع linter errors مربوط به json import
- ✅ رفع مشکل به‌روزرسانی فیلدهای خالی

### 📚 مستندات

- ✅ ایجاد `CASE_INFO_PANEL_GUIDE.md`
- ✅ ایجاد `CASE_INFO_PANEL_CHANGELOG.md`
- ✅ کامنت‌گذاری کامل کد

### 🎯 نتایج

#### قبل از این به‌روزرسانی:
- ❌ AI اطلاعات پرونده را در سوالات بعدی نمی‌دانست
- ❌ کاربر باید اطلاعات را مجدداً تکرار می‌کرد
- ❌ عدم دسترسی سریع به اطلاعات کلیدی پرونده
- ❌ AI پاسخ‌های عمومی می‌داد

#### بعد از این به‌روزرسانی:
- ✅ AI تمام اطلاعات پرونده را در context دارد
- ✅ پاسخ‌های شخصی‌سازی شده و دقیق
- ✅ دسترسی فوری به اطلاعات در پنل سمت راست
- ✅ به‌روزرسانی خودکار با هر گفتگو
- ✅ تجربه کاربری بهتر و حرفه‌ای‌تر

### 🔮 آینده

#### نسخه 1.1.0 (برنامه‌ریزی شده)
- [ ] ویرایش مستقیم از پنل
- [ ] تاریخچه تغییرات
- [ ] Export به PDF
- [ ] Sync با سرور

#### نسخه 1.2.0 (ایده‌ها)
- [ ] اعلان‌های real-time
- [ ] فیلترهای پیشرفته
- [ ] گزارش‌های خودکار
- [ ] یادآوری‌های هوشمند

---

## 📞 پشتیبانی

در صورت بروز مشکل:
1. کنسول مرورگر را بررسی کنید
2. localStorage را چک کنید (`case_info_${caseId}`)
3. Network tab را برای بررسی API calls مشاهده کنید
4. Log های سرور را بررسی کنید

## 🙏 سپاسگزاری

این ویژگی با الهام از سیستم‌های مدیریت پرونده مدرن و با هدف بهبود تجربه کاربری وکلا و موکلین طراحی شده است.

