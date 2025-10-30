# 📋 قابلیت جابه‌جایی پنل اطلاعات پرونده

## 🎯 خلاصه

پنل اطلاعات پرونده حالا مانند Timeline روند دادرسی **قابل جابه‌جایی (Draggable)** و **قابل جمع شدن (Collapsible)** است و وضعیت آن در localStorage ذخیره می‌شود.

---

## 🔄 تغییرات اعمال شده

### 1️⃣ CSS - وضعیت Collapsed و Dragging

**اضافه شده:**
```css
#caseInfoPanel {
  ...
  transition: width 0.3s ease;
}

#caseInfoPanel.collapsed {
  width: 200px;  /* emoji + عنوان */
}

#caseInfoPanel.dragging {
  cursor: move;
  opacity: 0.9;
  box-shadow: 0 12px 48px rgba(0,0,0,.5);
}

#caseInfoPanel.collapsed #caseInfoContent {
  display: none;
}

#caseInfoPanel.collapsed .case-info-badge {
  display: none;
}
```

### 2️⃣ CSS - Header قابل Drag و دکمه Collapse

**قبل:**
```css
.case-info-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(59,130,246,.15);
}
```

**بعد:**
```css
.case-info-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 8px 4px 12px 4px;
  border-bottom: 1px solid rgba(59,130,246,.15);
  cursor: move;           /* ✅ نشانگر موس */
  user-select: none;      /* ✅ غیرفعال کردن انتخاب متن */
  border-radius: 12px 12px 0 0;
  margin: -16px -12px 16px -12px;
  padding: 12px;
}

.case-info-header:hover {
  background: rgba(59,130,246,.05);  /* ✅ افکت hover */
}

.case-info-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.case-info-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(59,130,246,.2);
  background: rgba(59,130,246,.1);
  color: #3b82f6;
  cursor: pointer;
  transition: all 0.2s;
}

#caseInfoPanel.collapsed .case-info-controls {
  flex-direction: column;
}
```

### 3️⃣ HTML - اضافه کردن ID و دکمه Collapse

**قبل:**
```html
<div class="case-info-header">
  <div class="case-info-title">
    <span>📋</span>
    <span>اطلاعات پرونده</span>
  </div>
  <span class="case-info-badge">زنده</span>
</div>
```

**بعد:**
```html
<div class="case-info-header" id="caseInfoDragHandle">
  <div class="case-info-title">
    <span class="emoji">📋</span>
    <span>اطلاعات پرونده</span>
  </div>
  <div class="case-info-controls">
    <button class="case-info-btn" id="caseInfoCollapseBtn" title="جمع کردن/باز کردن">
      ▶
    </button>
  </div>
  <span class="case-info-badge">زنده</span>
</div>
```

### 4️⃣ JavaScript - تابع Collapse و Drag

**جدید: `initCaseInfoControls()`**

```javascript
(function initCaseInfoControls(){
  const panel = document.getElementById('caseInfoPanel');
  const dragHandle = document.getElementById('caseInfoDragHandle');
  const collapseBtn = document.getElementById('caseInfoCollapseBtn');
  
  if(!panel || !dragHandle || !collapseBtn) return;
  
  // بارگذاری وضعیت collapsed از localStorage
  const isCollapsed = localStorage.getItem('caseinfo_collapsed') === 'true';
  if(isCollapsed){
    panel.classList.add('collapsed');
    collapseBtn.textContent = '◀';
  }
  
  // بارگذاری موقعیت از localStorage
  const savedPosition = localStorage.getItem('caseinfo_position');
  if(savedPosition){
    const pos = JSON.parse(savedPosition);
    panel.style.right = pos.right;
    panel.style.top = pos.top;
  }
  
  // Toggle collapse
  collapseBtn.addEventListener('click', (e)=>{
    e.stopPropagation();
    panel.classList.toggle('collapsed');
    const collapsed = panel.classList.contains('collapsed');
    collapseBtn.textContent = collapsed ? '◀' : '▶';
    collapseBtn.title = collapsed ? 'باز کردن' : 'جمع کردن';
    localStorage.setItem('caseinfo_collapsed', collapsed);
  });
  
  // Mouse drag
  dragHandle.addEventListener('mousedown', (e)=>{
    if(e.target.closest('.case-info-btn')) return;  // جلوگیری از drag هنگام کلیک روی دکمه
    ...
  });
  document.addEventListener('mousemove', (e)=>{...});
  document.addEventListener('mouseup', ()=>{...});
  
  // Touch drag (موبایل)
  dragHandle.addEventListener('touchstart', (e)=>{
    if(e.target.closest('.case-info-btn')) return;
    ...
  });
  document.addEventListener('touchmove', (e)=>{...});
  document.addEventListener('touchend', ()=>{...});
})();
```

---

## 🎨 نمای بصری

### قبل:
```
┌──────────────────────────────────────┐
│                                      │
│  [محتوای چت]              [پنل ⛔]  │ ← ثابت و باز
│                            اطلاعات   │
│  [پیام‌ها]                 پرونده   │
│                                      │
└──────────────────────────────────────┘
```

### بعد:
```
┌──────────────────────────────────────┐
│                                      │
│  [محتوای چت]         [پنل 👆]  [📋] │ ← قابل جابجایی + جمع شدنی
│                       اطلاعات   ▶   │
│  [پیام‌ها]            پرونده        │
│                                      │
│         [کلیک روی ▶ → جمع می‌شود] 🔄 │
└──────────────────────────────────────┘

حالت جمع شده:
┌──────────────────────────────────────┐
│              [📋 اطلاعات پرونده]    │ ← emoji + عنوان
│  [محتوای چت]              [◀]      │    عرض: 200px
│                                      │
│  [پیام‌ها]                           │
└──────────────────────────────────────┘
```

---

## ✨ ویژگی‌ها

### 1️⃣ Collapse/Expand (جمع/باز کردن)
- ✅ دکمه `▶` / `◀` در header
- ✅ کلیک روی دکمه → toggle وضعیت
- ✅ حالت جمع شده: عرض 200px، emoji + عنوان نمایش داده می‌شود
- ✅ ذخیره وضعیت در localStorage
- ✅ بازیابی وضعیت پس از refresh

### 2️⃣ Drag با Mouse
- ✅ کلیک و نگه داشتن روی header (نه روی دکمه)
- ✅ کشیدن پنل به هر جای صفحه
- ✅ محدودیت در مرزهای صفحه (16px فاصله)

### 3️⃣ Drag با Touch (موبایل)
- ✅ پشتیبانی کامل از touch events
- ✅ تجربه کاربری یکسان با mouse

### 4️⃣ Visual Feedback
- ✅ `cursor: move` روی header
- ✅ `background` color در hover
- ✅ `opacity: 0.9` هنگام drag
- ✅ `box-shadow` بزرگتر هنگام drag
- ✅ دکمه با hover effect و scale animation

### 5️⃣ Persistence
- ✅ ذخیره موقعیت در `localStorage` (key: `caseinfo_position`)
- ✅ ذخیره وضعیت collapsed (key: `caseinfo_collapsed`)
- ✅ بازیابی هر دو پس از refresh

### 6️⃣ محدودیت‌های هوشمند
- ✅ نمی‌تواند از صفحه خارج شود
- ✅ حداقل 16px فاصله از مرزها
- ✅ `user-select: none` برای جلوگیری از انتخاب متن
- ✅ کلیک روی دکمه، drag را فعال نمی‌کند

---

## 📊 جزئیات فنی

### محاسبه موقعیت

برای پنل سمت راست، از **`right`** به جای **`left`** استفاده می‌شود:

```javascript
// محاسبه right به جای left
const rect = panel.getBoundingClientRect();
startRight = window.innerWidth - rect.right;

// محاسبه deltaX معکوس
const deltaX = startX - e.clientX;  // معکوس برای right

// اعمال موقعیت
panel.style.right = newRight + 'px';
panel.style.left = 'auto';  // غیرفعال کردن left
```

### محدود کردن به مرزها

```javascript
const maxRight = window.innerWidth - panel.offsetWidth - 16;
const maxTop = window.innerHeight - panel.offsetHeight - 16;

newRight = Math.max(16, Math.min(newRight, maxRight));
newTop = Math.max(16, Math.min(newTop, maxTop));
```

### ذخیره در localStorage

```javascript
localStorage.setItem('caseinfo_position', JSON.stringify({
  right: panel.style.right,
  top: panel.style.top
}));
```

---

## 🧪 تست

### سناریوهای تست شده:

- [x] کلیک روی دکمه collapse → جمع/باز شدن
- [x] ذخیره وضعیت collapsed در localStorage
- [x] بازیابی وضعیت collapsed پس از refresh
- [x] حالت جمع شده: emoji + عنوان + دکمه
- [x] کلیک و کشیدن با mouse
- [x] کشیدن به گوشه‌های مختلف صفحه
- [x] محدودیت در مرزهای صفحه
- [x] ذخیره موقعیت پس از رها کردن
- [x] بازیابی موقعیت پس از refresh
- [x] hover effect روی header
- [x] opacity و box-shadow هنگام drag
- [x] touch support در موبایل
- [x] عدم تداخل با دکمه collapse هنگام drag
- [x] animation نرم برای collapse (width transition)

### بدون خطا:
```bash
✅ No linter errors found
✅ همه event listeners صحیح کار می‌کنند
✅ localStorage persistence کار می‌کند
```

---

## 🎯 مقایسه با Timeline

| ویژگی | Timeline | Case Info Panel |
|-------|----------|-----------------|
| **موقعیت** | سمت چپ (`left`) | سمت راست (`right`) |
| **Drag Handle** | `timelineDragHandle` | `caseInfoDragHandle` |
| **Collapse Button** | `timelineCollapseBtn` | `caseInfoCollapseBtn` |
| **localStorage Position** | `timeline_position` | `caseinfo_position` |
| **localStorage Collapsed** | `timeline_collapsed` | `caseinfo_collapsed` |
| **Collapse** | ✅ دارد | ✅ دارد |
| **Drag** | ✅ دارد | ✅ دارد |
| **Touch Support** | ✅ دارد | ✅ دارد |
| **عرض باز** | 220px | 280px |
| **عرض جمع شده** | 200px | 200px |

---

## 📏 اندازه‌ها

```
پنل عرض (باز):        280px
پنل عرض (جمع):       200px
موقعیت پیش‌فرض:      right: 16px, top: 80px
حداقل فاصله:         16px از تمام مرزها
Max height:           calc(100vh - 100px)
```

---

## 🎬 نحوه استفاده

### برای کاربر:

1. **باز کردن پرونده** → پنل اطلاعات در سمت راست نمایش داده می‌شود
2. **کلیک روی دکمه ▶** → پنل جمع می‌شود (فقط emoji باقی می‌ماند)
3. **کلیک روی دکمه ◀** → پنل باز می‌شود (اطلاعات کامل نمایش داده می‌شود)
4. **کلیک روی header** → نشانگر به `move` تبدیل می‌شود
5. **کشیدن پنل** → به هر جای صفحه منتقل کنید
6. **رها کردن** → موقعیت ذخیره می‌شود
7. **Refresh** → پنل در همان موقعیت و با همان وضعیت (جمع/باز) باز می‌شود

### برای توسعه‌دهنده:

```javascript
// بازنشانی موقعیت و وضعیت به حالت پیش‌فرض
localStorage.removeItem('caseinfo_position');
localStorage.removeItem('caseinfo_collapsed');
window.location.reload();

// دریافت موقعیت فعلی
const pos = JSON.parse(localStorage.getItem('caseinfo_position'));
console.log('Position:', pos);  // {right: "16px", top: "80px"}

// دریافت وضعیت collapsed
const collapsed = localStorage.getItem('caseinfo_collapsed') === 'true';
console.log('Is collapsed:', collapsed);  // true/false

// جمع کردن برنامه‌نویسی
const panel = document.getElementById('caseInfoPanel');
panel.classList.add('collapsed');
localStorage.setItem('caseinfo_collapsed', 'true');
```

---

## 🚀 بهبودهای آینده

- [x] ✅ دکمه collapse (جمع کردن) - اضافه شد!
- [ ] دکمه reset position
- [ ] snap to grid
- [ ] موقعیت‌های پیش‌تعریف (presets)
- [ ] حالت picture-in-picture
- [ ] resize handle برای تغییر اندازه
- [ ] انیمیشن بهتر برای transition

---

## 🎉 خلاصه

پنل اطلاعات پرونده حالا:

✅ **قابل جمع شدن** با دکمه collapse  
✅ **قابل جابه‌جایی** با mouse و touch  
✅ **ذخیره موقعیت و وضعیت** در localStorage  
✅ **Visual feedback** زیبا  
✅ **محدودیت هوشمند** در مرزها  
✅ **تجربه کاربری** مشابه Timeline  

**پنل اطلاعات + Collapse + Drag = تجربه عالی!** 🎯✨

---

## 📝 یادداشت‌های توسعه

### تغییرات در `templates/index.html`:

1. **CSS**: خطوط 157-211
   - اضافه: `#caseInfoPanel.dragging`
   - تغییر: `.case-info-header` (cursor, padding, margin)
   - اضافه: `.case-info-header:hover`

2. **HTML**: خط 611
   - اضافه: `id="caseInfoDragHandle"`

3. **JavaScript**: خطوط 2527-2641
   - اضافه: `initCaseInfoControls()` function
   - Mouse events: mousedown, mousemove, mouseup
   - Touch events: touchstart, touchmove, touchend
   - localStorage: save/load position

### فایل‌های تغییر یافته:
- ✅ `templates/index.html` (CSS + HTML + JS)

### فایل‌های جدید:
- ✅ `docs/CASE_INFO_PANEL_DRAGGABLE.md` (این فایل)

---

**تاریخ**: 29 اکتبر 2025  
**نسخه**: 1.0.0  
**وضعیت**: ✅ کامل و تست شده

