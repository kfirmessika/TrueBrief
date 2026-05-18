'use client';

import Link from 'next/link';
import { Menu, X, Zap } from 'lucide-react';
import { useState } from 'react';

const NAV_LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/history', label: 'History' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/settings', label: 'Settings' },
];

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="border-b bg-white/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div className="bg-indigo-600 p-1.5 rounded-lg group-hover:bg-indigo-700 transition-colors">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-violet-600">
              TrueBrief
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm font-medium text-slate-600 hover:text-indigo-600 transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <Link
              href="/dashboard"
              className="hidden sm:inline-flex bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-all shadow-sm shadow-indigo-200"
            >
              Get Started
            </Link>

            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMenuOpen((o) => !o)}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              className="md:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100 transition-colors"
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="md:hidden border-t border-slate-100 bg-white px-4 py-4 flex flex-col gap-1">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className="px-3 py-3 rounded-xl text-sm font-semibold text-slate-700 hover:bg-slate-50 hover:text-indigo-600 transition-colors"
            >
              {link.label}
            </Link>
          ))}
          <Link
            href="/dashboard"
            onClick={() => setMenuOpen(false)}
            className="mt-2 flex items-center justify-center bg-indigo-600 text-white px-4 py-3 rounded-xl text-sm font-bold hover:bg-indigo-700 transition-all"
          >
            Get Started
          </Link>
        </div>
      )}
    </nav>
  );
}
