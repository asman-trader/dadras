# 📊 راهنمای تایم‌لاین عمودی روند دادرسی

## 🎯 هدف

تایم‌لاین عمودی یک **نمای بصری زنده** از روند پرونده حقوقی است که:
- ✅ **خودکار** مرحله فعلی را تشخیص می‌دهد
- ✅ در **سمت چپ** (راست صفحه در RTL) به صورت **ثابت** نمایش داده می‌شود
- ✅ وضعیت هر مرحله را با رنگ‌ها و انیمیشن نشان می‌دهد
- ✅ فقط برای **پرونده‌ها** نمایش داده می‌شود، نه چت‌های عادی

> 📝 **نکته:** این timeline جایگزین timeline افقی قدیمی شده است که حذف شد.

---

## 🎨 ویژگی‌های بصری

### موقعیت و طراحی

```
📍 موقعیت: Fixed در سمت چپ (right: 16px)
📏 عرض: 220px
🔝 فاصله از بالا: 80px
📱 پاسخگو: مخفی می‌شود در عرض‌های کمتر از 1280px
```

### وضعیت‌های مرحله

#### 1️⃣ مراحل گذشته (Completed)
- ✅ نقطه سبز روشن با گرادیانت
- ✅ تیک سبز در نقطه
- ✅ متن سبز رنگ
- ✅ سایه نور دور نقطه

#### 2️⃣ مرحله فعلی (Active)
- 🟢 نقطه سبز روشن با انیمیشن پالس
- 🟢 متن سبز bold
- 🟢 انیمیشن نبض (pulse) مداوم

#### 3️⃣ مراحل آینده (Pending)
- ⚪ نقطه خاکستری
- ⚪ متن خاکستری روشن

---

## 🔄 مراحل دادرسی

تایم‌لاین شامل 8 مرحله اصلی است:

### 1. قبل از شکایت
```
🔹 شناسه: pre_complaint
🔹 توضیح: جمع‌آوری مدارک و تنظیم دادخواست
🔹 اقدامات: جمع‌آوری مدارک، مشاوره حقوقی
```

### 2. ثبت دادخواست
```
🔹 شناسه: complaint_filed
🔹 توضیح: ارائه به دادگاه و دریافت شماره
🔹 اقدامات: ثبت در دادگاه، پرداخت هزینه
```

### 3. بررسی اولیه
```
🔹 شناسه: case_review
🔹 توضیح: ارجاع به شعبه و تعیین وقت
🔹 اقدامات: ارجاع به شعبه، تعیین وقت رسیدگی
```

### 4. جلسه دادگاه
```
🔹 شناسه: court_session
🔹 توضیح: رسیدگی و ارائه دفاعیات
🔹 اقدامات: حضور در جلسه، ارائه دفاعیه
```

### 5. صدور رأی
```
🔹 شناسه: verdict
🔹 توضیح: تصمیم دادگاه و ابلاغ رأی
🔹 اقدامات: دریافت رأی، بررسی رأی
```

### 6. تجدیدنظر
```
🔹 شناسه: appeal
🔹 توضیح: اعتراض و بررسی مجدد
🔹 اقدامات: ثبت اعتراض، دادخواست تجدیدنظر
```

### 7. اجرای حکم
```
🔹 شناسه: execution
🔹 توضیح: اجرای رأی نهایی
🔹 اقدامات: مراجعه به اجرای احکام
```

### 8. پایان پرونده
```
🔹 شناسه: closed
🔹 توضیح: اتمام کامل دادرسی
🔹 وضعیت: پرونده بسته شده
```

---

## 🤖 تشخیص خودکار مرحله

سیستم با استفاده از هوش مصنوعی و تحلیل متن، مرحله فعلی را تشخیص می‌دهد:

### الگوریتم تشخیص

```javascript
function detectCaseStage(caseInfo) {
  const stageText = caseInfo.case_stage.toLowerCase();
  
  // بررسی کلمات کلیدی
  if (stageText.includes('بسته') || stageText.includes('پایان')) 
    return 'closed';
  
  if (stageText.includes('اجرا')) 
    return 'execution';
  
  if (stageText.includes('تجدید') || stageText.includes('فرجام')) 
    return 'appeal';
  
  if (stageText.includes('رأی') || stageText.includes('حکم')) 
    return 'verdict';
  
  if (stageText.includes('جلسه') || stageText.includes('دادگاه')) 
    return 'court_session';
  
  if (stageText.includes('بررسی') || stageText.includes('ارجاع')) 
    return 'case_review';
  
  if (caseInfo.case_number && caseInfo.case_number !== '(ندارد)') 
    return 'complaint_filed';
  
  return 'pre_complaint';
}
```

### کلمات کلیدی

| مرحله | کلمات کلیدی |
|-------|-------------|
| پایان | بسته، پایان، اتمام |
| اجرای حکم | اجرا، اجرای احکام |
| تجدیدنظر | تجدید، فرجام، تجدیدنظر |
| صدور رأی | رأی، حکم، صدور |
| جلسه دادگاه | جلسه، دادگاه، رسیدگی |
| بررسی اولیه | بررسی، ارجاع |
| ثبت دادخواست | وجود شماره پرونده |
| قبل از شکایت | پیش‌فرض |

---

## 💻 نحوه کار سیستم

### 1. زمان نمایش

Timeline در این موارد نمایش داده می‌شود:

```javascript
// 1. هنگام ایجاد پرونده جدید
async function startCaseIntakeWizard(caseId, ...) {
  updateVerticalTimeline(caseInfo);
}

// 2. هنگام باز کردن پرونده موجود
function updateTimelineVisibility(chatTitle) {
  if (chatTitle.startsWith('📁')) {
    refreshTimelineFromLocalStorage(currentChatId);
  }
}

// 3. بعد از تحلیل و به‌روزرسانی اطلاعات
async function analyzeCaseStatus(caseId, caseInfo) {
  updateVerticalTimeline(caseInfo);
}

// 4. بعد از تکمیل خلاصه اطلاعات
// در تابع askNextPythonQuestion
if (result.complete) {
  updateVerticalTimeline(result.case_info);
}
```

### 2. به‌روزرسانی خودکار

```javascript
function updateVerticalTimeline(caseInfo) {
  // 1. تشخیص مرحله فعلی
  const currentStage = detectCaseStage(caseInfo);
  
  // 2. محاسبه index مرحله
  const stagesOrder = ['pre_complaint', 'complaint_filed', ...];
  const currentIndex = stagesOrder.indexOf(currentStage);
  
  // 3. به‌روزرسانی وضعیت visual
  steps.forEach((step, index) => {
    if (stepIndex < currentIndex) {
      step.classList.add('completed'); // گذشته
    } else if (stepIndex === currentIndex) {
      step.classList.add('active');    // فعلی
    }
    // بقیه: pending (پیش‌فرض)
  });
  
  // 4. نمایش timeline
  timeline.style.display = 'block';
}
```

### 3. مخفی‌سازی برای چت‌های عادی

```javascript
function hideVerticalTimeline() {
  const timeline = document.getElementById('verticalCaseTimeline');
  if (timeline) {
    timeline.style.display = 'none';
  }
}
```

---

## 🎭 انیمیشن‌ها

### Pulse Animation (مرحله فعلی)

```css
@keyframes v-pulse {
  0%, 100% { 
    box-shadow: 0 0 0 4px rgba(34,197,94,.2); 
  }
  50% { 
    box-shadow: 0 0 0 8px rgba(34,197,94,0); 
  }
}
```

این انیمیشن باعث می‌شود نقطه فعلی مدام نبض بزند و توجه کاربر را جلب کند.

### Hover Effect

```css
.v-step:hover {
  transform: translateX(-2px);
}
```

هنگام hover، مرحله کمی به سمت چپ حرکت می‌کند.

---

## 📱 Responsive Design

```css
@media (max-width: 1280px) {
  #verticalCaseTimeline {
    display: none !important;
  }
}
```

در صفحات کوچک‌تر از 1280px، timeline مخفی می‌شود تا فضای بیشتری برای محتوای اصلی باشد.

---

## 🔧 نکات تکنیکی

### ساختار HTML

```html
<div id="verticalCaseTimeline">
  <div class="v-timeline-header">
    <div class="v-timeline-title">⚖️ روند دادرسی</div>
  </div>
  
  <div class="v-timeline-steps">
    <div class="v-timeline-line"></div>
    
    <div class="v-step" data-stage="pre_complaint">
      <div class="v-step-dot">1</div>
      <div class="v-step-content">
        <div class="v-step-title">قبل از شکایت</div>
        <div class="v-step-desc">جمع‌آوری مدارک...</div>
      </div>
    </div>
    
    <!-- سایر مراحل -->
  </div>
</div>
```

### Positioning

```css
#verticalCaseTimeline {
  position: fixed;      /* ثابت در صفحه */
  right: 16px;          /* فاصله از راست */
  top: 80px;            /* فاصله از بالا */
  z-index: 40;          /* بالای محتوا */
}
```

### خط اتصال مراحل

```css
.v-timeline-line {
  position: absolute;
  right: 20px;          /* وسط نقاط */
  top: 12px;
  bottom: 12px;
  width: 2px;
  background: linear-gradient(180deg, 
    rgba(34,197,94,.3) 0%, 
    rgba(100,116,139,.15) 100%
  );
}
```

---

## 🎨 رنگ‌بندی

### پالت رنگی

```
🟢 سبز فعال:    #22c55e (accent)
🟢 سبز تیره:    #16a34a (dark accent)
⚪ خاکستری:     #64748b (muted)
⚫ تیره:        #0f141b (background)
```

### گرادیانت‌ها

```css
/* پس‌زمینه timeline */
background: linear-gradient(135deg, 
  rgba(15,20,27,.98) 0%, 
  rgba(11,15,20,.95) 100%
);

/* نقطه فعلی */
background: linear-gradient(135deg, 
  #22c55e 0%, 
  #16a34a 100%
);
```

---

## 📊 مثال عملی

### سناریو: پرونده در مرحله "جلسه دادگاه"

```javascript
const caseInfo = {
  case_stage: "پرونده در مرحله جلسه دادگاه است",
  case_number: "1402/123/456",
  // ... سایر اطلاعات
};

// تشخیص: court_session
detectCaseStage(caseInfo); // → "court_session"

// نتیجه visual:
// ✅ قبل از شکایت     (completed - سبز)
// ✅ ثبت دادخواست      (completed - سبز)
// ✅ بررسی اولیه       (completed - سبز)
// 🟢 جلسه دادگاه      (active - سبز با pulse)
// ⚪ صدور رأی         (pending - خاکستری)
// ⚪ تجدیدنظر         (pending - خاکستری)
// ⚪ اجرای حکم        (pending - خاکستری)
// ⚪ پایان پرونده     (pending - خاکستری)
```

---

## ✅ مزایا

### برای کاربران:

1. **درک سریع**: با یک نگاه می‌دانند پرونده در کجاست
2. **شفافیت**: مراحل گذشته و آینده مشخص است
3. **انگیزه**: دیدن پیشرفت انگیزه‌بخش است
4. **راهنمایی**: می‌دانند چه اقداماتی انجام شده و چه باید انجام شود

### برای سیستم:

1. **خودکار**: نیاز به ورودی دستی ندارد
2. **هوشمند**: بر اساس تحلیل متن
3. **قابل اطمینان**: همیشه به‌روز است
4. **زیبا**: طراحی مدرن و حرفه‌ای

---

## 🚀 آینده

### پیشنهادات توسعه:

- [ ] **تاریخ‌ها**: نمایش تاریخ هر مرحله
- [ ] **یادداشت‌ها**: امکان افزودن یادداشت به هر مرحله
- [ ] **اسناد**: لینک اسناد مربوط به هر مرحله
- [ ] **اعلان‌ها**: هشدار برای ضرب‌الاجل‌ها
- [ ] **گزارش**: PDF خروجی از تایم‌لاین
- [ ] **اشتراک‌گذاری**: به اشتراک‌گذاری با موکل

---

## 🎯 خلاصه

تایم‌لاین عمودی یک **ابزار بصری قدرتمند** است که:

✅ مرحله پرونده را **خودکار** تشخیص می‌دهد  
✅ در **سمت چپ** به صورت **ثابت** نمایش داده می‌شود  
✅ با **انیمیشن‌ها** و **رنگ‌ها** جذاب است  
✅ فقط برای **پرونده‌ها** فعال است  
✅ **همیشه به‌روز** است  

**نتیجه:** کاربر همیشه می‌داند پرونده‌اش کجاست و چه مراحلی در پیش است! 🎉

