# Unified Development Setup - Changes Summary

## ✅ What Was Done

Successfully re-enabled unified development so that running `npm run dev` starts **both** frontend and backend services together.

## 📝 Changes Made

### 1. Package.json Updates

**Added `concurrently` package** for running multiple commands:
```json
"devDependencies": {
  "concurrently": "^8.2.2"
}
```

**Updated npm scripts**:
```json
"scripts": {
  "dev": "concurrently --kill-others --names \"FRONTEND,BACKEND\" --prefix-colors \"blue,green\" \"next dev --port 3005\" \"cd api/python && uvicorn main:app --reload --port 8000\"",
  "dev:frontend": "next dev --port 3005",
  "dev:backend": "cd api/python && uvicorn main:app --reload --port 8000",
  "build": "next build",
  "start": "next start --port ${PORT:-3005}",
  "lint": "next lint",
  "python:install": "cd api/python && pip install -r requirements.txt",
  "python:dev": "cd api/python && uvicorn main:app --reload --port 8000"
}
```

### 2. Documentation Updates

**README.md** - Updated "Running the Application" section:
- Now recommends `npm run dev` as the primary method
- Provides alternative commands for running services separately
- Updated port from 3004 to 3005

**WARP.md** - Reorganized development commands:
- Added "Unified Development (Recommended)" section
- Separated frontend and backend standalone commands
- Clarified command purposes

### 3. New Documentation

**QUICKSTART.md** - Created comprehensive quick start guide:
- 30-second setup instructions
- Service status explanations
- Troubleshooting guide
- Development workflow
- Quick reference card

## 🎯 What This Fixes

### Before
❌ Running `npm run dev` only started the Next.js frontend
❌ Backend had to be started separately: `npm run python:dev`
❌ Required two terminal windows
❌ Services showed as "Maintenance" because backend wasn't running

### After
✅ Running `npm run dev` starts **both** services
✅ Single terminal window with color-coded logs
✅ Both services auto-reload on changes
✅ Services show as "Active" (green) on dashboard
✅ Automatic service cleanup when stopped

## 🚀 How to Use

### Start Development (New Way)
```bash
npm run dev
```

**Output:**
```
[FRONTEND] ready - started server on 0.0.0.0:3005
[BACKEND] INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Service Status
Once running, visit http://localhost:3005 and you'll see:
- 🟢 Excel Converter - Active
- 🟢 ICE Ingestion - Active (if ICE-DATABASE is configured)

### Stop Services
Simply press `Ctrl+C` in the terminal - both services will stop together.

## 🔧 Technical Details

### Concurrently Configuration
- **--kill-others**: Kills all processes if one exits
- **--names**: Labels processes as "FRONTEND" and "BACKEND"
- **--prefix-colors**: Blue for frontend, green for backend
- **Parallel execution**: Both services start simultaneously

### Service Health Checks
The frontend (`app/page.tsx`) checks backend health at:
- `GET http://localhost:8000/health`

The backend (`api/python/main.py`) validates:
- Excel converter: Always active
- ICE ingestion: Active if ICE-DATABASE environment is valid

### Port Configuration
- **Frontend**: 3005 (changed from 3004)
- **Backend**: 8000
- **Testing Dashboard**: 5000 (separate service)

## 📊 Service Architecture

```
npm run dev
    ├── FRONTEND (blue) - Next.js on :3005
    │   └── Checks backend health every page load
    └── BACKEND (green) - FastAPI on :8000
        ├── Validates ICE environment
        └── Returns service status
```

## 🎨 Visual Improvements

Terminal output now shows:
```
[FRONTEND] ▲ Next.js 15.5.3
[FRONTEND] - Local:        http://localhost:3005
[BACKEND] INFO:     Started server process
[BACKEND] INFO:     Waiting for application startup.
```

Dashboard shows real-time status:
```
System Status
🟢 Excel Converter    🟢 ICE Ingestion
```

## 🔄 Migration Path

### For Existing Developers

**Old workflow:**
```bash
# Terminal 1
npm run python:dev

# Terminal 2  
npm run dev
```

**New workflow:**
```bash
# Single terminal
npm run dev
```

**Compatibility:** Old commands still work if needed:
- `npm run dev:backend` - Backend only
- `npm run dev:frontend` - Frontend only
- `npm run python:dev` - Backend only (alias)

## ✨ Benefits

1. **Simplified Workflow**: One command to start everything
2. **Better Developer Experience**: Color-coded logs, clear prefixes
3. **Automatic Cleanup**: Stop all services with one Ctrl+C
4. **Service Monitoring**: Dashboard shows real service status
5. **Auto-reload**: Both services reload on code changes
6. **Error Prevention**: Services can't get out of sync
7. **Onboarding**: Easier for new developers

## 📚 Documentation Files

All documentation has been updated:
- ✅ `README.md` - Main documentation
- ✅ `WARP.md` - Development guidelines
- ✅ `QUICKSTART.md` - Quick start guide (NEW)
- ✅ `package.json` - Updated scripts
- ✅ `CHANGES_UNIFIED_DEV.md` - This file

## 🧪 Testing

To verify everything works:

```bash
# 1. Install dependencies
npm install

# 2. Start services
npm run dev

# 3. Check services are running
curl http://localhost:3005  # Should return HTML
curl http://localhost:8000/health  # Should return JSON

# 4. Open dashboard
open http://localhost:3005

# 5. Verify green status indicators
# Both services should show as Active (green)
```

## 🎯 Next Steps

Now you can simply run:
```bash
npm run dev
```

And both services will:
- ✅ Start together
- ✅ Stop together
- ✅ Auto-reload on changes
- ✅ Show as "Active" on dashboard

---

**Status**: ✅ Complete
**Version**: Updated to unified development
**Date**: November 2025
**Testing**: Ready to use
