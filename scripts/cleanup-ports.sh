#!/bin/bash
# Cleanup ports 3005 and 8000 before starting services

echo "🧹 Cleaning up ports 3005 and 8000..."

# Kill any node processes (Next.js)
NODE_PROCS=$(pgrep -f "next dev")
if [ ! -z "$NODE_PROCS" ]; then
    echo "  Killing Next.js processes: $NODE_PROCS"
    kill -9 $NODE_PROCS 2>/dev/null
fi

# Kill any python/uvicorn processes
PYTHON_PROCS=$(pgrep -f "uvicorn")
if [ ! -z "$PYTHON_PROCS" ]; then
    echo "  Killing uvicorn processes: $PYTHON_PROCS"
    kill -9 $PYTHON_PROCS 2>/dev/null
fi

# Kill processes on port 3005 using lsof
PORT_3005=$(lsof -ti:3005 2>/dev/null)
if [ ! -z "$PORT_3005" ]; then
    echo "  Killing process on port 3005 (lsof): $PORT_3005"
    kill -9 $PORT_3005 2>/dev/null
fi

# Kill processes on port 3005 using ss (more reliable)
PORT_3005_SS=$(ss -tulpn 2>/dev/null | grep :3005 | grep -oP 'pid=\K[0-9]+')
if [ ! -z "$PORT_3005_SS" ]; then
    echo "  Killing process on port 3005 (ss): $PORT_3005_SS"
    kill -9 $PORT_3005_SS 2>/dev/null
fi

# Kill processes on port 8000 using lsof
PORT_8000=$(lsof -ti:8000 2>/dev/null)
if [ ! -z "$PORT_8000" ]; then
    echo "  Killing process on port 8000 (lsof): $PORT_8000"
    kill -9 $PORT_8000 2>/dev/null
fi

# Kill processes on port 8000 using ss
PORT_8000_SS=$(ss -tulpn 2>/dev/null | grep :8000 | grep -oP 'pid=\K[0-9]+')
if [ ! -z "$PORT_8000_SS" ]; then
    echo "  Killing process on port 8000 (ss): $PORT_8000_SS"
    kill -9 $PORT_8000_SS 2>/dev/null
fi

echo "  ✓ All port checks complete"

# Give processes time to fully terminate and release ports
echo "  Waiting for ports to be released..."
sleep 2

echo "✅ Ports cleaned up and ready!"
