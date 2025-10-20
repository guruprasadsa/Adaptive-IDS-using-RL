# Fixing "Session Expired" Error - Troubleshooting Guide

## Issue Description
Users may encounter "Session expired. Please login again" error message when:
1. First loading the application
2. When the SSE (Server-Sent Events) connection attempts to establish
3. When tokens genuinely expire

## Root Causes

### 1. SSE Authentication Issue
**Problem**: EventSource (used for SSE) doesn't support custom headers, so it can't send the Authorization header with the JWT token.

**Solution Implemented**: Modified backend to accept token as query parameter for SSE endpoint.

### 2. Token Refresh Timing
**Problem**: When access token expires, the refresh mechanism might show "session expired" before attempting refresh.

**Solution Implemented**: Improved error handling to only show message after refresh attempts fail.

### 3. Initial Load Check
**Problem**: On first load, the app checks for existing tokens which might trigger unnecessary error messages.

**Solution Implemented**: Better logging to differentiate between "no token" and "expired token" scenarios.

## Changes Made

### Backend Changes

#### 1. Modified SSE Endpoint (`backend/api/app.py`)
```python
@app.route("/api/stream/alerts", methods=["GET"])
def stream_alerts() -> Any:
    # Accept token as query parameter (since EventSource doesn't support headers)
    token = request.args.get('token', '')
    
    # Fallback to Authorization header
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    
    # Validate token manually
    user_id = None
    if token:
        try:
            from auth import jwt_decode
            payload = jwt_decode(token)
            if payload:
                user_id = payload.get('user_id')
        except Exception as e:
            logging.warning(f"SSE token validation failed: {e}")
    
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # ... rest of SSE logic
```

**Why**: This allows the SSE connection to authenticate using query parameter, which EventSource supports.

### Frontend Changes

#### 1. Improved RealtimeClient (`frontend/utils/realtimeClient.ts`)
```typescript
connect(): void {
    const accessToken = tokenManager.getAccessToken();
    if (!accessToken) {
        console.log('SSE: No access token available, skipping connection');
        this.updateStatus('disconnected');
        return; // Don't show error
    }
    
    // URL-encode the token
    const url = `${API_BASE_URL}/api/stream/alerts?token=${encodeURIComponent(accessToken)}`;
    this.eventSource = new EventSource(url);
}
```

**Why**: Properly passes token as query parameter and handles missing token gracefully.

#### 2. Better Error Handling in AuthService (`frontend/services/authService.ts`)
```typescript
private async checkAuthStatus(): Promise<void> {
    // ... code ...
    try {
        const user = await apiService.getCurrentUser();
        // Success
    } catch (error: any) {
        // Only log if it's not a simple "no token" scenario
        if (error.status !== 401) {
            console.error('Failed to validate authentication:', error);
        }
        // Clear tokens silently
        apiService.clearTokens();
    }
}
```

**Why**: Prevents showing error messages for normal "not logged in" states.

#### 3. Improved Connection Timing (`frontend/index.tsx`)
```typescript
private async loadInitialData() {
    try {
        // Load all data first
        // ...
        
        // Connect to realtime AFTER successful data load
        this.connectRealtime();
    } catch (error) {
        // Handle error
    }
}
```

**Why**: Ensures we only attempt SSE connection after we know the backend is available and we have valid tokens.

## Testing the Fix

### 1. Test Fresh Load (No Tokens)
```
1. Clear localStorage
2. Open application
3. Should show login page WITHOUT error message
4. Login should work normally
```

### 2. Test Valid Session
```
1. Login successfully
2. Navigate to different pages
3. Should NOT see "session expired" errors
4. SSE connection should establish successfully
```

### 3. Test Token Expiration
```
1. Login successfully
2. Wait for token to expire (or modify token TTL to 30 seconds for testing)
3. Make an API request
4. Should automatically refresh token
5. Request should succeed without showing error
```

### 4. Test Refresh Token Expiration
```
1. Login successfully
2. Manually delete or corrupt refresh token in localStorage
3. Make an API request after access token expires
4. Should show "Session expired" and redirect to login
```

## Verification Steps

### Check Backend is Running
```cmd
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "model_loaded": true,
  "database": "connected",
  "timestamp": "2025-10-20T...",
  "version": "2.0.0"
}
```

### Check SSE Endpoint
```cmd
# Test without token (should fail)
curl http://localhost:5000/api/stream/alerts

# Test with token (replace TOKEN with actual JWT)
curl "http://localhost:5000/api/stream/alerts?token=TOKEN"
```

### Check Frontend Console
Open browser DevTools (F12) and check Console for:
- ✅ `SSE connection established` (good)
- ✅ `Realtime event received: {type: 'connected'}` (good)
- ❌ `Session expired` on initial load (bad - means fix didn't work)
- ❌ `SSE error` continuously (bad - token not being passed correctly)

### Check Network Tab
1. Open DevTools → Network tab
2. Filter by "stream"
3. Look for `/api/stream/alerts?token=...` request
4. Should show Status: 200 and Type: eventsource
5. Click on it → Preview tab should show events

## Common Issues After Fix

### Issue 1: Still Seeing "Session Expired"
**Cause**: Old code is cached in browser

**Solution**:
```cmd
# Clear browser cache
Ctrl + Shift + Delete → Clear cache

# Hard refresh
Ctrl + Shift + R

# Or restart dev server
cd frontend/frontend
npm run dev
```

### Issue 2: SSE Connection Fails
**Cause**: Backend not updated or CORS issue

**Solution**:
```cmd
# Restart backend
cd backend/api
python app.py

# Check CORS settings in backend/.env
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Issue 3: Token Not Being Sent
**Cause**: Token might be malformed or not stored

**Solution**:
```javascript
// In browser console:
console.log(localStorage.getItem('adaptive_ids_access_token'));
console.log(localStorage.getItem('adaptive_ids_refresh_token'));

// If null or undefined:
// 1. Login again
// 2. Check if authService.ts is properly saving tokens
```

### Issue 4: CORS Errors in Console
**Cause**: Backend CORS not configured for EventSource

**Solution**:
```python
# In backend/api/app.py, verify CORS config includes:
CORS(app, resources={
    r"/api/*": {
        "origins": cors_origins,
        "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})
```

## Environment Variables Check

### Backend `.env`
```env
JWT_SECRET=your-secret-here
ACCESS_TOKEN_TTL=900          # 15 minutes
REFRESH_TOKEN_TTL=604800      # 7 days
CORS_ORIGINS=http://localhost:5173
```

### Frontend `.env`
```env
VITE_API_BASE_URL=http://localhost:5000
VITE_ENABLE_API_LOGGING=true  # For debugging
```

## Additional Debugging

### Enable Verbose Logging

#### Frontend
```typescript
// In frontend/.env
VITE_ENABLE_API_LOGGING=true

// Or modify apiClient.ts temporarily:
const ENABLE_LOGGING = true;
```

#### Backend
```python
# In backend/api/app.py
logging.basicConfig(level=logging.DEBUG)
```

### Monitor Token Lifecycle
```javascript
// Add to browser console:
setInterval(() => {
    const token = localStorage.getItem('adaptive_ids_access_token');
    if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const exp = new Date(payload.exp * 1000);
        console.log('Token expires at:', exp);
        console.log('Time until expiry:', (payload.exp * 1000 - Date.now()) / 1000, 'seconds');
    }
}, 5000);
```

## Production Considerations

For production deployment, consider:

1. **Use WebSocket instead of SSE** for better authentication support
2. **Implement httpOnly cookies** instead of localStorage
3. **Add CSRF protection** for cookie-based auth
4. **Use shorter access token TTL** (5-15 minutes)
5. **Implement token rotation** for refresh tokens
6. **Add rate limiting** on auth endpoints
7. **Monitor token refresh patterns** for security

## Summary of Fixes

✅ Modified backend SSE endpoint to accept token as query parameter  
✅ Updated frontend to URL-encode token in SSE connection  
✅ Improved error handling to avoid false "session expired" messages  
✅ Better logging to differentiate between error types  
✅ Connect to SSE only after successful data load  
✅ Gracefully handle missing tokens on initial load  

## If Issues Persist

1. **Check browser console** for specific error messages
2. **Check backend logs** for authentication failures
3. **Verify database** has users table and admin user
4. **Test API endpoints directly** with curl/Postman
5. **Clear all browser data** and test fresh
6. **Review token payload** to ensure it's valid JWT

## Contact Support

If the issue persists after following this guide:
1. Check `documentation/AUTH_SETUP_GUIDE.md`
2. Review `documentation/AUTH_QUICK_REFERENCE.md`
3. Enable debug logging and capture console output
4. Check Network tab for failed requests
5. Verify all environment variables are set correctly

---

**Fix Version**: 1.1  
**Date**: October 20, 2025  
**Status**: ✅ Implemented and Tested
