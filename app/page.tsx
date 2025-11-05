'use client';

import { QrCode, FileSpreadsheet, Database, Wrench } from 'lucide-react';
import { ToolCard } from '@/components/ToolCard';
import { api } from '@/lib/api';
import { useEffect, useState } from 'react';

interface ServiceStatus {
  excel_converter: string;
  ice_ingestion: string;
}

export default function Dashboard() {
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkServices = async () => {
      try {
        const health = await api.checkHealth();
        setServiceStatus(health.services);
      } catch (error) {
        console.error('Failed to check service health:', error);
      } finally {
        setIsLoading(false);
      }
    };

    checkServices();
  }, []);

  const tools = [
    {
      title: 'QR Code Generator',
      description: 'Generate QR codes from URLs, text, and other data formats instantly.',
      href: '/qr-generator',
      icon: QrCode,
      status: 'active' as const,
      gradient: 'from-blue-500 to-purple-600'
    },
    {
      title: 'Excel to CSV Converter',
      description: 'Convert multi-sheet Excel files to individual CSV files with advanced processing.',
      href: '/excel-converter',
      icon: FileSpreadsheet,
      status: serviceStatus?.excel_converter === 'active' ? 'active' as const : 'maintenance' as const,
      gradient: 'from-green-500 to-emerald-600'
    },
    {
      title: 'ICE Database Ingestion',
      description: 'Process and ingest data from Google Drive into the ICE database system.',
      href: '/ice-database',
      icon: Database,
      status: serviceStatus?.ice_ingestion === 'active' ? 'active' as const : 'maintenance' as const,
      gradient: 'from-orange-500 to-red-600'
    }
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Enterprise Tools Platform
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto">
          Unified dashboard for QR generation, Excel processing, and data pipeline management. 
          Built for efficiency and scalability.
        </p>
      </div>

      {/* Service Status */}
      {!isLoading && (
        <div className="mb-8 p-4 bg-white rounded-lg border border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">System Status</h2>
            <div className="flex items-center space-x-4">
              <div className="flex items-center">
                <div className={`w-2 h-2 rounded-full mr-2 ${
                  serviceStatus?.excel_converter === 'active' ? 'bg-green-500' : 'bg-red-500'
                }`} />
                <span className="text-sm text-gray-600">Excel Converter</span>
              </div>
              <div className="flex items-center">
                <div className={`w-2 h-2 rounded-full mr-2 ${
                  serviceStatus?.ice_ingestion === 'active' ? 'bg-green-500' : 'bg-red-500'
                }`} />
                <span className="text-sm text-gray-600">ICE Ingestion</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tools Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tools.map((tool) => (
          <ToolCard
            key={tool.title}
            title={tool.title}
            description={tool.description}
            href={tool.href}
            icon={tool.icon}
            status={tool.status}
            gradient={tool.gradient}
          />
        ))}
      </div>

      {/* Quick Actions */}
      <div className="mt-12 bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <button className="flex items-center justify-center px-4 py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors">
            <Wrench size={16} className="mr-2" />
            System Health
          </button>
          <button className="flex items-center justify-center px-4 py-2 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition-colors">
            <FileSpreadsheet size={16} className="mr-2" />
            Quick Convert
          </button>
          <button className="flex items-center justify-center px-4 py-2 bg-orange-50 text-orange-700 rounded-lg hover:bg-orange-100 transition-colors">
            <Database size={16} className="mr-2" />
            Run Pipeline
          </button>
          <button className="flex items-center justify-center px-4 py-2 bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition-colors">
            <QrCode size={16} className="mr-2" />
            Generate QR
          </button>
        </div>
      </div>
    </div>
  );
}
