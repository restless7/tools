// API Client for Tools Platform Backend

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ConversionResult {
  success: boolean;
  filename: string;
  sheets_processed: number;
  files_created: string[];
  message: string;
  processing_time: number;
}

export interface ICEIngestionResult {
  success: boolean;
  files_processed: number;
  total_rows: number;
  message: string;
  processing_time: number;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  services: {
    excel_converter: string;
    ice_ingestion: string;
  };
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error: ${response.status} - ${errorText}`);
    }

    return response.json();
  }

  // Health check
  async checkHealth(): Promise<HealthStatus> {
    return this.request<HealthStatus>('/health');
  }

  // Excel conversion
  async convertExcelToCSV(file: File): Promise<ConversionResult> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/excel/convert`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Conversion failed: ${response.status} - ${errorText}`);
    }

    return response.json();
  }

  // Get Excel sheet names
  async getExcelSheets(filename: string): Promise<{
    filename: string;
    sheets: string[];
    sheet_count: number;
  }> {
    return this.request(`/excel/sheets/${encodeURIComponent(filename)}`);
  }

  // Download converted file
  async downloadFile(filename: string): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/download/${encodeURIComponent(filename)}`);
    
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }

    return response.blob();
  }

  // ICE database ingestion
  async triggerICEIngestion(options: {
    folder_id?: string;
    force_reprocess?: boolean;
  } = {}): Promise<ICEIngestionResult> {
    return this.request<ICEIngestionResult>('/ice/ingest', {
      method: 'POST',
      body: JSON.stringify(options),
    });
  }

  // Cleanup temporary files
  async cleanup(): Promise<{
    message: string;
    upload_files_removed: number;
    output_files_removed: number;
  }> {
    return this.request('/cleanup', {
      method: 'DELETE',
    });
  }
}

export const api = new ApiClient();