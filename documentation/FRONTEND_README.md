# Adaptive IDS Frontend

Modern, accessible dashboard for the Adaptive IDS system built with Vite + TypeScript.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type check
npm run type-check
```

## 📚 Documentation

- **[Component Quick Start Guide](./COMPONENT_QUICK_START.md)** - Learn how to use the new UI components
- **[Implementation Summary](../documentation/FRONTEND_IMPLEMENTATION_SUMMARY.md)** - Detailed project documentation
- **[Executive Summary](../documentation/FRONTEND_EXECUTIVE_SUMMARY.md)** - High-level overview and progress

## 🎨 Design System

The frontend now includes a comprehensive design system with:

- **80+ CSS Variables** for consistent theming
- **150+ Utility Classes** for rapid development
- **Dark Mode Support** with one-line toggle
- **Responsive Design** patterns for mobile/tablet/desktop
- **Accessibility** features (WCAG 2.1 AA compliant)

### Using CSS Variables

```css
.my-component {
    background-color: var(--bg-card);
    color: var(--text-primary);
    padding: var(--space-6); /* 24px */
    border-radius: var(--radius-lg); /* 12px */
    box-shadow: var(--shadow-md);
}
```

### Using Utility Classes

```typescript
element.className = 'flex items-center justify-between gap-4 p-6 rounded-lg shadow-md';
```

## 🧩 Components

### Available Components (3/12)

1. **Button** - 7 variants, 3 sizes, with icons and loading states
2. **Toast** - Notification system with 4 types and auto-dismiss
3. **Modal** - Dialog system with 5 sizes and confirm helpers

### Usage Example

```typescript
import { createButton } from './components/Button';
import { toast } from './components/Toast';
import { Modal } from './components/Modal';

// Button
const button = createButton({
    variant: 'primary',
    icon: 'check_circle',
    children: 'Save Changes',
    onClick: handleSave
});

// Toast
toast.success('Changes saved successfully');
toast.error('Failed to connect to server');

// Modal
const modal = new Modal({
    title: 'Confirm Action',
    content: '<p>Are you sure?</p>',
    size: 'sm'
});
modal.open();
```

## 🌓 Dark Mode

Toggle dark mode programmatically:

```typescript
// Enable dark mode
document.documentElement.setAttribute('data-theme', 'dark');
localStorage.setItem('theme', 'dark');

// Disable dark mode
document.documentElement.removeAttribute('data-theme');
localStorage.setItem('theme', 'light');
```

## 📱 Responsive Design

The design system uses a mobile-first approach with these breakpoints:

- **Mobile**: < 640px
- **Tablet**: 768px - 1023px
- **Desktop**: 1024px - 1279px
- **Large Desktop**: 1280px - 1535px
- **XL Desktop**: ≥ 1536px

## ♿ Accessibility

All components include:

- ARIA labels and roles
- Keyboard navigation (Tab, Enter, ESC)
- Focus indicators
- Screen reader support
- Color contrast compliance (WCAG 2.1 AA)

## 🏗️ Project Structure

```
frontend/
├── api.ts                      # API service layer
├── data.ts                     # Mock data and constants
├── index.css                   # Main stylesheet (imports variables & utilities)
├── index.html                  # HTML entry point
├── index.tsx                   # TypeScript entry point
├── types.ts                    # TypeScript type definitions
├── vite.config.ts              # Vite configuration
├── components/                 # Reusable UI components
│   ├── Button.ts              # Button component ✅
│   ├── Chart.ts               # Chart.js wrapper
│   ├── ConnectionStatus.ts    # Real-time connection indicator
│   ├── Header.ts              # Application header
│   ├── Modal.ts               # Modal dialog ✅
│   ├── Pagination.ts          # Pagination controls
│   └── Toast.ts               # Toast notifications ✅
├── hooks/                      # Custom React hooks
│   └── useApi.ts
├── pages/                      # Page components
│   ├── AlertsPage.ts
│   ├── Dashboard.ts
│   ├── IncidentsPage.ts
│   ├── LoginPage.ts
│   ├── PlaceholderPage.ts
│   └── RLModelPage.ts
├── providers/                  # Context providers
│   └── QueryProvider.tsx
├── services/                   # Business logic services
│   └── authService.ts
├── styles/                     # Design system
│   ├── variables.css          # CSS variables (design tokens) ✅
│   └── utilities.css          # Utility classes ✅
└── utils/                      # Utility functions
    ├── apiClient.ts
    ├── csvExport.ts
    └── realtimeClient.ts
```

## 🔧 Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_BASE_URL=http://localhost:5000
VITE_SSE_URL=http://localhost:5000/events
```

## 🧪 Testing

```bash
# Run unit tests (when implemented)
npm test

# Run E2E tests (when implemented)
npm run test:e2e
```

## 🚢 Deployment

```bash
# Build for production
npm run build

# Output will be in ./dist directory
# Serve with any static file server
```

## 📊 Performance Targets

- **Lighthouse Performance**: ≥ 90
- **First Contentful Paint**: < 1.5s
- **Time to Interactive**: < 3.5s
- **Bundle Size**: < 500KB gzipped
- **Accessibility Score**: ≥ 95

## 🤝 Contributing

1. Follow the component pattern in existing components
2. Use TypeScript with strict types (no `any`)
3. Add ARIA labels for accessibility
4. Test on mobile, tablet, and desktop
5. Document your component in the Quick Start Guide
6. Run type-check before committing: `npm run type-check`

## 📖 Additional Resources

- [Vite Documentation](https://vitejs.dev/)
- [TypeScript Documentation](https://www.typescriptlang.org/)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Material Symbols Icons](https://fonts.google.com/icons)

## 📝 License

MIT License

---

**Last Updated**: October 24, 2025  
**Version**: 2.0.0  
**Status**: Phase 1 Complete ✅ (25% of total scope)
