# Quick Start Guide - Enterprise Tools Platform

## 🚀 Get Started in 30 Seconds

### Prerequisites Check
```bash
node --version  # Should be 18+
python3 --version  # Should be 3.9+
```

### One-Command Setup
```bash
# 1. Install all dependencies
npm install

# 2. Install Python backend dependencies
npm run python:install

# 3. Start both frontend and backend
npm run dev
# Note: This automatically cleans up ports 3005 and 8000 before starting!
```

### Access Your Applications
- **Frontend Dashboard**: http://localhost:3005
- **Backend API Docs**: http://localhost:8000/docs
- **Testing Dashboard**: http://localhost:5000 (run `./start_dashboard.sh`)

## 📊 What You Get

### ✅ Both Services Running Together
When you run `npm run dev`, you get:
- **FRONTEND** (blue): Next.js on port 3005
- **BACKEND** (green): FastAPI on port 8000

### 🎯 Available Tools
1. **QR Code Generator** - Always active
2. **Excel to CSV Converter** - Active when backend is running
3. **ICE Database Ingestion** - Active when backend is running

## 🔧 Advanced Usage

### Run Services Separately
```bash
# Terminal 1: Backend only
npm run dev:backend

# Terminal 2: Frontend only
npm run dev:frontend
```

### Check Service Status
The dashboard automatically checks service health:
- 🟢 **Green** = Service is active and ready
- 🔴 **Red** = Service is in maintenance or not running

### Troubleshooting

**Services show as "Maintenance"?**
- Make sure Python backend is running: `npm run dev:backend`
- Check backend logs at: http://localhost:8000/health

**Port conflicts?**
```bash
# Automatically cleanup ports and restart
npm run cleanup
npm run dev

# Or manually check what's using the ports
lsof -i :3005  # Frontend
lsof -i :8000  # Backend
```

**Backend won't start?**
```bash
# Install Python dependencies again
npm run python:install
```

**Frontend won't start?**
```bash
# Reinstall Node modules
npm install
```

## 📁 ICE Database Setup (Optional)

If you need ICE database functionality:

```bash
# 1. Check if ICE-DATABASE exists
ls /home/sebastiangarcia/ICE-DATABASE/

# 2. Environment should already be configured
# If not, copy from ICE-DATABASE
cp /home/sebastiangarcia/ICE-DATABASE/.env api/python/.env
```

## 🎯 Development Workflow

### Making Changes

1. **Frontend changes**: Auto-reload in browser
2. **Backend changes**: FastAPI auto-reloads
3. **Both stay in sync** automatically

### Testing Your Changes

```bash
# Run linter
npm run lint

# Build for production
npm run build

# Test backend API
curl http://localhost:8000/health
```

## 🆘 Need Help?

### Common Commands
```bash
# View all available commands
npm run

# Stop all services
Ctrl+C (in the terminal running npm run dev)

# Clean restart
killall node python3
npm run dev
```

### File Locations
- **Frontend code**: `app/`
- **Backend code**: `api/python/`
- **Shared components**: `app/components/`
- **API client**: `app/lib/api.ts`

### Logs
- **Frontend**: Terminal output (blue)
- **Backend**: Terminal output (green)
- **Backend API docs**: http://localhost:8000/docs

## ✨ What Changed

### Before (Manual)
You had to run two separate commands in two terminals:
```bash
# Terminal 1
npm run python:dev

# Terminal 2
npm run dev
```

### Now (Automatic) ✅
One command runs everything:
```bash
npm run dev
```

Both services start together, stop together, and auto-reload on changes!

---

**Quick Reference Card**
```
Start Everything:     npm run dev
Frontend Only:        npm run dev:frontend  
Backend Only:         npm run dev:backend
Install Dependencies: npm install && npm run python:install
View API Docs:        http://localhost:8000/docs
Dashboard:            http://localhost:3005
Stop Services:        Ctrl+C
```
