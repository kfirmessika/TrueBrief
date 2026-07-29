import { describe, it, expect } from 'vitest';
import { utcToLocal, localToUtc, fmtHM, tzShortLabel } from '@/lib/timezone';

// Schedule times are stored as UTC (hour, minute) pairs; only the UI translates.
//
// Absolute assertions here use Asia/Kolkata (UTC+5:30, no DST anywhere in the year) so
// they hold in January as well as July. Zones that observe DST are only asserted on
// properties that stay true across a transition — a test pinned to a summer offset
// passes today and fails in the autumn for no real reason.
describe('timezone conversion', () => {
  it('is a no-op for UTC', () => {
    expect(utcToLocal(9, 0, 'UTC')).toEqual({ hour: 9, minute: 0 });
    expect(localToUtc(9, 0, 'UTC')).toEqual({ hour: 9, minute: 0 });
  });

  it('applies a fractional offset without losing the minutes', () => {
    // 09:00 UTC + 5:30 = 14:30 — not 14:00, which is what whole-hour math would give.
    expect(utcToLocal(9, 0, 'Asia/Kolkata')).toEqual({ hour: 14, minute: 30 });
    expect(localToUtc(14, 30, 'Asia/Kolkata')).toEqual({ hour: 9, minute: 0 });
  });

  it('wraps forward past midnight instead of overflowing past 24h', () => {
    // 20:00 UTC + 5:30 = 25:30 -> 01:30 the next day.
    expect(utcToLocal(20, 0, 'Asia/Kolkata')).toEqual({ hour: 1, minute: 30 });
  });

  it('wraps backward past midnight instead of going negative', () => {
    // 02:00 local - 5:30 = -3:30 -> 20:30 the previous day.
    expect(localToUtc(2, 0, 'Asia/Kolkata')).toEqual({ hour: 20, minute: 30 });
  });

  it('round-trips every quarter-hour of the day', () => {
    for (let h = 0; h < 24; h++) {
      for (const m of [0, 15, 30, 45]) {
        const utc = localToUtc(h, m, 'Asia/Kolkata');
        expect(utcToLocal(utc.hour, utc.minute, 'Asia/Kolkata')).toEqual({ hour: h, minute: m });
      }
    }
  });

  it('shifts DST zones in the right direction year-round', () => {
    // Jerusalem is east of UTC and New York west of it in every season — only the
    // size of the offset moves, so direction is the only safe absolute claim.
    expect(tzShortLabel('Asia/Jerusalem').startsWith('GMT+')).toBe(true);
    expect(tzShortLabel('America/New_York').startsWith('GMT-')).toBe(true);
  });

  it('round-trips through a DST zone too', () => {
    for (const tz of ['Asia/Jerusalem', 'America/New_York', 'Australia/Adelaide']) {
      const utc = localToUtc(9, 30, tz);
      expect(utcToLocal(utc.hour, utc.minute, tz)).toEqual({ hour: 9, minute: 30 });
    }
  });

  it('labels a fractional offset with its minutes', () => {
    expect(tzShortLabel('UTC')).toBe('GMT+0');
    expect(tzShortLabel('Asia/Kolkata')).toBe('GMT+5:30');
  });

  it('zero-pads for display', () => {
    expect(fmtHM(9, 0)).toBe('09:00');
    expect(fmtHM(21, 5)).toBe('21:05');
  });
});
