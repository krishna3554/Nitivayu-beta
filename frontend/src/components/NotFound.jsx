import React from 'react';
import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="mx-auto w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center mb-4">
          <Compass className="w-6 h-6" />
        </div>
        <p className="text-sm font-bold text-indigo-600 uppercase tracking-widest mb-2">404</p>
        <h1 className="text-2xl font-bold text-zinc-900 mb-2">Page not found</h1>
        <p className="text-sm text-zinc-500 mb-6">The page you are looking for does not exist or may have been moved.</p>
        <Link to="/" className="inline-flex items-center px-4 py-2 text-sm font-medium bg-zinc-900 text-white rounded-lg hover:bg-zinc-800 transition-colors">
          Back to home
        </Link>
      </div>
    </div>
  );
}
