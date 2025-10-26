# Frontend Real-Time Alerts - Quick Reference

## Phase 8 Implementation Summary

### New Components Created
- ✅ `frontend/utils/csvExport.ts` - CSV export utility
- ✅ Enhanced SSE client with topic support
- ✅ Advanced filter UI with 8 filter types
- ✅ Enhanced alert table with 9 columns
- ✅ Alert action buttons (ack, FP, view)
- ✅ 300+ lines of new CSS

### Files Modified (6)
1. `frontend/types.ts` - Extended Alert, AlertsState, SSEMessage
2. `frontend/utils/realtimeClient.ts` - Updated SSE endpoint
3. `frontend/pages/AlertsPage.ts` - Enhanced UI
4. `frontend/index.tsx` - Event handlers
5. `frontend/api.ts` - New API methods
6. `frontend/index.css` - New styles

---

## Quick Usage Guide

### Advanced Filters
```typescript
// 8 available filters:
severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
className: string (e.g., 'DDoS', 'PortScan')
srcIp: string (e.g., '192.168.1.100')
dstIp: string (e.g., '10.0.0.50')
minConfidence: number (0-100)
maxConfidence: number (0-100)
startTime: string (ISO 8601)
endTime: string (ISO 8601)
```

### Alert Actions
```typescript
// Acknowledge alert
apiService.acknowledgeAlert(alertId, notes?)

// Mark false positive
apiService.markAlertFalsePositive(alertId, feedback?)

// View details
viewAlertDetails(alertId) // Shows modal with full info
```

### CSV Export
```typescript
// Export filtered alerts
exportAlertsToCSV(alerts, filename)

// Auto-generate filename with timestamp
const filename = generateCSVFilename('alerts')
// Result: alerts_2025-01-15T10-30-00.csv
```

### SSE Client
```typescript
const client = getRealtimeClient()

// Connect to alerts topic
client.connect('alerts')

// Subscribe to events
client.onEvent((message: SSEMessage) => {
  console.log(message.type, message.data)
})

// Subscribe to alerts only
client.onAlert((alert: Alert) => {
  console.log('New alert:', alert.description)
})

// Check status
client.isConnected() // true/false
client.getStatus() // 'connected' | 'disconnected' | 'reconnecting' | 'error'
```

---

## API Integration

### Endpoints Used
```
GET  /api/events?token={jwt}&topic=alerts
GET  /api/alerts?page=1&per_page=10&severity=HIGH&...
PATCH /api/alerts/{id}/ack
POST /api/alerts/{id}/false-positive
```

### Filter Parameters
```typescript
{
  page: number
  per_page: number
  priority?: 'critical' | 'high' | 'medium' | 'low'
  status?: 'new' | 'investigating' | 'resolved' | 'false_positive'
  severity?: string
  className?: string
  srcIp?: string
  dstIp?: string
  minConfidence?: number
  maxConfidence?: number
  startTime?: string
  endTime?: string
}
```

---

## UI Components

### Toolbar Buttons
- **Filters** - Toggle advanced filters section
- **Export CSV** - Download filtered alerts
- **Refresh** - Reload current page

### Advanced Filters (Collapsible)
- Severity dropdown (5 levels)
- Attack Type text input
- Source IP text input
- Destination IP text input
- Min/Max Confidence number inputs
- Start/End Time datetime inputs
- Apply Filters button
- Clear All button

### Alert Table (9 Columns)
| Column | Type | Features |
|--------|------|----------|
| Priority | Badge | Color-coded |
| Severity | Badge | 5-level colors |
| Timestamp | DateTime | Localized |
| Attack Type | Badge | Class colors |
| Source IP | Text | Monospace |
| Dest IP | Text | Monospace |
| Confidence | Bar | 0-100% visual |
| Status | Badge | 4 states |
| Actions | Icons | 3 buttons |

### Action Buttons
- ✅ **Acknowledge** - Mark resolved with notes
- ❌ **False Positive** - Mark FP with feedback
- 👁️ **View Details** - Show full alert info

---

## CSS Classes Reference

### Severity Badges
```css
.severity-critical  /* Red - #fee/#b91c1c */
.severity-high      /* Orange - #ffedd5/#c2410c */
.severity-medium    /* Yellow - #fef3c7/#a16207 */
.severity-low       /* Blue - #dbeafe/#1e40af */
.severity-info      /* Indigo - #e0e7ff/#4338ca */
```

### Attack Class Badges
```css
.class-ddos         /* Red */
.class-portscan     /* Orange */
.class-bruteforce   /* Yellow */
.class-botnet       /* Purple */
.class-webattack    /* Pink */
.class-other        /* Indigo */
```

### Action Buttons
```css
.ack-alert-btn      /* Green on hover */
.fp-alert-btn       /* Red on hover */
.view-alert-btn     /* Blue on hover */
```

---

## Event Handlers

### Click Handlers (13)
```typescript
- Navigation links
- Pagination buttons
- Toggle filters button
- Export CSV button
- Refresh alerts button
- Apply filters button
- Clear filters button
- Acknowledge alert button (.ack-alert-btn)
- False positive button (.fp-alert-btn)
- View details button (.view-alert-btn)
```

### Change Handlers
```typescript
- Priority filter (dropdown)
- Status filter (dropdown)
- Severity filter (dropdown)
- Advanced filter inputs (text/number/date)
```

### Input Handlers
```typescript
- Search input (debounced)
```

---

## Testing Checklist

### Connection
- [ ] SSE connects on app load
- [ ] Reconnects after network drop
- [ ] Heartbeat every 30s

### Filters
- [ ] All 8 filters work
- [ ] Apply button sends to API
- [ ] Clear resets all

### Actions
- [ ] Acknowledge calls PATCH
- [ ] FP calls POST
- [ ] View shows details

### Export
- [ ] CSV downloads
- [ ] 16 columns included
- [ ] UTF-8 BOM for Excel

### Real-Time
- [ ] New alerts appear
- [ ] UI refreshes on Alerts page
- [ ] Keeps 100 alerts max

---

## Common Tasks

### Add New Filter
1. Add to `AlertsState.filters` type
2. Add UI input to `renderAlertsToolbar()`
3. Update `handleAdvancedFilterChange()`
4. Backend automatically handles new parameter

### Add New Action
1. Add button to `renderAlertsTable()`
2. Add handler method (e.g., `assignAlert()`)
3. Add API method to `api.ts`
4. Wire up in `attachEventListeners()`

### Add New Badge Color
1. Define CSS class in `index.css`
2. Add to badge mapping function
3. Apply class in table cell

---

## Performance Notes

- **Pagination**: Only 10-50 alerts per page
- **Memory**: Max 100 alerts cached
- **SSE**: Single connection, shared across app
- **CSV**: Client-side generation, no server load
- **Debounce**: Search waits 300ms before API call

---

## Troubleshooting

### SSE Not Connecting
```typescript
// Check authentication
tokenManager.getAccessToken() // Should return JWT

// Check connection status
const client = getRealtimeClient()
console.log(client.getStatus()) // Should be 'connected'

// Check browser console
// Look for "SSE connection established"
```

### Filters Not Working
```typescript
// Check filter state
console.log(this.alertsState.filters)

// Check API params
// Open Network tab in DevTools
// Look at /api/alerts request query params
```

### Actions Failing
```typescript
// Check API response
try {
  await apiService.acknowledgeAlert(id, notes)
} catch (error) {
  console.error('API error:', error.response?.data)
}

// Check authentication
// 401 = token expired, need to refresh
```

---

## File Sizes

- `csvExport.ts`: ~120 lines
- `realtimeClient.ts`: ~310 lines
- `AlertsPage.ts`: ~180 lines
- `index.tsx`: ~790 lines
- `api.ts`: ~195 lines
- `index.css`: ~1450 lines
- **Total**: ~1,200 lines of TS/TSX, ~300 lines of CSS

---

## Browser Compatibility

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Mobile browsers (iOS Safari, Chrome Android)
- ⚠️ IE11 not supported (EventSource API required)

---

## Next Phase Recommendations

1. Custom modal components (replace alert dialogs)
2. Toast notifications (non-blocking)
3. Bulk actions (checkboxes + batch operations)
4. Filter presets (save common filters)
5. Alert assignment UI (dropdown)
6. WebSocket upgrade (bi-directional)
7. Dark mode support
8. Notification badges (unread count)
9. Sound alerts (critical only)
10. Virtual scrolling (performance)
