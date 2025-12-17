#!/bin/bash
# Ensure PostgreSQL is running before starting tools

if ! pg_lsclusters | grep -q "16 main.*online"; then
    echo "🔄 Starting PostgreSQL 16..."
    sudo pg_ctlcluster 16 main start
    sleep 2
fi

if PGPASSWORD=224207bB psql -h localhost -U postgres -d leads_project -c "SELECT 1" &>/dev/null; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL connection failed"
    exit 1
fi
