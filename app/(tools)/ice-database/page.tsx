'use client';

import { useState, useEffect } from 'react';
import { Database, Users, FileText, Home, TrendingUp, Filter, CheckCircle2, Clock, AlertCircle, Trash2, AlertTriangle } from 'lucide-react';
import Link from 'next/link';
import { LoadingSpinner } from '@/components/LoadingSpinner';

interface StagingSummary {
  total_students: number;
  total_documents: number;
  total_leads: number;
  total_reference_files: number;
  programs: Array<{ program: string; count: number }>;
  sources: Array<{ source: string; count: number }>;
  latest_run: {
    id: number;
    run_date: string;
    total_students: number;
    total_documents: number;
    execution_time_seconds: number;
    status: string;
  } | null;
}

interface Student {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  program: string;
  source: string;
  document_count: number;
}

interface StudentsResponse {
  students: Student[];
  total: number;
  limit: number;
  offset: number;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ICEDatabasePage() {
  const [summary, setSummary] = useState<StagingSummary | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProgram, setSelectedProgram] = useState<string>('');
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(0);
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestionMessage, setIngestionMessage] = useState<string | null>(null);
  const [sourceDirectory, setSourceDirectory] = useState<string>('/home/sebastiangarcia/Downloads/data_ingestion/drive-download-20251105T055300Z-1-001');
  const [isCleaning, setIsCleaning] = useState(false);
  const [showCleanupConfirm, setShowCleanupConfirm] = useState(false);
  const itemsPerPage = 20;

  // Fetch summary data
  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/staging/summary`);
        if (!response.ok) throw new Error('Failed to fetch summary');
        const data = await response.json();
        setSummary(data);
      } catch (err) {
        console.error('Error fetching summary:', err);
        setError(err instanceof Error ? err.message : 'Failed to load data');
      }
    };

    fetchSummary();
  }, []);

  // Fetch students data
  useEffect(() => {
    const fetchStudents = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          limit: itemsPerPage.toString(),
          offset: (currentPage * itemsPerPage).toString(),
        });
        
        if (selectedProgram) params.append('program', selectedProgram);
        if (selectedSource) params.append('source', selectedSource);

        const response = await fetch(`${API_BASE_URL}/staging/students?${params}`);
        if (!response.ok) throw new Error('Failed to fetch students');
        
        const data: StudentsResponse = await response.json();
        setStudents(data.students);
      } catch (err) {
        console.error('Error fetching students:', err);
        setError(err instanceof Error ? err.message : 'Failed to load students');
      } finally {
        setLoading(false);
      }
    };

    fetchStudents();
  }, [selectedProgram, selectedSource, currentPage]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getSourceBadgeColor = (source: string) => {
    return source === 'directory+csv' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800';
  };

  const runIngestion = async () => {
    setIsIngesting(true);
    setError(null);
    setIngestionMessage(null);

    try {
      // Use V3 enhanced ingestion pipeline
      const response = await fetch(`${API_BASE_URL}/staging/trigger-v3-ingestion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_directory: sourceDirectory }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'V3 Ingestion failed');
      }

      const data = await response.json();
      setIngestionMessage(`${data.message} (${data.pipeline_version.toUpperCase()})` );
      
      // Refresh summary and students after ingestion
      const summaryResponse = await fetch(`${API_BASE_URL}/staging/summary`);
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        setSummary(summaryData);
      }

      // Refresh students list
      const studentsResponse = await fetch(`${API_BASE_URL}/staging/students?limit=${itemsPerPage}&offset=0`);
      if (studentsResponse.ok) {
        const studentsData = await studentsResponse.json();
        setStudents(studentsData.students);
      }
    } catch (err) {
      console.error('Ingestion error:', err);
      setError(err instanceof Error ? err.message : 'Failed to run ingestion');
    } finally {
      setIsIngesting(false);
    }
  };

  const cleanupStaging = async () => {
    setIsCleaning(true);
    setError(null);
    setIngestionMessage(null);

    try {
      const response = await fetch(`${API_BASE_URL}/staging/cleanup?confirm=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Cleanup failed');
      }

      const data = await response.json();
      setIngestionMessage(data.message);
      setShowCleanupConfirm(false);
      
      // Refresh summary and students after cleanup
      const summaryResponse = await fetch(`${API_BASE_URL}/staging/summary`);
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        setSummary(summaryData);
      }

      // Clear students list
      setStudents([]);
    } catch (err) {
      console.error('Cleanup error:', err);
      setError(err instanceof Error ? err.message : 'Failed to cleanup staging');
    } finally {
      setIsCleaning(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center space-x-2 text-sm text-gray-500 mb-8">
        <Link href="/" className="hover:text-gray-700 flex items-center">
          <Home size={16} className="mr-1" />
          Dashboard
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">ICE Data Staging</span>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center mb-4">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-red-600 text-white mr-4">
            <Database size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              ICE Data Staging Dashboard
            </h1>
            <p className="text-gray-600 mt-1">
              Review and validate ingested data before production migration
            </p>
          </div>
        </div>
      </div>

      {/* Ingestion Controls */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Run Ingestion Pipeline</h2>
        <div className="space-y-4">
          <div>
            <label htmlFor="source-dir" className="block text-sm font-medium text-gray-700 mb-2">
              Source Directory
            </label>
            <input
              id="source-dir"
              type="text"
              value={sourceDirectory}
              onChange={(e) => setSourceDirectory(e.target.value)}
              disabled={isIngesting}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-orange-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              placeholder="/path/to/data/directory"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              onClick={runIngestion}
              disabled={isIngesting || isCleaning}
              className="bg-gradient-to-br from-orange-500 to-red-600 text-white font-medium py-3 px-6 rounded-lg hover:from-orange-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2"
            >
              {isIngesting ? (
                <>
                  <LoadingSpinner size="sm" />
                  <span>Running V3 Ingestion...</span>
                </>
              ) : (
                <>
                  <Database size={18} />
                  <span>Run V3 Ingestion Pipeline</span>
                </>
              )}
            </button>
            
            <button
              onClick={() => setShowCleanupConfirm(true)}
              disabled={isIngesting || isCleaning}
              className="bg-gradient-to-br from-red-500 to-red-700 text-white font-medium py-3 px-6 rounded-lg hover:from-red-600 hover:to-red-800 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center gap-2"
            >
              <Trash2 size={18} />
              <span>Clean & Reset</span>
            </button>
          </div>
        </div>
      </div>

      {/* Cleanup Confirmation Modal */}
      {showCleanupConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="ml-4 text-lg font-semibold text-gray-900">Clean Staging Environment?</h3>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              This will permanently DELETE:
            </p>
            <ul className="text-sm text-gray-600 mb-6 space-y-1 list-disc list-inside">
              <li>All database records (students, documents, leads)</li>
              <li>All staged documents in /ice-data-staging/documents</li>
              <li>All extracted CSV files</li>
              <li>All reports and logs</li>
            </ul>
            <p className="text-sm text-gray-700 mb-6 font-medium">
              This action CANNOT be undone. You can run a fresh V3 ingestion after cleanup.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowCleanupConfirm(false)}
                disabled={isCleaning}
                className="flex-1 bg-gray-200 text-gray-900 font-medium py-2 px-4 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
              <button
                onClick={cleanupStaging}
                disabled={isCleaning}
                className="flex-1 bg-red-600 text-white font-medium py-2 px-4 rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isCleaning ? (
                  <>
                    <LoadingSpinner size="sm" />
                    <span>Cleaning...</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={16} />
                    <span>Yes, Clean All</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Success Message */}
      {ingestionMessage && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
          <div className="flex items-center">
            <CheckCircle2 size={20} className="text-green-600 mr-3" />
            <p className="text-sm text-green-600 font-medium">{ingestionMessage}</p>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <div className="flex items-center">
            <AlertCircle size={20} className="text-red-600 mr-3" />
            <p className="text-sm text-red-600">{error}</p>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <Users size={18} className="text-blue-600" />
            </div>
            <p className="text-xs text-gray-600 font-medium">Total Students</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {summary.total_students.toLocaleString()}
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <FileText size={18} className="text-green-600" />
            </div>
            <p className="text-xs text-gray-600 font-medium">Total Documents</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {summary.total_documents.toLocaleString()}
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <Users size={18} className="text-purple-600" />
            </div>
            <p className="text-xs text-gray-600 font-medium">Total Leads</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {summary.total_leads.toLocaleString()}
            </p>
            <p className="text-xs text-purple-600 mt-1 font-medium">V3 Enhanced</p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <FileText size={18} className="text-indigo-600" />
            </div>
            <p className="text-xs text-gray-600 font-medium">Reference Files</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {summary.total_reference_files.toLocaleString()}
            </p>
            <p className="text-xs text-indigo-600 mt-1 font-medium">V3 Enhanced</p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <CheckCircle2 size={18} className="text-teal-600" />
            </div>
            <p className="text-xs text-gray-600 font-medium">Enriched Records</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {summary.sources.find(s => s.source === 'directory+csv')?.count || 0}
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <Clock size={18} className="text-orange-600" />
            </div>
            <p className="text-xs text-gray-600 font-medium">Execution Time</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {summary.latest_run?.execution_time_seconds.toFixed(1)}s
            </p>
          </div>
        </div>
      )}

      {/* Latest Run Status */}
      {summary?.latest_run && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-8">
          <div className="flex items-center">
            <CheckCircle2 size={20} className="text-green-600 mr-3" />
            <div className="flex-1">
              <p className="text-sm font-medium text-green-900">
                Latest Ingestion Run #{summary.latest_run.id} - {summary.latest_run.status}
              </p>
              <p className="text-xs text-green-700 mt-1">
                Completed on {formatDate(summary.latest_run.run_date)} • 
                Processed {summary.latest_run.total_students} students and {summary.latest_run.total_documents} documents
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Programs Breakdown */}
      {summary && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <TrendingUp size={20} className="mr-2 text-orange-600" />
            Program Distribution
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {summary.programs.map((prog) => (
              <div key={prog.program} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer">
                <p className="text-sm text-gray-600 font-medium mb-1">{prog.program}</p>
                <p className="text-2xl font-bold text-gray-900">{prog.count}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {((prog.count / summary.total_students) * 100).toFixed(1)}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 mb-6">
        <div className="flex items-center gap-4">
          <Filter size={20} className="text-gray-600" />
          <select
            value={selectedProgram}
            onChange={(e) => {
              setSelectedProgram(e.target.value);
              setCurrentPage(0);
            }}
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-orange-500 font-medium"
          >
            <option value="" className="text-gray-900">All Programs</option>
            {summary?.programs.map((prog) => (
              <option key={prog.program} value={prog.program} className="text-gray-900">
                {prog.program} ({prog.count})
              </option>
            ))}
          </select>

          <select
            value={selectedSource}
            onChange={(e) => {
              setSelectedSource(e.target.value);
              setCurrentPage(0);
            }}
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-orange-500 font-medium"
          >
            <option value="" className="text-gray-900">All Sources</option>
            {summary?.sources.map((src) => (
              <option key={src.source} value={src.source} className="text-gray-900">
                {src.source === 'directory+csv' ? 'Enriched' : 'Directory Only'} ({src.count})
              </option>
            ))}
          </select>

          {(selectedProgram || selectedSource) && (
            <button
              onClick={() => {
                setSelectedProgram('');
                setSelectedSource('');
                setCurrentPage(0);
              }}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 font-medium"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Students Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Students Registry</h2>
          <p className="text-sm text-gray-600 mt-1">
            {students.length} students shown
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        ) : students.length === 0 ? (
          <div className="text-center py-12">
            <Users size={48} className="mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No students found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Program
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Contact
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Source
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Documents
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {students.map((student) => (
                  <tr key={student.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {student.full_name}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-700">{student.program}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-700">
                        {student.email && <div>{student.email}</div>}
                        {student.phone && <div className="text-gray-500">{student.phone}</div>}
                        {!student.email && !student.phone && (
                          <span className="text-gray-400 text-xs">No contact info</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getSourceBadgeColor(student.source)}`}>
                        {student.source === 'directory+csv' ? 'Enriched' : 'Basic'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {student.document_count} files
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!loading && students.length > 0 && (
          <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Showing {currentPage * itemsPerPage + 1} to {Math.min((currentPage + 1) * itemsPerPage, summary?.total_students || 0)} of {summary?.total_students || 0} students
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                disabled={currentPage === 0}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={(currentPage + 1) * itemsPerPage >= (summary?.total_students || 0)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* System Info Footer */}
      <div className="mt-8 bg-orange-50 border border-orange-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-orange-900 mb-3">System Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-orange-800">
          <div>
            <span className="font-medium">Staging Location:</span>
            <p className="text-xs mt-1">/home/sebastiangarcia/ice-data-staging</p>
          </div>
          <div>
            <span className="font-medium">Database:</span>
            <p className="text-xs mt-1">PostgreSQL staging tables</p>
          </div>
          <div>
            <span className="font-medium">Status:</span>
            <p className="text-xs mt-1 flex items-center">
              <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
              Ready for Review
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
