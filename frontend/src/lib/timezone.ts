// Schedule times are stored and executed in UTC (the Celery beat scheduler and the
// topic_schedule_times table both work in UTC — see src/truebrief/ledger/alarm_schedule.py).
// Only the UI translates: the user picks and reads times in their own zone, and we
// convert at the edge. Nothing server-side is timezone-aware, deliberately.

const STORAGE_KEY = 'tb_timezone';

/** The user's chosen zone, or the browser's own if they've never picked one. */
export function getTimezone(): string {
  if (typeof window !== 'undefined') {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) return saved;
  }
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

export function setTimezone(tz: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, tz);
  // Same-tab listeners: the native 'storage' event only fires in OTHER tabs.
  window.dispatchEvent(new Event('tb-timezone-change'));
}

/** Zones the browser knows about, for the settings picker. */
export function listTimezones(): string[] {
  try {
    const supported = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] })
      .supportedValuesOf;
    if (supported) return supported('timeZone');
  } catch {
    /* fall through */
  }
  return ['UTC', getTimezone()].filter((v, i, a) => a.indexOf(v) === i);
}

/**
 * Offset of `tz` from UTC in minutes at `when` (positive = ahead of UTC).
 * Derived from formatted parts rather than a fixed table, so DST is handled by the
 * platform instead of by us.
 */
function offsetMinutes(tz: string, when: Date): number {
  const fmt = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const p: Record<string, string> = {};
  for (const { type, value } of fmt.formatToParts(when)) p[type] = value;
  // Date.UTC on the wall-clock reading in `tz` minus the real instant = that zone's offset.
  const asUTC = Date.UTC(
    Number(p.year), Number(p.month) - 1, Number(p.day),
    Number(p.hour === '24' ? '00' : p.hour), Number(p.minute), Number(p.second),
  );
  return Math.round((asUTC - when.getTime()) / 60000);
}

function wrap(total: number): { hour: number; minute: number } {
  const m = ((total % 1440) + 1440) % 1440;
  return { hour: Math.floor(m / 60), minute: m % 60 };
}

/** UTC (hour, minute) as it should be displayed in `tz`. */
export function utcToLocal(hour: number, minute: number, tz = getTimezone()) {
  return wrap(hour * 60 + minute + offsetMinutes(tz, new Date()));
}

/** A (hour, minute) the user picked in `tz`, converted to the UTC pair we store. */
export function localToUtc(hour: number, minute: number, tz = getTimezone()) {
  return wrap(hour * 60 + minute - offsetMinutes(tz, new Date()));
}

/** "GMT+3" style label for the current zone, for UI headings. */
export function tzShortLabel(tz = getTimezone()): string {
  const off = offsetMinutes(tz, new Date());
  const sign = off >= 0 ? '+' : '-';
  const abs = Math.abs(off);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  return `GMT${sign}${h}${m ? `:${String(m).padStart(2, '0')}` : ''}`;
}

export function fmtHM(hour: number, minute: number): string {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}
