# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Architecture Overview

The PlanMaestro Tools platform is a full-stack enterprise application with a hybrid Next.js/Python architecture:

- **Frontend**: Next.js 15 with App Router, TypeScript, TailwindCSS
- **Backend**: Python FastAPI for data processing and file operations
- **Integration**: RESTful API communication between frontend and backend
- **Deployment**: Docker containerized with standalone Next.js output

### Key Architectural Patterns

- **Monorepo Structure**: Part of the planmaestro-ecosystem with package-based organization
- **Hybrid Stack**: Next.js handles UI/routing, Python handles data processing/file operations
- **Service Communication**: HTTP API calls from Next.js to FastAPI backend
- **File Processing Pipeline**: Temporary storage with automatic cleanup for Excel/CSV operations
- **ICE Database Integration**: External system integration via mounted credentials and environment

## Development Commands

### Unified Development (Recommended)
```bash
# Start both frontend and backend simultaneously
npm run dev

# Access points:
# Frontend: http://localhost:3005
# API Docs: http://localhost:8000/docs
```

### Frontend Development (Standalone)
```bash
# Start Next.js development server only (port 3005)
npm run dev:frontend

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

### Backend Development (Standalone)
```bash
# Install Python dependencies
npm run python:install

# Start FastAPI development server (port 8000)
npm run dev:backend
# or
npm run python:dev

# Direct uvicorn command
cd api/python && uvicorn main:app --reload --port 8000
```

### Docker Operations
```bash
# Build and run entire stack
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f [frontend|backend]

# Stop services
docker-compose down
```

## Project Structure & Import Patterns

### Frontend Architecture (Next.js App Router)
```
app/
├── (tools)/                 # Route groups for tools
│   ├── qr-generator/        # QR generation tool
│   ├── excel-converter/     # Excel to CSV converter
│   └── ice-database/        # ICE database ingestion
├── components/              # Shared UI components
│   ├── ToolCard.tsx         # Dashboard tool cards
│   └── LoadingSpinner.tsx   # Loading states
├── lib/                     # Utilities and API client
│   ├── api.ts              # FastAPI client functions
│   └── utils.ts            # General utilities
├── globals.css             # TailwindCSS imports (only in layout.tsx)
├── layout.tsx              # Root layout with header/navigation
└── page.tsx                # Dashboard with service health checks
```

### Backend Architecture (Python FastAPI)
```
api/python/
├── main.py                 # FastAPI app with CORS, file processing endpoints
├── ice_ingestion.py        # ICE database pipeline integration
└── requirements.txt        # Python dependencies
```

### Import Configuration
- **TypeScript Path Alias**: `@/*` maps to project root
- **Correct Import Examples**:
  - `import { ToolCard } from '@/components/ToolCard'`
  - `import { api } from '@/lib/api'`

## Configuration Details

### Next.js Configuration (next.config.ts)
- **Output**: `standalone` for Docker deployment
- **File Tracing**: Configured for monorepo structure
- **Environment**: `NEXT_PUBLIC_API_URL` for backend communication

### TailwindCSS Configuration
- **Version**: v3 (stable)
- **Content Paths**: `./app/**/*.{js,ts,jsx,tsx,mdx}`
- **PostCSS**: Configured with autoprefixer
- **Import Pattern**: Only in `app/globals.css`, imported once in `app/layout.tsx`

### TypeScript Configuration
- **Strict Mode**: Enabled
- **Path Mapping**: `@/*` alias for clean imports
- **Target**: ES2017 for broad compatibility
- **Incremental**: Enabled for faster builds

### Python Backend Configuration
- **CORS**: Configured for localhost:3004 and localhost:3000
- **File Limits**: 50MB upload limit
- **Temporary Storage**: `/tmp/tools_uploads` and `/tmp/tools_output`
- **Cleanup**: Automatic temporary file cleanup after processing

## Service Integration

### ICE Database Integration
The platform integrates with an external ICE database system:

- **Credentials**: Mounted from `/home/sebastiangarcia/ICE-DATABASE/`
- **Environment**: `.env` file with database connection details
- **Pipeline**: Automated Google Drive to PostgreSQL ingestion
- **Dependencies**: Google API client, pydrive2, psycopg2

### API Communication Pattern
Frontend communicates with backend via:
- **Health Checks**: `GET /health` for service status
- **File Processing**: `POST /excel/convert` for Excel to CSV conversion
- **Database Operations**: `POST /ice/ingest` for pipeline triggers
- **File Downloads**: `GET /download/{filename}` for processed files

## Development Patterns

### Error Handling
- **Frontend**: Error boundaries and user feedback messages
- **Backend**: HTTPException with detailed error messages
- **Logging**: Structured logging with different levels (INFO, ERROR)

### File Processing Workflow
1. File upload to `/tmp/tools_uploads`
2. Processing with pandas/openpyxl
3. Output to `/tmp/tools_output`
4. Automatic cleanup of temporary files
5. Download links for processed files

### Service Health Monitoring
- Dashboard displays real-time service status
- Health endpoint checks Excel converter and ICE ingestion services
- Color-coded status indicators (green=active, red=maintenance)

## Environment Requirements

### Development Prerequisites
- Node.js 18+ and npm
- Python 3.9+
- PostgreSQL (for ICE database features)
- Google Cloud Service Account (for ICE features)

### Environment Variables
```bash
# Next.js Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Python Backend (api/python/.env)
# Copy from /home/sebastiangarcia/ICE-DATABASE/.env
```

### External Dependencies
- ICE Database system at `/home/sebastiangarcia/ICE-DATABASE/`
- Google Drive API credentials for automated ingestion
- PostgreSQL database for data persistence

## Testing & Quality

### Available Scripts
- `npm run lint` - ESLint with Next.js TypeScript rules
- `npm run build` - Production build validation
- Backend testing through `/docs` endpoint for API exploration

### Code Quality Tools
- ESLint with Next.js core-web-vitals and TypeScript rules
- TypeScript strict mode for type safety
- TailwindCSS for consistent styling patterns