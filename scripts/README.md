# Tools Package Scripts

## ensure-db.sh
Checks if PostgreSQL 16 is running. If not, starts it automatically.
Called before `npm run dev` to ensure database connectivity.

## cleanup-ports.sh
Cleans up ports 3005 (frontend) and 8000 (backend) before starting dev servers.
Prevents "port already in use" errors.

## Usage
These scripts run automatically via `npm run dev` in the correct order:
1. `ensure-db.sh` - Start PostgreSQL if needed
2. `cleanup-ports.sh` - Clean up ports
3. Start frontend and backend servers
