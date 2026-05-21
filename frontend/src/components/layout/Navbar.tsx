'use client';

import Link from 'next/link';
import { Menu, X, Zap, Sun, Moon, Monitor } from 'lucide-react';
import { useState } from 'react';
import { useTheme } from 'next-themes';
import { useUser, UserButton } from '@clerk/nextjs';

const NAV_LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/history',   label: 'History' },
  { href: '/settings',  label: 'Settings' },
];

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const cycle = () => {
    if (theme === 'system') setTheme('light');
    else if (theme === 'light') setTheme('dark');
    else setTheme('system');
  };
  const Icon = theme === 'light' ? Sun : theme === 'dark' ? Moon : Monitor;
  return (
    <button
      onClick={cycle}
      aria-label="Toggle theme"
      className="p-2 rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text)] transition-colors"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { isSignedIn, isLoaded } = useUser();

  return (
    <nav className="border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-md sticky top-0 z-50 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group shrink-0">
            <div className="bg-[var(--color-brand)] p-1.5 rounded-lg group-hover:bg-[var(--color-brand-dark)] transition-colors">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-base font-bold text-[var(--color-text)]">TrueBrief</span>
          </Link>

          {/* Desktop nav — only show when signed in */}
          {isLoaded && isSignedIn && (
            <div className="hidden md:flex items-center gap-1">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="px-3 py-2 rounded-lg text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-overlay)] transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          )}

          {/* Right side */}
          <div className="flex items-center gap-2">
            <ThemeToggle />

            {isLoaded && !isSignedIn && (
              <>
                <Link
                  href="/sign-in"
                  className="hidden sm:block text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors px-3 py-2"
                >
                  Sign in
                </Link>
                <Link
                  href="/sign-up"
                  className="hidden sm:inline-flex bg-[var(--color-brand)] text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-[var(--color-brand-dark)] transition-all shadow-sm"
                >
                  Start Free
                </Link>
              </>
            )}

            {isLoaded && isSignedIn && (
              <UserButton
                appearance={{
                  elements: { avatarBox: 'h-8 w-8' },
                }}
              />
            )}

            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMenuOpen((o) => !o)}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              className="md:hidden p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] transition-colors"
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="md:hidden border-t border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 flex flex-col gap-1">
          {isLoaded && isSignedIn && NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMenuOpen(false)}
              className="px-3 py-3 rounded-xl text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text)] transition-colors"
            >
              {link.label}
            </Link>
          ))}
          {isLoaded && !isSignedIn && (
            <>
              <Link
                href="/sign-in"
                onClick={() => setMenuOpen(false)}
                className="px-3 py-3 rounded-xl text-sm font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/sign-up"
                onClick={() => setMenuOpen(false)}
                className="mt-1 flex items-center justify-center bg-[var(--color-brand)] text-white px-4 py-3 rounded-xl text-sm font-semibold hover:bg-[var(--color-brand-dark)] transition-all"
              >
                Start Free
              </Link>
            </>
          )}
        </div>
      )}
    </nav>
  );
}
