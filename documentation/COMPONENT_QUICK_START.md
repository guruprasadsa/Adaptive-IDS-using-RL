# Frontend UI Components - Quick Start Guide

## Overview
This guide will help you integrate the new design system and UI components into the Adaptive IDS frontend.

---

## Prerequisites
- Node.js 18+ installed
- Familiarity with TypeScript
- Basic understanding of the existing codebase

---

## Step 1: Update Your CSS Imports

The new design system is split into modular CSS files. Update `frontend/index.css`:

```css
/* At the top of index.css */
@import './styles/variables.css';
@import './styles/utilities.css';
```

**Note**: The existing `index.css` has been updated with these imports. No action needed if using the latest version.

---

## Step 2: Using the Design System

### CSS Variables
Access design tokens anywhere in your CSS:

```css
.my-component {
    /* Colors */
    background-color: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    
    /* Spacing */
    padding: var(--space-4); /* 16px */
    margin-bottom: var(--space-6); /* 24px */
    gap: var(--space-2); /* 8px */
    
    /* Typography */
    font-size: var(--font-size-base); /* 16px */
    font-weight: var(--font-weight-semibold); /* 600 */
    line-height: var(--line-height-normal); /* 1.5 */
    
    /* Border Radius */
    border-radius: var(--radius-lg); /* 12px */
    
    /* Shadows */
    box-shadow: var(--shadow-md);
    
    /* Transitions */
    transition: all var(--transition-base); /* 200ms */
}
```

### Utility Classes
Apply pre-built styles directly in HTML:

```typescript
const element = document.createElement('div');
element.className = 'flex items-center justify-between gap-4 p-4 rounded-lg shadow-md';
```

**Common Patterns:**
```html
<!-- Flexbox layout -->
<div class="flex items-center gap-4">
    <span>Item 1</span>
    <span>Item 2</span>
</div>

<!-- Centered content -->
<div class="flex justify-center items-center h-full">
    <h1 class="text-2xl font-bold">Centered Text</h1>
</div>

<!-- Card with shadow -->
<div class="bg-card rounded-lg shadow-md p-6">
    <h2 class="text-lg font-semibold mb-4">Card Title</h2>
    <p class="text-secondary">Card content goes here</p>
</div>

<!-- Responsive spacing -->
<div class="mt-4 mb-8 px-6">Content</div>
```

---

## Step 3: Using Components

### Button Component

**Import:**
```typescript
import { createButton, ButtonProps } from './components/Button';
```

**Basic Usage:**
```typescript
// Simple button
const button = createButton({
    variant: 'primary',
    size: 'md',
    children: 'Click Me'
});

// Button with icon
const iconButton = createButton({
    variant: 'secondary',
    size: 'sm',
    icon: 'refresh',
    iconPosition: 'left',
    children: 'Refresh',
    onClick: () => console.log('Refreshing...')
});

// Loading button
const loadingButton = createButton({
    variant: 'primary',
    loading: true,
    children: 'Saving...',
    disabled: true
});

// Append to DOM
document.getElementById('container')!.appendChild(button);
```

**All Props:**
```typescript
interface ButtonProps {
    variant?: 'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'ghost' | 'link';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    loading?: boolean;
    icon?: string; // Material Symbols icon name
    iconPosition?: 'left' | 'right';
    fullWidth?: boolean;
    type?: 'button' | 'submit' | 'reset';
    ariaLabel?: string;
    onClick?: (e: MouseEvent) => void;
    children: string | HTMLElement[];
}
```

**Real-World Examples:**
```typescript
// Alert acknowledge button
const ackButton = createButton({
    variant: 'success',
    size: 'sm',
    icon: 'check_circle',
    children: 'Acknowledge',
    ariaLabel: `Acknowledge alert ${alertId}`,
    onClick: () => acknowledgeAlert(alertId)
});

// Delete button (danger)
const deleteButton = createButton({
    variant: 'danger',
    icon: 'delete',
    children: 'Delete',
    onClick: () => showDeleteConfirmation()
});

// Submit button in form
const submitButton = createButton({
    type: 'submit',
    variant: 'primary',
    fullWidth: true,
    loading: isSubmitting,
    children: isSubmitting ? 'Submitting...' : 'Submit'
});
```

---

### Toast Notifications

**Import:**
```typescript
import { toast } from './components/Toast';
```

**Basic Usage:**
```typescript
// Success notification
toast.success('Alert acknowledged successfully');

// Error notification (stays longer)
toast.error('Failed to connect to server');

// Warning
toast.warning('This action cannot be undone');

// Info
toast.info('Processing your request...');
```

**Advanced Usage:**
```typescript
// Custom duration and position
const toastId = toast.show({
    message: 'Custom notification',
    type: 'info',
    duration: 10000, // 10 seconds
    position: 'bottom-right',
    dismissible: true
});

// Manually dismiss a toast
toast.dismiss(toastId);

// Dismiss all toasts
toast.dismissAll();

// No auto-dismiss (manual only)
toast.show({
    message: 'Important: Read this carefully',
    type: 'warning',
    duration: 0, // Won't auto-dismiss
    dismissible: true
});
```

**Integration with API Calls:**
```typescript
async function acknowledgeAlert(alertId: string) {
    try {
        await apiService.acknowledgeAlert(alertId);
        toast.success('Alert acknowledged successfully');
        refreshAlerts();
    } catch (error) {
        toast.error(`Failed to acknowledge alert: ${error.message}`);
    }
}

async function saveSettings(data: Settings) {
    const toastId = toast.show({
        message: 'Saving settings...',
        type: 'info',
        duration: 0
    });
    
    try {
        await apiService.updateSettings(data);
        toast.dismiss(toastId);
        toast.success('Settings saved successfully');
    } catch (error) {
        toast.dismiss(toastId);
        toast.error('Failed to save settings');
    }
}
```

---

### Modal Dialog

**Import:**
```typescript
import { Modal, showConfirmDialog } from './components/Modal';
```

**Basic Modal:**
```typescript
const modal = new Modal({
    title: 'Alert Details',
    content: '<h3>Alert Information</h3><p>Details go here...</p>',
    size: 'md'
});

modal.open();

// Close programmatically
setTimeout(() => modal.close(), 5000);
```

**Modal with Custom Content:**
```typescript
// Create custom content
const content = document.createElement('div');
content.innerHTML = `
    <div class="alert-details">
        <p><strong>Source IP:</strong> ${alert.srcIp}</p>
        <p><strong>Destination IP:</strong> ${alert.dstIp}</p>
        <p><strong>Confidence:</strong> ${(alert.confidence * 100).toFixed(1)}%</p>
        <p><strong>Description:</strong> ${alert.description}</p>
    </div>
`;

const modal = new Modal({
    title: `Alert ${alert.id}`,
    content,
    size: 'lg',
    onClose: () => console.log('Modal closed')
});

modal.open();
```

**Modal with Footer:**
```typescript
// Create footer with buttons
const footer = document.createElement('div');
footer.style.cssText = 'display: flex; gap: 12px; justify-content: flex-end;';

const cancelBtn = createButton({ variant: 'secondary', children: 'Cancel' });
const saveBtn = createButton({ variant: 'primary', children: 'Save Changes' });

footer.appendChild(cancelBtn);
footer.appendChild(saveBtn);

const modal = new Modal({
    title: 'Edit Alert',
    content: '<form>...</form>',
    footer,
    size: 'md'
});

cancelBtn.addEventListener('click', () => modal.close());
saveBtn.addEventListener('click', () => {
    saveChanges();
    modal.close();
});

modal.open();
```

**Confirm Dialog:**
```typescript
// Simple confirmation
showConfirmDialog({
    title: 'Delete Alert',
    message: 'Are you sure you want to delete this alert? This action cannot be undone.',
    confirmText: 'Delete',
    cancelText: 'Cancel',
    danger: true, // Makes confirm button red
    onConfirm: () => {
        deleteAlert(alertId);
        toast.success('Alert deleted');
    },
    onCancel: () => {
        console.log('Deletion cancelled');
    }
});

// Acknowledge confirmation
showConfirmDialog({
    title: 'Acknowledge Alert',
    message: 'Mark this alert as acknowledged?',
    confirmText: 'Acknowledge',
    onConfirm: async () => {
        try {
            await apiService.acknowledgeAlert(alertId);
            toast.success('Alert acknowledged');
        } catch (error) {
            toast.error('Failed to acknowledge alert');
        }
    }
});
```

**Modal Options:**
```typescript
interface ModalOptions {
    title?: string;
    content: string | HTMLElement;
    footer?: HTMLElement;
    size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
    closeOnOverlayClick?: boolean; // default: true
    closeOnEscape?: boolean;       // default: true
    showCloseButton?: boolean;     // default: true
    onOpen?: () => void;
    onClose?: () => void;
}
```

---

## Step 4: Dark Mode Support

The design system includes full dark mode support via CSS variables.

### Toggle Dark Mode:
```typescript
// Enable dark mode
function enableDarkMode() {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem('theme', 'dark');
}

// Disable dark mode (back to light)
function disableDarkMode() {
    document.documentElement.removeAttribute('data-theme');
    localStorage.setItem('theme', 'light');
}

// Toggle between light and dark
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    if (currentTheme === 'dark') {
        disableDarkMode();
    } else {
        enableDarkMode();
    }
}

// Initialize theme from localStorage
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
}

// Call on page load
document.addEventListener('DOMContentLoaded', initTheme);
```

### Dark Mode Toggle Button:
```typescript
const themeToggle = createButton({
    variant: 'ghost',
    icon: 'dark_mode',
    ariaLabel: 'Toggle dark mode',
    onClick: toggleTheme
});

// Update icon based on current theme
function updateThemeIcon() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const icon = themeToggle.querySelector('.material-symbols-outlined');
    if (icon) {
        icon.textContent = isDark ? 'light_mode' : 'dark_mode';
    }
}
```

---

## Step 5: Responsive Design

Use utility classes and media queries for responsive layouts.

### Utility Classes for Responsiveness:
```typescript
// Hide on mobile, show on desktop
element.className = 'hidden md:block';

// Stack on mobile, row on desktop
container.className = 'flex flex-column md:flex-row gap-4';

// Full width on mobile, auto on desktop
button.className = 'w-full md:w-auto';
```

### Custom Media Queries:
```css
/* Mobile-first approach */
.my-component {
    padding: var(--space-2);
}

@media (min-width: 768px) {
    .my-component {
        padding: var(--space-6);
    }
}

@media (min-width: 1024px) {
    .my-component {
        padding: var(--space-8);
    }
}
```

### Responsive Grid:
```typescript
const grid = document.createElement('div');
grid.className = 'grid gap-4';
grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(280px, 1fr))';

// Cards automatically wrap and resize
cards.forEach(card => grid.appendChild(card));
```

---

## Step 6: Accessibility Best Practices

### ARIA Labels:
```typescript
// Buttons
const button = createButton({
    icon: 'delete',
    ariaLabel: 'Delete alert 123',
    children: ''
});

// Inputs
input.setAttribute('aria-label', 'Search alerts');
input.setAttribute('aria-describedby', 'search-help');

// Live regions (for toast)
container.setAttribute('aria-live', 'polite');
container.setAttribute('aria-atomic', 'true');
```

### Keyboard Navigation:
```typescript
// Handle Enter key
element.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onClick();
    }
});

// Escape to close
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
});
```

### Focus Management:
```typescript
// Focus first focusable element in modal
const focusableElements = modal.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
);
if (focusableElements.length > 0) {
    (focusableElements[0] as HTMLElement).focus();
}

// Focus ring utility class
element.classList.add('focus-ring');
```

---

## Step 7: Integration Example (Alerts Page)

Here's a complete example of integrating the new components into the Alerts page:

```typescript
import { createButton } from './components/Button';
import { toast } from './components/Toast';
import { showConfirmDialog } from './components/Modal';

function renderAlertsPage(alerts: Alert[]) {
    const container = document.createElement('div');
    container.className = 'p-6';

    // Header with actions
    const header = document.createElement('div');
    header.className = 'flex items-center justify-between mb-6';

    const title = document.createElement('h1');
    title.className = 'text-2xl font-bold';
    title.textContent = 'Alerts';

    const actions = document.createElement('div');
    actions.className = 'flex gap-2';

    const refreshBtn = createButton({
        variant: 'secondary',
        icon: 'refresh',
        children: 'Refresh',
        onClick: handleRefresh
    });

    const exportBtn = createButton({
        variant: 'secondary',
        icon: 'download',
        children: 'Export CSV',
        onClick: handleExport
    });

    actions.appendChild(refreshBtn);
    actions.appendChild(exportBtn);
    header.appendChild(title);
    header.appendChild(actions);
    container.appendChild(header);

    // Alerts table
    const table = renderAlertsTable(alerts);
    container.appendChild(table);

    return container;
}

function handleAcknowledge(alertId: string) {
    showConfirmDialog({
        title: 'Acknowledge Alert',
        message: 'Mark this alert as acknowledged and resolved?',
        confirmText: 'Acknowledge',
        onConfirm: async () => {
            try {
                await apiService.acknowledgeAlert(alertId);
                toast.success('Alert acknowledged successfully');
                refreshAlerts();
            } catch (error) {
                toast.error('Failed to acknowledge alert');
            }
        }
    });
}

function handleExport() {
    const exportToastId = toast.show({
        message: 'Exporting alerts...',
        type: 'info',
        duration: 0
    });

    try {
        exportAlertsToCSV(alerts);
        toast.dismiss(exportToastId);
        toast.success('Alerts exported successfully');
    } catch (error) {
        toast.dismiss(exportToastId);
        toast.error('Failed to export alerts');
    }
}

async function handleRefresh() {
    const refreshBtn = document.querySelector('[data-action="refresh"]') as HTMLButtonElement;
    if (refreshBtn) {
        refreshBtn.disabled = true;
        // Update button to show loading state
    }

    try {
        await loadAlerts();
        toast.success('Alerts refreshed');
    } catch (error) {
        toast.error('Failed to refresh alerts');
    } finally {
        if (refreshBtn) refreshBtn.disabled = false;
    }
}
```

---

## Common Patterns

### Loading State:
```typescript
function handleSubmit() {
    const submitBtn = createButton({
        variant: 'primary',
        loading: true,
        disabled: true,
        children: 'Submitting...'
    });
    
    // Replace existing button
    oldButton.replaceWith(submitBtn);
    
    // After completion
    submitBtn.loading = false;
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit';
}
```

### Form Validation:
```typescript
function validateForm() {
    const errors: string[] = [];
    
    if (!email.value) {
        errors.push('Email is required');
        email.classList.add('border-danger');
        email.setAttribute('aria-invalid', 'true');
    }
    
    if (errors.length > 0) {
        toast.error(errors.join(', '));
        return false;
    }
    
    return true;
}
```

### Empty States:
```typescript
function renderEmptyState() {
    const empty = document.createElement('div');
    empty.className = 'flex flex-column items-center justify-center p-12 text-center';
    empty.innerHTML = `
        <svg class="w-16 h-16 text-secondary mb-4">...</svg>
        <h3 class="text-lg font-semibold mb-2">No alerts found</h3>
        <p class="text-secondary mb-4">Try adjusting your filters or create a new alert</p>
    `;
    
    const createBtn = createButton({
        variant: 'primary',
        icon: 'add',
        children: 'Create Alert'
    });
    
    empty.appendChild(createBtn);
    return empty;
}
```

---

## Troubleshooting

### Styles Not Loading:
1. Ensure `variables.css` and `utilities.css` are imported in `index.css`
2. Check that Vite is serving the files correctly
3. Clear browser cache and rebuild: `npm run build`

### Components Not Rendering:
1. Verify import paths are correct
2. Ensure component files are in the `components` directory
3. Check for TypeScript compilation errors: `npm run type-check`

### Dark Mode Not Working:
1. Verify `data-theme="dark"` attribute is set on `<html>` element
2. Check that `variables.css` is loaded
3. Inspect element in DevTools to see computed CSS variables

### Accessibility Issues:
1. Run Lighthouse audit in Chrome DevTools
2. Test keyboard navigation (Tab, Enter, Esc)
3. Test with screen reader (NVDA, JAWS, VoiceOver)

---

## Additional Resources

- [MDN Web Docs - Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Material Symbols Icons](https://fonts.google.com/icons)
- [CSS Variables (Custom Properties)](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)

---

## Support

For questions or issues:
1. Check the `FRONTEND_IMPLEMENTATION_SUMMARY.md` for detailed documentation
2. Review component source code in `frontend/components/`
3. Check existing usage examples in page files

---

**Last Updated**: October 24, 2025  
**Version**: 1.0.0
