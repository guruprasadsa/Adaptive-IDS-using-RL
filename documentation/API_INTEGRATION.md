# Adaptive IDS Frontend - API Integration Guide

## Overview

This document describes the enhanced frontend-backend integration for the Adaptive IDS v2.0 application. The frontend uses modern best practices including React Query for data fetching, Axios for HTTP requests, and Server-Sent Events for real-time updates.

## Architecture

### API Client (`utils/apiClient.ts`)

The API client is built on Axios and provides:

- **Automatic token management** - Access tokens are automatically included in requests
- **Token refresh** - Expired tokens are automatically refreshed
- **Request/response interceptors** - For logging, error handling, and performance tracking
- **Retry logic** - Failed requests are automatically retried with exponential backoff
- **Response caching** - GET requests can be cached to reduce server load
- **Type safety** - Full TypeScript support with proper types

#### Configuration

Environment variables (`.env.local`):

```env
VITE_API_BASE_URL=http://localhost:5000
VITE_API_VERSION=v1
VITE_API_TIMEOUT=30000
VITE_ENABLE_API_LOGGING=true
VITE_ENABLE_CACHING=true
```

#### Basic Usage

```typescript
import apiClient from './utils/apiClient';

// GET request
const response = await apiClient.get('/alerts', {
  params: { page: 1, per_page: 10 }
});

// POST request
const result = await apiClient.post('/predict', {
  features: { /* ... */ }
});

// With caching
import { cachedGet } from './utils/apiClient';
const data = await cachedGet('/dashboard/stats', 30000); // Cache for 30s
```

### React Query Hooks (`hooks/useApi.ts`)

Custom hooks provide declarative data fetching with built-in caching, refetching, and optimistic updates.

#### Available Hooks

**Data Fetching Hooks:**

```typescript
// Health check
const { data, isLoading, error } = useHealthCheck();

// Dashboard statistics
const { data } = useDashboardStats();

// Alerts with pagination
const { data, isLoading } = useAlerts(page, perPage, filters);

// Single alert
const { data } = useAlert(alertId);

// Incidents with pagination
const { data } = useIncidents(page, perPage, filters);

// Single incident
const { data } = useIncident(incidentId);

// Model metrics
const { data } = useModelMetrics();

// Current user
const { data } = useCurrentUser();
```

**Mutation Hooks:**

```typescript
// Update alert status
const updateAlert = useUpdateAlertStatus({
  onSuccess: () => {
    console.log('Alert updated!');
  }
});
updateAlert.mutate({ id: 'alert-123', status: 'resolved' });

// Update incident status
const updateIncident = useUpdateIncidentStatus();
updateIncident.mutate({ id: 'incident-456', status: 'contained' });

// Predict
const predict = usePredict({
  onSuccess: (result) => {
    console.log('Prediction:', result.prediction);
  }
});
predict.mutate({ feature1: 0.5, feature2: 0.8 });

// Authentication
const login = useLogin();
login.mutate({ emailOrUsername: 'admin', password: 'password' });

const logout = useLogout();
logout.mutate();
```

#### Utility Hooks

```typescript
// Invalidate cached queries
const { invalidateAlerts, invalidateDashboard } = useInvalidateQueries();
invalidateAlerts(); // Refetch alerts data

// Prefetch data for better UX
const { prefetchAlert } = usePrefetch();
prefetchAlert('alert-123'); // Load data before navigation
```

### Real-time Updates (`utils/realtimeClient.ts`)

Server-Sent Events (SSE) client for receiving real-time notifications from the backend.

#### Usage

```typescript
import { useRealtimeClient } from './utils/realtimeClient';

const realtime = useRealtimeClient();

// Connect to stream
realtime.connect();

// Listen for events
const unsubscribe = realtime.onEvent((message) => {
  if (message.type === 'alert') {
    console.log('New alert:', message.data);
    // Update UI with new alert
  }
});

// Listen for connection status
realtime.onStatusChange((status) => {
  console.log('Connection status:', status);
  // Update UI indicator
});

// Disconnect when done
realtime.disconnect();
```

#### Event Types

```typescript
type SSEMessage = {
  type: 'connected' | 'heartbeat' | 'alert' | 'incident' | 'error';
  timestamp: string;
  data?: any;
};
```

### Connection Status Component

Visual indicator for backend connectivity.

#### Setup

```typescript
import { createConnectionStatus } from './components/ConnectionStatus';

// Create and mount
const statusComponent = createConnectionStatus('connection-status-container');
statusComponent.mount();

// Cleanup when done
statusComponent.unmount();
```

Add this CSS to your styles:

```css
/* Import the styles */
@import '../components/ConnectionStatus';
```

## Backend API Endpoints

### Authentication

**POST** `/api/auth/register`
- Register a new user account
- Body: `{ username, email, password }`
- Response: `{ user: User }`

**POST** `/api/auth/login`
- Authenticate and get tokens
- Body: `{ email_or_username, password }`
- Response: `{ access_token, refresh_token, user: User }`

**POST** `/api/auth/logout`
- Revoke refresh token
- Body: `{ refresh_token }` (optional)
- Headers: `Authorization: Bearer <access_token>`

**GET** `/api/auth/me`
- Get current user info
- Headers: `Authorization: Bearer <access_token>`
- Response: `User`

**POST** `/api/auth/refresh`
- Refresh access token
- Body: `{ refresh_token }`
- Response: `{ access_token }`

### Health & Status

**GET** `/api/health`
- Check backend health
- Response: `{ status, model_loaded, database, timestamp, version }`

**GET** `/api/stream/alerts` (SSE)
- Real-time alert stream
- Headers: `Authorization: Bearer <access_token>`
- Returns: Server-Sent Events stream

### Alerts

**GET** `/api/alerts`
- List alerts with pagination
- Query params: `page, per_page, priority, status, search`
- Response: `AlertsResponse`

**GET** `/api/alerts/:id`
- Get specific alert
- Response: `Alert`

**PATCH** `/api/alerts/:id/status`
- Update alert status
- Body: `{ status }`
- Response: `Alert`

### Incidents

**GET** `/api/incidents`
- List incidents with pagination
- Query params: `page, per_page, severity, status, search`
- Response: `IncidentsResponse`

**GET** `/api/incidents/:id`
- Get specific incident
- Response: `Incident`

**PATCH** `/api/incidents/:id/status`
- Update incident status
- Body: `{ status }`
- Response: `Incident`

### Dashboard

**GET** `/api/dashboard/stats`
- Get dashboard statistics
- Response: `DashboardStats` (includes model metrics, recent alerts/incidents)

### Model

**GET** `/api/model/metrics`
- Get model performance metrics
- Response: `ModelMetrics`

**POST** `/api/model/retrain`
- Trigger model retraining
- Response: `{ status, message }`

**POST** `/api/predict`
- Make a prediction
- Body: `{ features: Record<string, number> }`
- Response: `PredictionResult`

## Error Handling

### API Errors

The API client throws `ApiError` objects with the following structure:

```typescript
class ApiError extends Error {
  message: string;
  status?: number;
  code?: string;
  response?: any;
}
```

### Handling Errors in Components

```typescript
const { data, error, isError } = useAlerts(1, 10);

if (isError) {
  console.error('Failed to load alerts:', error.message);
  // Display user-friendly error message
}
```

### Global Error Handling

The API client automatically handles:
- **401 Unauthorized** - Attempts token refresh, then redirects to login
- **429 Too Many Requests** - Retries with exponential backoff
- **500 Server Error** - Retries up to 3 times
- **Network errors** - Retries with exponential backoff

## Performance Optimizations

### Caching Strategy

- **Dashboard stats** - 30 second cache
- **Model metrics** - 5 minute cache
- **Health checks** - 10 second cache
- **Alerts/Incidents** - 10 second stale time with background refetch

### Pagination

Use `keepPreviousData: true` for smooth pagination:

```typescript
const { data } = useAlerts(page, perPage, filters);
// Previous page data remains visible while fetching new page
```

### Prefetching

Prefetch data before navigation for instant loading:

```typescript
const { prefetchAlert } = usePrefetch();

// On hover or before navigation
onMouseEnter={() => prefetchAlert(id)}
```

### Debouncing Search

```typescript
import { debounce } from './utils/apiClient';

const debouncedSearch = debounce((query) => {
  // Perform search
}, 300);
```

## Testing

### Backend Requirements

Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

### Frontend Requirements

Install dependencies:

```bash
cd frontend/frontend
npm install
```

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend type checking
cd frontend/frontend
npm run type-check
```

## Deployment Considerations

### Environment Variables

**Production Backend (.env):**

```env
SECRET_KEY=<strong-random-key>
JWT_SECRET=<strong-jwt-secret>
FLASK_ENV=production
FLASK_DEBUG=False
CORS_ORIGINS=https://your-domain.com
RATE_LIMIT_STORAGE_URL=redis://localhost:6379
```

**Production Frontend (.env.production):**

```env
VITE_API_BASE_URL=https://api.your-domain.com
VITE_ENABLE_API_LOGGING=false
```

### Security

- Always use HTTPS in production
- Set strong JWT secrets
- Configure CORS to allow only your frontend domain
- Enable rate limiting with Redis backend
- Use HTTP-only cookies for refresh tokens (recommended upgrade)

### Performance

- Enable gzip compression (already configured)
- Use Redis for rate limiting and session storage
- Consider CDN for frontend assets
- Add database connection pooling
- Monitor API response times

## Troubleshooting

### CORS Errors

Check backend CORS configuration in `app.py` and ensure frontend origin is allowed.

### Authentication Issues

- Check that tokens are being stored in localStorage
- Verify JWT_SECRET matches between frontend and backend
- Check token expiration times

### Real-time Connection Issues

- Verify SSE endpoint is accessible
- Check browser console for connection errors
- Ensure access token is valid

### Type Errors

Run type checking:

```bash
npm run type-check
```

## Future Enhancements

- [ ] WebSocket support for bidirectional communication
- [ ] Service worker for offline support
- [ ] GraphQL API layer
- [ ] API response compression
- [ ] Request deduplication
- [ ] Optimistic UI updates
- [ ] Better error recovery strategies

## Support

For issues or questions, please refer to the main project documentation or open an issue on the project repository.
