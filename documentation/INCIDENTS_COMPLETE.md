# Incidents Management System - Complete Implementation

## Overview
Complete implementation of the Incidents Management system with CRUD operations, status workflow, alert linking, and real-time UI updates.

## Backend Implementation

### 1. API Endpoints (`backend/api/routes/incidents.py`)

#### Create Incident
```
POST /api/incidents
Permission: 'create_incidents'
```

**Request Body:**
```json
{
  "title": "string (required, max 200 chars)",
  "description": "string (required)",
  "severity": "low|medium|high|critical (required)",
  "alert_ids": ["uuid", ...] (optional)
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "incident_id": "INC-{uuid}",
  "title": "string",
  "description": "string",
  "status": "open",
  "severity": "low|medium|high|critical",
  "assigned_to": null,
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp",
  "related_alerts": ["uuid", ...]
}
```

#### Update Incident Status
```
PATCH /api/incidents/:id/status
Permission: 'update_incidents'
```

**Request Body:**
```json
{
  "status": "open|investigating|contained|resolved"
}
```

**Valid Transitions:**
- `open` → `investigating`, `resolved`
- `investigating` → `contained`, `resolved`
- `contained` → `resolved`
- `resolved` → (no transitions)

#### Assign Incident
```
PATCH /api/incidents/:id/assign
Permission: 'update_incidents'
```

**Request Body:**
```json
{
  "assigned_to": "username"
}
```

#### Link Alerts to Incident
```
POST /api/incidents/:id/alerts
Permission: 'update_incidents'
```

**Request Body:**
```json
{
  "alert_ids": ["uuid", "uuid", ...]
}
```

#### Unlink Alert from Incident
```
DELETE /api/incidents/:id/alerts/:alert_id
Permission: 'update_incidents'
```

### 2. Database Models (`backend/db/models.py`)

#### Alert Model
```python
class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True))
    severity = Column(String)
    status = Column(String)
    type = Column(String)
    confidence = Column(Float)
    source = Column(String)
    src_ip = Column(String)
    dst_ip = Column(String)
    src_port = Column(Integer)
    dst_port = Column(Integer)
    protocol = Column(String)
    raw_payload = Column(JSONB)
    tags = Column(ARRAY(String))
    class_name = Column(String)
    class_idx = Column(Integer)
    model_version = Column(String)
    feature_version = Column(String)
    assigned_to = Column(String)
    notes = Column(Text)
```

#### Incident Model
```python
class Incident(db.Model):
    __tablename__ = 'incidents'
    
    id = Column(String, primary_key=True)
    incident_id = Column(String, unique=True)
    title = Column(String)
    description = Column(Text)
    status = Column(String)  # open, investigating, contained, resolved
    severity = Column(String)  # low, medium, high, critical
    assigned_to = Column(String)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    related_alerts = Column(JSONB)  # Array of alert IDs
```

### 3. Blueprint Registration

In `backend/api/app.py`:
```python
try:
    from backend.api.routes.incidents import incidents_bp
    app.register_blueprint(incidents_bp)
    logger.info("Incidents blueprint registered successfully")
except Exception as e:
    logger.error(f"Failed to register incidents blueprint: {e}")
```

## Frontend Implementation

### 1. Incidents Service (`frontend/services/incidentsService.ts`)

**Functions:**
- `createIncident(data)` - Create new incident
- `updateIncidentStatus(id, status)` - Update incident status
- `assignIncident(id, assignedTo)` - Assign incident to user
- `linkAlertsToIncident(id, alertIds)` - Link alerts
- `unlinkAlertFromIncident(id, alertId)` - Unlink alert

**Usage Example:**
```typescript
import { createIncident, updateIncidentStatus } from '../services/incidentsService';

// Create incident
const incident = await createIncident({
  title: "Suspicious port scan",
  description: "Multiple ports scanned from 192.168.1.100",
  severity: "high",
  alert_ids: ["alert-uuid-1", "alert-uuid-2"]
});

// Update status
await updateIncidentStatus(incident.id, "investigating");
```

### 2. UI Components (`frontend/pages/IncidentsPage.ts`)

#### Create Incident Modal
**Features:**
- Title input (max 200 chars)
- Description textarea
- Severity dropdown (critical, high, medium, low)
- Alert selector with search
- Displays up to 10 recent alerts
- Real-time alert search filtering

#### Actions Column in Table
**Dynamic Status Buttons:**
- Open → Shows "Investigate" and "Resolve" buttons
- Investigating → Shows "Contain" and "Resolve" buttons
- Contained → Shows "Resolve" button
- Resolved → No action buttons

**Button Icons:**
- Investigate: 🔍 (search icon)
- Contain: 🛡️ (shield icon)
- Resolve: ✓ (check_circle icon)

### 3. Event Listeners

**Setup Function:**
```typescript
setupIncidentsEventListeners(onRefresh: () => void, alerts: Alert[]): void
```

**Events Handled:**
1. **Create Incident Button** - Opens modal
2. **Status Update Buttons** - Updates incident status
3. **Modal Close** - Via close button, cancel, or backdrop click
4. **Alert Search** - Filters alert list in real-time
5. **Form Submit** - Validates and creates incident

### 4. Styles (`frontend/styles/pages.css`)

**Added Styles:**
- `.alerts-selector` - Alert picker container
- `.alerts-list` - Scrollable alert list (max 250px)
- `.alert-checkbox` - Individual alert item
- `.alert-info` - Alert details display
- `.modal-actions` - Modal footer buttons
- `.action-buttons` - Incidents table action buttons
- `.btn-icon` - Icon-only action buttons

## Workflow

### Creating an Incident

1. User clicks "Create Incident" button
2. Modal opens with form
3. User fills required fields (title, description, severity)
4. Optionally selects related alerts
5. User submits form
6. Frontend validates input
7. POST request to `/api/incidents`
8. Backend validates permissions
9. Backend creates incident with UUID and INC-{uuid} identifier
10. Backend links selected alerts
11. Success toast notification
12. Modal closes
13. Incidents list refreshes

### Updating Status

1. User clicks status action button (e.g., "Investigate")
2. Frontend extracts incident ID and new status
3. PATCH request to `/api/incidents/:id/status`
4. Backend validates status transition
5. Backend updates incident and timestamp
6. Success toast notification
7. Incidents list refreshes
8. Action buttons update based on new status

## Permission Requirements

### Backend Permissions
- `create_incidents` - Create new incidents
- `update_incidents` - Update status, assign, link/unlink alerts
- `view_incidents` - View incidents list (inherited from page access)

### Frontend RBAC
Permissions checked via `authState.user.permissions`:
```typescript
const canCreateIncidents = user?.permissions?.includes('create_incidents');
const canUpdateIncidents = user?.permissions?.includes('update_incidents');
```

## Status Workflow

```
    open
      ↓
  investigating
      ↓
   contained
      ↓
   resolved
```

**Allowed Transitions:**
- open → investigating, resolved
- investigating → contained, resolved  
- contained → resolved
- resolved → (terminal state)

## Error Handling

### Backend Errors
- **400** - Invalid request (missing fields, invalid status transition)
- **403** - Insufficient permissions
- **404** - Incident or alert not found
- **500** - Server error

### Frontend Error Handling
```typescript
try {
  await createIncident(data);
  toast.show({ message: 'Success', type: 'success' });
} catch (error) {
  console.error('Error:', error);
  toast.show({ message: 'Failed', type: 'error' });
}
```

## Testing

### Manual Testing Steps

1. **Create Incident:**
   ```
   - Navigate to Incidents page
   - Click "Create Incident"
   - Fill all fields
   - Select 2-3 alerts
   - Submit
   - Verify incident appears in table
   ```

2. **Update Status:**
   ```
   - Find an open incident
   - Click "Investigate" button
   - Verify status updates to "investigating"
   - Verify buttons change (Contain, Resolve)
   - Click "Contain"
   - Verify status updates to "contained"
   ```

3. **Alert Search:**
   ```
   - Open Create Incident modal
   - Type in alert search box
   - Verify alerts filter correctly
   ```

### API Testing with curl

**Create Incident:**
```bash
curl -X POST http://localhost:5001/api/incidents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "title": "Test Incident",
    "description": "Testing incident creation",
    "severity": "high",
    "alert_ids": ["alert-uuid"]
  }'
```

**Update Status:**
```bash
curl -X PATCH http://localhost:5001/api/incidents/<incident-id>/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"status": "investigating"}'
```

## Future Enhancements

### Planned Features
1. **Incident Comments** - Add discussion thread to incidents
2. **Incident Timeline** - Show history of status changes
3. **Bulk Operations** - Update multiple incidents at once
4. **Incident Templates** - Pre-fill common incident types
5. **Auto-escalation** - Automatically escalate based on severity/time
6. **Email Notifications** - Notify on assignment or status change
7. **Incident Metrics** - MTTR, resolution rates, etc.

### Technical Improvements
1. **Pagination** - Backend pagination for large incident lists
2. **Advanced Filters** - Filter by status, severity, assignee, date range
3. **Export** - CSV export for incident reports
4. **Attachments** - Upload evidence files
5. **Related Incidents** - Link similar incidents

## File Locations

### Backend Files
```
backend/
├── api/
│   ├── app.py (blueprint registration)
│   └── routes/
│       └── incidents.py (API endpoints)
└── db/
    ├── models.py (SQLAlchemy models)
    └── schema.sql (database schema)
```

### Frontend Files
```
frontend/
├── pages/
│   └── IncidentsPage.ts (UI components + event listeners)
├── services/
│   └── incidentsService.ts (API client)
├── styles/
│   └── pages.css (incidents modal styles)
└── index.tsx (app initialization)
```

## Dependencies

### Backend
- Flask (blueprints, request handling)
- SQLAlchemy (ORM)
- PostgreSQL (database with JSONB support)
- flask-sqlalchemy (Flask integration)

### Frontend
- TypeScript (type safety)
- Vite (bundler)
- Axios (HTTP client via apiClient)
- Material Symbols (icons)

## Summary

✅ **Backend:** 5 API endpoints with RBAC, status validation, alert linking
✅ **Database:** SQLAlchemy models with JSONB for flexible alert storage
✅ **Frontend:** Create modal, action buttons, status workflow
✅ **Services:** Typed API client with error handling
✅ **Styles:** Modal, alert selector, action buttons
✅ **Integration:** Event listeners, toast notifications, list refresh

The incidents system is **production-ready** for basic CRUD operations with room for future enhancements.
