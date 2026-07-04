'use client';

// Shared source chip — a favicon box that links straight to the source article
// ("go to source"). Inline-styled with design-system CSS variables (no Tailwind),
// so it matches the topic page and dashboard shells. Used in both places so the
// look is identical everywhere ("like it was before").

export interface Source {
  domain: string | null;
  url: string | null;
}

/** Drop empty and duplicate sources (same url, else same domain). */
export function dedupeSources(sources: Source[]): Source[] {
  const seen = new Set<string>();
  const out: Source[] = [];
  for (const s of sources) {
    const key = (s.url || s.domain || '').trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(s);
  }
  return out;
}

function hostOf(url: string | null): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

export function SourceChip({ domain, url }: Source) {
  const d = (domain ?? hostOf(url)) || '';
  if (!d && !url) return null;
  const favicon = d ? `https://www.google.com/s2/favicons?domain=${d}&sz=32` : null;
  const href = url ?? (d ? `https://${d}` : '#');
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      title={`Open source — ${d || href}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontSize: 11,
        color: 'var(--color-text-secondary)',
        textDecoration: 'none',
        border: '1px solid var(--color-border-secondary)',
        borderRadius: 6,
        padding: '2px 7px 2px 5px',
        background: 'var(--color-background-primary)',
        maxWidth: 180,
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        textOverflow: 'ellipsis',
      }}
    >
      {favicon && (
        <img
          src={favicon}
          alt=""
          width={12}
          height={12}
          style={{ borderRadius: 2, flexShrink: 0 }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = 'none';
          }}
        />
      )}
      {d || 'source'}
    </a>
  );
}
