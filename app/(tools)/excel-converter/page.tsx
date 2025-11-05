'use client';

import { useState, useCallback } from 'react';
import { Upload, Download, FileSpreadsheet, Home, CheckCircle, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { api, ConversionResult } from '@/lib/api';
import { formatFileSize } from '@/lib/utils';
import { LoadingSpinner } from '@/components/LoadingSpinner';

export default function ExcelConverterPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isConverting, setIsConverting] = useState(false);
  const [result, setResult] = useState<ConversionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const excelFile = droppedFiles.find(f => 
      f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
    );

    if (excelFile) {
      setFile(excelFile);
      setResult(null);
      setError(null);
    } else {
      setError('Please drop an Excel file (.xlsx or .xls)');
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setResult(null);
      setError(null);
    }
  };

  const convertFile = async () => {
    if (!file) return;

    setIsConverting(true);
    setError(null);

    try {
      const conversionResult = await api.convertExcelToCSV(file);
      setResult(conversionResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Conversion failed');
    } finally {
      setIsConverting(false);
    }
  };

  const downloadFile = async (filename: string) => {
    try {
      const blob = await api.downloadFile(filename);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError('Failed to download file');
    }
  };

  const downloadAll = async () => {
    if (!result) return;
    
    for (const filename of result.files_created) {
      await downloadFile(filename);
      // Small delay between downloads
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center space-x-2 text-sm text-gray-500 mb-8">
        <Link href="/" className="hover:text-gray-700 flex items-center">
          <Home size={16} className="mr-1" />
          Dashboard
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">Excel to CSV Converter</span>
      </nav>

      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-green-500 to-emerald-600 text-white mb-4">
          <FileSpreadsheet size={32} />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          Excel to CSV Converter
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Convert multi-sheet Excel files to individual CSV files. Each sheet becomes 
          a separate CSV file with clean, structured data.
        </p>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 mb-8">
        <div
          className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
            dragActive
              ? 'border-green-400 bg-green-50'
              : 'border-gray-300 hover:border-green-400 hover:bg-gray-50'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <Upload size={48} className="mx-auto text-gray-400 mb-4" />
          
          {file ? (
            <div className="space-y-4">
              <div className="bg-gray-50 rounded-lg p-4 max-w-sm mx-auto">
                <div className="flex items-center space-x-3">
                  <FileSpreadsheet size={24} className="text-green-600" />
                  <div className="flex-1 text-left">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
              </div>
              
              <button
                onClick={convertFile}
                disabled={isConverting}
                className="bg-gradient-to-br from-green-500 to-emerald-600 text-white font-medium py-3 px-6 rounded-lg hover:from-green-600 hover:to-emerald-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                {isConverting ? (
                  <span className="flex items-center">
                    <LoadingSpinner size="sm" className="mr-2" />
                    Converting...
                  </span>
                ) : (
                  'Convert to CSV'
                )}
              </button>
              
              <button
                onClick={() => setFile(null)}
                className="ml-3 text-gray-500 hover:text-gray-700 text-sm font-medium"
              >
                Remove file
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Choose an Excel file
                </h3>
                <p className="text-gray-500 mb-4">
                  Drag and drop your Excel file here, or click to browse
                </p>
              </div>
              
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
              />
              
              <label
                htmlFor="file-upload"
                className="inline-flex items-center px-6 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer transition-colors"
              >
                <Upload size={16} className="mr-2" />
                Select File
              </label>
              
              <p className="text-xs text-gray-400 mt-2">
                Supports .xlsx and .xls files up to 50MB
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8">
          <div className="flex items-center">
            <AlertCircle size={20} className="text-red-600 mr-3" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
          <div className="flex items-center mb-6">
            <CheckCircle size={24} className="text-green-600 mr-3" />
            <div>
              <h3 className="text-lg font-medium text-gray-900">
                Conversion Completed Successfully!
              </h3>
              <p className="text-sm text-gray-500">
                Processed {result.sheets_processed} sheets in {result.processing_time.toFixed(2)}s
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Summary */}
            <div className="space-y-4">
              <h4 className="font-medium text-gray-900">Summary</h4>
              <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Original file:</span>
                  <span className="font-medium">{result.filename}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Sheets processed:</span>
                  <span className="font-medium">{result.sheets_processed}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">CSV files created:</span>
                  <span className="font-medium">{result.files_created.length}</span>
                </div>
              </div>
              
              <button
                onClick={downloadAll}
                className="w-full bg-green-600 text-white font-medium py-2 px-4 rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-colors"
              >
                <Download size={16} className="inline mr-2" />
                Download All CSV Files
              </button>
            </div>

            {/* File List */}
            <div className="space-y-4">
              <h4 className="font-medium text-gray-900">Generated Files</h4>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {result.files_created.map((filename, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                  >
                    <div className="flex items-center flex-1 min-w-0">
                      <FileSpreadsheet size={16} className="text-green-600 mr-2 flex-shrink-0" />
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {filename}
                      </span>
                    </div>
                    <button
                      onClick={() => downloadFile(filename)}
                      className="ml-3 flex-shrink-0 text-green-600 hover:text-green-700 text-xs font-medium"
                    >
                      Download
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Features */}
      <div className="mt-12 bg-green-50 border border-green-200 rounded-lg p-6">
        <h3 className="text-lg font-medium text-green-900 mb-4">Features</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-green-800">
          <div>
            <h4 className="font-medium mb-2">Multi-Sheet Processing:</h4>
            <p>Each Excel sheet becomes a separate CSV file automatically</p>
          </div>
          <div>
            <h4 className="font-medium mb-2">Data Integrity:</h4>
            <p>Preserves all data types and formatting during conversion</p>
          </div>
          <div>
            <h4 className="font-medium mb-2">Batch Download:</h4>
            <p>Download all CSV files at once or individually</p>
          </div>
          <div>
            <h4 className="font-medium mb-2">File Support:</h4>
            <p>Supports both .xlsx and legacy .xls formats</p>
          </div>
        </div>
      </div>
    </div>
  );
}