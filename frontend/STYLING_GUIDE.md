# Frontend Styling Guide

## Overview

The Adaptive IDS frontend uses a modern, scalable CSS architecture with custom properties (CSS variables), utility classes, and a comprehensive design system. Styles are production-ready with dark mode support, accessibility features, and responsive layouts.

## Architecture

### File Structure

```
frontend/
├── index.css              # Main entry point, global resets, and component styles
└── styles/
    ├── variables.css      # Design tokens (colors, spacing, typography, shadows)
    ├── utilities.css      # Reusable utility classes
    └── pages.css          # Page-specific styles (Analytics, Reports, etc.)
```

### Import Order

All styles are imported in `index.css` in this order:

1. `variables.css` - CSS custom properties for theming
2. `utilities.css` - Helper classes
3. `pages.css` - Page-specific styles
4. Global resets and base styles
5. Component-specific styles

## Design System

### CSS Variables

Located in `styles/variables.css`, organized by category:

#### Colors

```css
/* Primary/Accent */
--accent-color: #28a745;
--accent-color-hover: #218838;

/* Backgrounds (theme-aware) */
--bg-primary: #ffffff;    /* Light mode */
--bg-secondary: #f8f9fa;
--bg-card: #ffffff;

/* Text (theme-aware) */
--text-primary: #343a40;
--text-secondary: #6c757d;

/* Semantic colors */
--color-success: #28a745;
--color-warning: #ffc107;
--color-danger: #dc3545;
--color-info: #0d6efd;
```

#### Spacing Scale

Consistent spacing using an 8px base unit:

```css
--space-1: 4px;   /* 0.25rem */
--space-2: 8px;   /* 0.5rem */
--space-3: 12px;  /* 0.75rem */
--space-4: 16px;  /* 1rem */
--space-6: 24px;  /* 1.5rem */
--space-8: 32px;  /* 2rem */
```

#### Typography

```css
--font-family-base: 'Lato', sans-serif;
--font-family-mono: 'Courier New', monospace;

--font-size-xs: 0.75rem;   /* 12px */
--font-size-sm: 0.875rem;  /* 14px */
--font-size-base: 1rem;    /* 16px */
--font-size-lg: 1.125rem;  /* 18px */
--font-size-xl: 1.25rem;   /* 20px */
--font-size-2xl: 1.5rem;   /* 24px */
```

#### Shadows

```css
--shadow-sm: 0 1px 3px rgba(0,0,0,0.1);
--shadow-md: 0 4px 6px rgba(0,0,0,0.1);
--shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
```

## Dark Mode

Dark mode is supported via `data-theme="dark"` attribute on the root element:

```html
<html data-theme="dark">
```

Variables automatically update:

```css
[data-theme="dark"] {
  --bg-primary: #212529;
  --bg-secondary: #343a40;
  --text-primary: #e9ecef;
  --text-secondary: #ced4da;
}
```

## Utility Classes

Located in `styles/utilities.css`. Use these for rapid prototyping and consistent styling:

### Layout

```css
.flex { display: flex; }
.flex-column { flex-direction: column; }
.justify-center { justify-content: center; }
.items-center { align-items: center; }
.gap-4 { gap: var(--space-4); }
```

### Container

```css
.container { max-width: 1400px; margin: 0 auto; padding: 0 1rem; }
.container-sm { max-width: 768px; }
.container-md { max-width: 1024px; }
```

### Spacing

```css
.mt-4 { margin-top: var(--space-4); }
.mb-4 { margin-bottom: var(--space-4); }
.p-4 { padding: var(--space-4); }
.px-4 { padding-left: var(--space-4); padding-right: var(--space-4); }
```

### Typography

```css
.text-sm { font-size: var(--font-size-sm); }
.text-lg { font-size: var(--font-size-lg); }
.font-bold { font-weight: 700; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.line-clamp-2 { /* Truncate at 2 lines */ }
```

### Colors

```css
.text-primary { color: var(--text-primary); }
.text-success { color: var(--color-success); }
.bg-primary { background-color: var(--bg-primary); }
```

### Borders & Shadows

```css
.rounded { border-radius: var(--radius-base); }
.rounded-lg { border-radius: var(--radius-lg); }
.shadow-sm { box-shadow: var(--shadow-sm); }
```

## Accessibility Features

### Focus States

Global focus-visible outlines for keyboard navigation:

```css
*:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}
```

### Skip to Content

Screen reader and keyboard-accessible skip link:

```html
<a href="#main-content" class="skip-to-content">Skip to content</a>
```

### Reduced Motion

Respects user's motion preferences:

```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Custom Scrollbars

Themed scrollbars with dark mode support:

```css
*::-webkit-scrollbar {
  width: 10px;
}
*::-webkit-scrollbar-thumb {
  background-color: var(--border-color);
  border-radius: 9999px;
}
```

## Print Styles

Optimized for printing reports and analytics (in `styles/pages.css`):

```css
@media print {
  .header, .btn, .pagination-controls {
    display: none !important;
  }
  .card {
    box-shadow: none !important;
    border: 1px solid #ddd !important;
  }
}
```

## Component Patterns

### Cards

```html
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Title</h3>
  </div>
  <div class="card-body">
    Content
  </div>
</div>
```

### Buttons

```html
<button class="btn btn-primary">
  <span class="material-symbols-outlined">add</span>
  Add Item
</button>
```

### Status Badges

```html
<span class="status-badge status-new">New</span>
<span class="severity-badge severity-critical">Critical</span>
```

## Best Practices

1. **Use CSS Variables** - Always reference design tokens instead of hardcoded values
   ```css
   /* ❌ Don't */
   color: #28a745;
   
   /* ✅ Do */
   color: var(--accent-color);
   ```

2. **Leverage Utilities** - For one-off spacing/layout instead of custom CSS
   ```html
   <!-- ❌ Don't -->
   <div style="margin-top: 16px; display: flex;">
   
   <!-- ✅ Do -->
   <div class="mt-4 flex">
   ```

3. **Maintain Specificity** - Keep selectors flat and avoid deep nesting
   ```css
   /* ❌ Don't */
   .card .header .title h3 { }
   
   /* ✅ Do */
   .card-title { }
   ```

4. **Mobile-First** - Write base styles for mobile, then enhance for larger screens
   ```css
   .grid { grid-template-columns: 1fr; }
   
   @media (min-width: 768px) {
     .grid { grid-template-columns: repeat(2, 1fr); }
   }
   ```

## Development Workflow

### Local Development

1. Edit CSS files in `frontend/styles/` or `frontend/index.css`
2. Build the frontend:
   ```powershell
   cd frontend
   npm run build
   ```
3. Refresh browser at http://localhost:8080 to see changes

### Docker Production

The Docker setup uses `docker-compose.override.yml` to mount the built `dist/` folder:

```yaml
services:
  frontend:
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
```

Changes take effect after rebuilding:

```powershell
cd frontend
npm run build
# Refresh browser - no Docker rebuild needed!
```

### Full Rebuild (Optional)

To bake changes into the Docker image:

```powershell
docker compose build frontend
docker compose up -d frontend
```

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Modern mobile browsers

CSS features used:
- CSS Grid & Flexbox
- Custom Properties (CSS Variables)
- `color-scheme` for dark mode
- `:focus-visible` for accessibility
- Modern selectors (`:is()`, `:where()`)

## Troubleshooting

### Styles not updating in Docker

1. Rebuild the frontend: `npm run build` in `frontend/`
2. Refresh browser with hard reload (Ctrl+Shift+R)

### Dark mode not switching

Check that the root element has `data-theme` attribute:

```javascript
document.documentElement.setAttribute('data-theme', 'dark');
```

### Custom scrollbars not showing

Ensure browser supports `::-webkit-scrollbar` (Chrome, Edge, Safari). Firefox uses different syntax.

## Resources

- [MDN CSS Custom Properties](https://developer.mozilla.org/en-US/docs/Web/CSS/--*)
- [CSS Tricks - Complete Guide to Flexbox](https://css-tricks.com/snippets/css/a-guide-to-flexbox/)
- [Web.dev - Dark Mode](https://web.dev/prefers-color-scheme/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
