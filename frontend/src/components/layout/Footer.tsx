import { Zap } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="bg-slate-50 border-t mt-auto">
      <div className="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-indigo-600" />
            <span className="text-lg font-bold text-slate-900">TrueBrief</span>
          </div>
          <p className="text-slate-500 text-sm">
            © {new Date().getFullYear()} TrueBrief Intelligence. All rights reserved.
          </p>
          <div className="flex gap-6">
            <a href="#" className="text-sm text-slate-500 hover:text-indigo-600 transition-colors">Privacy</a>
            <a href="#" className="text-sm text-slate-500 hover:text-indigo-600 transition-colors">Terms</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
