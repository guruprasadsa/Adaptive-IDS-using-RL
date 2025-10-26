# Troubleshooting: ModuleNotFoundError in Model Service

## Issue
```
ModuleNotFoundError: No module named 'torch'
```

## Root Cause
The Docker container was built before the updated `requirements.txt` was in place, or Docker is using cached layers that don't include the PyTorch installation.

## Solution

### Option 1: Quick Rebuild (Recommended)
Run the provided rebuild script:

```cmd
rebuild_model_service.bat
```

This will:
1. Stop the model service
2. Remove the old container and image
3. Rebuild from scratch (no cache)
4. Start the service
5. Show logs

### Option 2: Manual Rebuild

#### Windows (cmd):
```cmd
docker compose stop model-service
docker compose rm -f model-service
docker compose build --no-cache model-service
docker compose up -d model-service
docker compose logs -f model-service
```

#### Linux/Mac:
```bash
docker compose stop model-service
docker compose rm -f model-service
docker compose build --no-cache model-service
docker compose up -d model-service
docker compose logs -f model-service
```

### Option 3: Rebuild All Services
If you want to rebuild everything:

```cmd
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Verification

### 1. Check Service Status
```cmd
docker compose ps model-service
```

Should show status as "running" and healthy.

### 2. Test Health Endpoint
```cmd
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "service": "model-inference",
  "model_ready": true,
  "worker_running": true
}
```

### 3. Check Model Info
```cmd
curl http://localhost:8000/model/info
```

Should return model metadata without errors.

### 4. View Logs
```cmd
docker compose logs model-service
```

Look for:
- ✅ "Loading model from..."
- ✅ "Model loaded successfully"
- ✅ "Subscribed to topic: flows.features"
- ❌ No "ModuleNotFoundError" or import errors

## Common Issues After Rebuild

### Issue: Model file not found
```
FileNotFoundError: Model file not found: ./model/checkpoints/final_model.pth
```

**Solution:**
Ensure the model checkpoint exists:
```cmd
dir backend\model\checkpoints\final_model.pth
```

If missing, you need to train the model first:
```cmd
python backend/scripts/train.py
```

### Issue: Label classes file not found
```
Label classes file not found: ./model/output/run_1758022767/label_classes.json
```

**Solution:**
Check if the output directory exists:
```cmd
dir backend\model\output\run_*\label_classes.json
```

If the run ID is different, update the environment variable in `docker-compose.yml`:
```yaml
- LABEL_CLASSES_PATH=/app/model/output/run_YOUR_RUN_ID/label_classes.json
```

### Issue: Kafka connection failed
```
Failed to initialize Kafka: ...
```

**Solution:**
Ensure Kafka is running and healthy:
```cmd
docker compose ps kafka
docker compose logs kafka
```

Wait for Kafka to be fully started (green health status).

### Issue: Build fails with "gcc not found"
```
error: command 'gcc' failed
```

**Solution:**
The updated Dockerfile now includes `gcc` and `g++`. If you still see this, ensure Docker has enough resources:
- Docker Desktop: Settings → Resources → Increase Memory to at least 4GB

### Issue: Container exits immediately
```cmd
docker compose logs model-service
```

Look for startup errors. Common causes:
1. Invalid environment variables
2. Missing model files
3. Port 8000 already in use

**Check port:**
```cmd
netstat -ano | findstr :8000
```

## Dockerfile Changes Made

The `Dockerfile.model` was updated to:
1. Add `g++` compiler for building Python packages
2. Upgrade pip, setuptools, and wheel
3. Install PyTorch from CPU-optimized wheel first
4. Then install remaining requirements

This ensures PyTorch is installed correctly before other dependencies.

## Prevention

To avoid this issue in future:
1. Always rebuild after updating `requirements.txt`:
   ```cmd
   docker compose build --no-cache model-service
   ```

2. Use the `--no-cache` flag when dependencies change

3. For development, consider using volume mounts with local Python environment instead of rebuilding

## Additional Resources

- **Service Documentation**: `backend/model/service/README.md`
- **Quick Start Guide**: `backend/model/service/QUICKSTART.md`
- **Docker Compose Reference**: `docker-compose.yml`

## Getting Help

If the issue persists after rebuilding:

1. **Check Docker logs:**
   ```cmd
   docker compose logs --tail=100 model-service
   ```

2. **Exec into container and check Python:**
   ```cmd
   docker exec -it adaptive_ids_model_service python -c "import torch; print(torch.__version__)"
   ```

3. **Verify requirements are installed:**
   ```cmd
   docker exec -it adaptive_ids_model_service pip list | findstr torch
   ```

4. **Check build output for errors:**
   Rebuild with verbose output:
   ```cmd
   docker compose build --no-cache --progress=plain model-service
   ```
