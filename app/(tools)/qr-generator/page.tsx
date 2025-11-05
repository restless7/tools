'use client';

import { useState, useCallback } from 'react';
import QRCode from 'qrcode';
import { Download, Copy, QrCode, Home } from 'lucide-react';
import Link from 'next/link';

export default function QRGeneratorPage() {
  const [input, setInput] = useState('');
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generateQR = useCallback(async () => {
    if (!input.trim()) {
      setError('Please enter some text or URL');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const qrDataURL = await QRCode.toDataURL(input.trim(), {
        width: 300,
        margin: 2,
        color: {
          dark: '#000000',
          light: '#FFFFFF'
        }
      });
      setQrCode(qrDataURL);
    } catch (err) {
      setError('Failed to generate QR code');
      console.error('QR Code generation error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [input]);

  const downloadQR = () => {
    if (!qrCode) return;

    const link = document.createElement('a');
    link.download = 'qr-code.png';
    link.href = qrCode;
    link.click();
  };

  const copyToClipboard = async () => {
    if (!qrCode) return;

    try {
      const response = await fetch(qrCode);
      const blob = await response.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob })
      ]);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
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
        <span className="text-gray-900 font-medium">QR Code Generator</span>
      </nav>

      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-purple-600 text-white mb-4">
          <QrCode size={32} />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          QR Code Generator
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Generate QR codes instantly from any URL or text. Perfect for sharing links, 
          contact information, or any text content.
        </p>
      </div>

      {/* Generator Form */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Input Section */}
          <div className="space-y-6">
            <div>
              <label htmlFor="qr-input" className="block text-sm font-medium text-gray-700 mb-2">
                Enter text or URL
              </label>
              <textarea
                id="qr-input"
                className="w-full min-h-[120px] px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                placeholder="https://example.com or any text..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    generateQR();
                  }
                }}
              />
            </div>

            <button
              onClick={generateQR}
              disabled={isLoading || !input.trim()}
              className="w-full bg-gradient-to-br from-blue-500 to-purple-600 text-white font-medium py-3 px-6 rounded-lg hover:from-blue-600 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              {isLoading ? 'Generating...' : 'Generate QR Code'}
            </button>

            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}
          </div>

          {/* Output Section */}
          <div className="flex flex-col items-center justify-center space-y-6">
            {qrCode ? (
              <>
                <div className="p-4 bg-white border border-gray-200 rounded-lg shadow-sm">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={qrCode} alt="Generated QR Code" className="w-64 h-64" />
                </div>
                
                <div className="flex space-x-3">
                  <button
                    onClick={downloadQR}
                    className="flex items-center px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-colors"
                  >
                    <Download size={16} className="mr-2" />
                    Download
                  </button>
                  
                  <button
                    onClick={copyToClipboard}
                    className="flex items-center px-4 py-2 bg-gray-600 text-white font-medium rounded-lg hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
                  >
                    <Copy size={16} className="mr-2" />
                    Copy
                  </button>
                </div>
              </>
            ) : (
              <div className="w-64 h-64 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <QrCode size={48} className="mx-auto text-gray-400 mb-4" />
                  <p className="text-gray-500">Your QR code will appear here</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Usage Tips */}
      <div className="mt-12 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-medium text-blue-900 mb-4">Usage Tips</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-800">
          <div>
            <h4 className="font-medium mb-2">For URLs:</h4>
            <p>Include the full URL including https:// for best results</p>
          </div>
          <div>
            <h4 className="font-medium mb-2">For Text:</h4>
            <p>Any text content will work - contacts, messages, or data</p>
          </div>
          <div>
            <h4 className="font-medium mb-2">Keyboard Shortcut:</h4>
            <p>Press Cmd/Ctrl + Enter to generate quickly</p>
          </div>
          <div>
            <h4 className="font-medium mb-2">Quality:</h4>
            <p>Generated QR codes are high resolution and print-ready</p>
          </div>
        </div>
      </div>
    </div>
  );
}