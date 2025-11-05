'use client';

import { useState, useEffect } from 'react';
import { Database, Users, FileText, Home, TrendingUp, Filter, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import { LoadingSpinner } from '@/components/LoadingSpinner';

interface StagingSummary {
  total_students: number;
  total_documents: number;
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
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <Users size={20} className="text-blue-600" />
              <TrendingUp size={16} className="text-green-500" />
            </div>
            <p className="text-sm text-gray-600 font-medium">Total Students</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {summary.total_students.toLocaleString()}
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <FileText size={20} className="text-green-600" />
            </div>
            <p className="text-sm text-gray-600 font-medium">Total Documents</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {summary.total_documents.toLocaleString()}
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <CheckCircle2 size={20} className="text-purple-600" />
            </div>
            <p className="text-sm text-gray-600 font-medium">Enriched Records</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {summary.sources.find(s => s.source === 'directory+csv')?.count || 0}
            </p>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <Clock size={20} className="text-orange-600" />
            </div>
            <p className="text-sm text-gray-600 font-medium">Execution Time</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
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
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
          >
            <option value="">All Programs</option>
            {summary?.programs.map((prog) => (
              <option key={prog.program} value={prog.program}>
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
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
          >
            <option value="">All Sources</option>
            {summary?.sources.map((src) => (
              <option key={src.source} value={src.source}>
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
