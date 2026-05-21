"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface BriefContentProps {
  content: string;
}

export default function BriefContent({ content }: BriefContentProps) {
  return (
    <div className="max-w-[65ch] mx-auto">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h2 className="text-2xl font-bold text-[var(--color-text)] mt-8 mb-3 tracking-tight">
              {children}
            </h2>
          ),
          h2: ({ children }) => (
            <h3 className="text-xl font-semibold text-[var(--color-text)] mt-6 mb-2">
              {children}
            </h3>
          ),
          h3: ({ children }) => (
            <h4 className="text-base font-semibold text-[var(--color-text)] mt-4 mb-2">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="text-[var(--color-text-secondary)] leading-relaxed mb-4">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-inside space-y-2 mb-4 text-[var(--color-text-secondary)] ml-2">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside space-y-2 mb-4 text-[var(--color-text-secondary)] ml-2">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--color-brand)] underline underline-offset-4 font-medium hover:text-[var(--color-brand-dark)] transition-colors"
            >
              {children}
            </a>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-[var(--color-text)]">{children}</strong>
          ),
          hr: () => <hr className="border-[var(--color-border)] my-8" />,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-[var(--color-brand-subtle)] pl-4 py-1 my-6 italic text-[var(--color-text-secondary)] bg-[var(--color-surface-overlay)] rounded-r-xl">
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code className="bg-[var(--color-surface-overlay)] text-[var(--color-text)] px-1.5 py-0.5 rounded font-mono text-sm">
              {children}
            </code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
