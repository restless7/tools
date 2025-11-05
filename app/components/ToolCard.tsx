'use client';

import Link from 'next/link';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToolCardProps {
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
  status?: 'active' | 'coming-soon' | 'maintenance';
  gradient?: string;
}

export function ToolCard({ 
  title, 
  description, 
  href, 
  icon: Icon,
  status = 'active',
  gradient = 'from-blue-500 to-purple-600'
}: ToolCardProps) {
  const isDisabled = status !== 'active';

  const CardContent = (
    <div className={cn(
      "relative overflow-hidden rounded-xl border border-gray-200 bg-white p-6 transition-all duration-300",
      "hover:shadow-lg hover:scale-[1.02]",
      isDisabled && "opacity-60 cursor-not-allowed"
    )}>
      {/* Gradient background */}
      <div className={cn(
        "absolute inset-0 bg-gradient-to-br opacity-5",
        gradient
      )} />
      
      {/* Icon */}
      <div className={cn(
        "relative z-10 mb-4 inline-flex h-12 w-12 items-center justify-center rounded-lg bg-gradient-to-br text-white",
        gradient
      )}>
        <Icon size={24} />
      </div>
      
      {/* Content */}
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          {status !== 'active' && (
            <span className={cn(
              "px-2 py-1 text-xs font-medium rounded-full",
              status === 'coming-soon' && "bg-yellow-100 text-yellow-800",
              status === 'maintenance' && "bg-red-100 text-red-800"
            )}>
              {status === 'coming-soon' ? 'Coming Soon' : 'Maintenance'}
            </span>
          )}
        </div>
        
        <p className="text-sm text-gray-600 leading-relaxed">
          {description}
        </p>
        
        {status === 'active' && (
          <div className="mt-4 flex items-center text-sm font-medium text-blue-600">
            Open Tool
            <svg 
              className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </div>
        )}
      </div>
    </div>
  );

  if (isDisabled) {
    return <div className="group">{CardContent}</div>;
  }

  return (
    <Link href={href} className="group block">
      {CardContent}
    </Link>
  );
}