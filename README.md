# PlanMaestro Tools Platform

Enterprise-level tools platform integrating QR generation, Excel processing, and data pipeline management under one unified dashboard.

## 🚀 Features

### 1. QR Code Generator
- Generate QR codes from URLs, text, and other data formats
- High-resolution output suitable for print
- One-click download and copy functionality
- Keyboard shortcuts for efficiency

### 2. Excel to CSV Converter
- Convert multi-sheet Excel files to individual CSV files
- Support for both .xlsx and .xls formats
- Drag-and-drop file upload interface
- Batch download functionality
- Data integrity preservation during conversion

### 3. ICE Database Ingestion
- Automated pipeline for processing Google Drive Excel files
- Direct ingestion into PostgreSQL database
- Data validation and normalization
- Comprehensive ETL logging
- Force reprocess functionality

## 🏗️ Architecture

### Frontend (Next.js)
- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **Styling**: TailwindCSS v3 (stable)
- **UI Components**: Custom components with Lucide React icons
- **State Management**: React hooks (useState, useEffect)

### Backend (Python)
- **Framework**: FastAPI
- **Key Libraries**: pandas, openpyxl, psycopg2, google-api-python-client
- **Processing**: Excel conversion, Google Drive integration, PostgreSQL operations
- **API**: RESTful endpoints with automatic OpenAPI documentation

### Integration Layer
- **Communication**: REST API calls from Next.js to FastAPI
- **File Handling**: Temporary storage with automatic cleanup
- **Error Handling**: Comprehensive error boundaries and user feedback

## 🛠️ Development Setup

### Prerequisites
- Node.js 18+ and npm
- Python 3.9+
- PostgreSQL (for ICE database features)
- Google Cloud Service Account (for ICE database features)

### Installation

1. **Install Node.js dependencies**:
```bash
npm install --legacy-peer-deps
```

2. **Install Python dependencies**:
```bash
npm run python:install
```

3. **Environment Configuration**:
Create a `.env.local` file:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For ICE database functionality, configure the Python environment:
```bash
# Copy from /home/sebastiangarcia/ICE-DATABASE/.env
cp /home/sebastiangarcia/ICE-DATABASE/.env api/python/.env
cp -r /home/sebastiangarcia/ICE-DATABASE/credentials api/python/
```

### Running the Application

**Unified Development (Recommended)**:
```bash
npm run dev
```
This starts both the Python backend and Next.js frontend simultaneously.

**Or run services separately**:

1. **Start the Python backend** (Terminal 1):
```bash
npm run dev:backend
```

2. **Start the Next.js frontend** (Terminal 2):
```bash
npm run dev:frontend
```

**Access the application**:
- Frontend: http://localhost:3005
- Python API Documentation: http://localhost:8000/docs

## 📁 Project Structure

```
packages/tools/
├── app/                          # Next.js App Router
│   ├── (tools)/                  # Tool pages
│   │   ├── qr-generator/         # QR Generator tool
│   │   ├── excel-converter/      # Excel Converter tool
│   │   └── ice-database/         # ICE Database tool
│   ├── components/               # Shared UI components
│   ├── lib/                      # Utilities and API client
│   ├── globals.css               # Global styles
│   ├── layout.tsx                # Root layout
│   └── page.tsx                  # Dashboard page
├── api/
│   └── python/                   # FastAPI backend
│       ├── main.py               # FastAPI application
│       ├── ice_ingestion.py      # ICE pipeline integration
│       └── requirements.txt      # Python dependencies
├── package.json                  # Node.js configuration
├── tailwind.config.js            # Tailwind configuration
├── tsconfig.json                 # TypeScript configuration
└── README.md                     # This file
```

## 🔧 Configuration

### TailwindCSS Setup
- Version: v3 (stable)
- PostCSS config: `postcss.config.mjs`
- Path aliases: `@/*` points to project root

### TypeScript Configuration
- Path aliases configured for clean imports
- Strict mode enabled
- Next.js integration with proper types

### Python API Configuration
- CORS enabled for localhost development
- File upload limits: 50MB
- Automatic cleanup of temporary files
- Comprehensive error handling and logging

## 🔗 API Endpoints

### Health Check
- `GET /health` - System health and service status

### Excel Conversion
- `POST /excel/convert` - Convert Excel to CSV files
- `GET /excel/sheets/{filename}` - Get Excel sheet information
- `GET /download/{filename}` - Download converted CSV files

### ICE Database
- `POST /ice/ingest` - Trigger ICE ingestion pipeline

### Utility
- `DELETE /cleanup` - Clean temporary files

## 🚀 Deployment

### Next.js Frontend
```bash
npm run build
npm run start
```

### Python Backend
```bash
cd api/python
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker Setup
[Docker configuration to be added]

## 📊 Monitoring and Logging

- **Frontend**: Console logging for development, error boundaries for production
- **Backend**: Structured logging with different levels (INFO, ERROR)
- **Database**: ETL log table tracks all ingestion operations
- **File Processing**: Comprehensive operation tracking and cleanup

## 🤝 Contributing

1. Follow the existing code structure and naming conventions
2. Use TypeScript for all frontend code
3. Implement proper error handling and user feedback
4. Add appropriate logging for debugging
5. Test all API integrations thoroughly
6. Update documentation for new features

## 📄 License

This project is part of the PlanMaestro ecosystem and follows the organization's licensing terms.

## 🆘 Support

For issues related to:
- **QR Generator**: Frontend functionality and QR code generation
- **Excel Converter**: File processing and Python backend
- **ICE Database**: Database connections and Google Drive integration

Check the logs in the respective components and ensure all dependencies are properly installed.
