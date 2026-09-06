---
name: mento-edit-frontend-ui
description: >-
  Use when the user wants to modify the Mento.AI frontend: changing the
  appearance, adding UI components, editing the stage flow (upload / processing
  / preview / download), adjusting the CSS design system, or modifying the
  accordion/results display. Covers the Neural Indigo design system rules and
  the 4-stage SPA architecture.
---

# Edit the Mento.AI Frontend UI

## File Map

| File | Role |
|---|---|
| [`frontend/index.html`](file:///D:/Mento.AI/frontend/index.html) | HTML structure — all 4 stages, navbar, hero, sections |
| [`frontend/css/style.css`](file:///D:/Mento.AI/frontend/css/style.css) | All styles — Neural Indigo design system |
| [`frontend/js/app.js`](file:///D:/Mento.AI/frontend/js/app.js) | All JS — upload, SSE, preview accordion, export |

> **No build step** — changes take effect immediately on browser refresh. No bundler, no npm.

## 4-Stage SPA Architecture

```
#upload-stage     → class="stage-section active"  (visible)
#processing-stage → class="stage-section"          (hidden)
#preview-stage    → class="stage-section"          (hidden)
#download-stage   → class="stage-section"          (hidden)
```

`showStage(element)` in `app.js` removes `active` from all 4 and adds it to the target.

## CSS Design System Rules

### Always use CSS variables — never hardcode colors
```css
/* ✅ Correct */
color: var(--indigo);
background: var(--surface);

/* ❌ Wrong */
color: #6366f1;
background: rgba(13,16,40,0.6);
```

### Adding a new card/section
```css
.my-new-card {
    background: var(--surface);
    backdrop-filter: var(--blur);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    transition: all 0.35s;
}
.my-new-card:hover {
    border-color: var(--border-a);
    transform: translateY(-4px);
    box-shadow: 0 16px 40px rgba(99,102,241,0.15);
    background: var(--surface-h);
}
```

### Gradient text
```css
.my-gradient-text {
    background: linear-gradient(135deg, var(--indigo), var(--violet));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
```

### Fade-in-up on scroll (add to any element)
```html
<div class="fade-in-up">Content here</div>
```
The IntersectionObserver in the inline `<script>` adds `.visible` class when it scrolls into view.

## Adding a New Stage or Panel

1. Add the HTML div in `#app .app-card`:
   ```html
   <div id="my-stage" class="stage-section">
     <!-- content -->
   </div>
   ```
2. Add a DOM reference in `app.js`:
   ```js
   const myStage = document.getElementById("my-stage");
   ```
3. Add to the stage list in `showStage()`:
   ```js
   function showStage(stageElement) {
       [uploadStage, processingStage, previewStage, downloadStage, myStage]
           .forEach(s => s.classList.remove("active"));
       stageElement.classList.add("active");
   }
   ```

## Accordion (Preview Stage)

The results accordion in `#results-accordion` is **dynamically built by `app.js`** `renderResultsPreview()`. Do not add static accordion HTML in `index.html`.

CSS classes used by the accordion:
- `.accordion-item`, `.accordion-item.open`
- `.accordion-header`, `.accordion-title-block`, `.accordion-num`, `.accordion-title`
- `.accordion-meta-block`, `.match-count-badge`, `.chevron-icon`
- `.accordion-body` (max-height transitions on `.open`)
- `.match-card`, `.match-top`, `.match-check-label`, `.confidence-pill`, `.match-snippet`

## Adding a New Section to the Landing Page

```html
<!-- In index.html, after #features section -->
<section id="my-section" class="my-section-class">
  <div class="section-label">MY SECTION</div>
  <h2 class="section-h2">Section Heading</h2>
  <!-- content -->
</section>
```

Add nav link:
```html
<a href="#my-section">My Section</a>
```
