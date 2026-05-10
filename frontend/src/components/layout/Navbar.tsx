import Link from 'next/link';
import { Mail, Zap } from 'lucide-react';

export default function Navbar() {
  return (
    <nav className="border-b bg-white/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center gap-2">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="bg-indigo-600 p-1.5 rounded-lg group-hover:bg-indigo-700 transition-colors">
                <Zap className="h-5 w-5 text-white" />
              </div>
              <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-violet-600">
                TrueBrief
              </span>
            </Link>
          </div>
          
          <div className="hidden md:flex items-center gap-8">
            <Link href="/dashboard" className="text-sm font-medium text-slate-600 hover:text-indigo-600 transition-colors">
              Dashboard
            </Link>
            <Link href="/pricing" className="text-sm font-medium text-slate-600 hover:text-indigo-600 transition-colors">
              Pricing
            </Link>
          </div>

          <div className="flex items-center gap-4">
            <Link 
              href="/dashboard" 
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-all shadow-sm shadow-indigo-200"
            >
              Get Started
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
