-- Migration 020: topics.scan_started_at — the "scan in progress" signal.
--
-- Until now scan progress was only observable via a frontend-initiated task_id in
-- localStorage, so SCHEDULED / automatic scans (and often the first scan) ran
-- invisibly — the user couldn't tell if a scan was running, stuck, or broken.
--
-- The pipeline now stamps scan_started_at = NOW() when a run begins (any path:
-- manual, scheduled, first-scan) and clears it (NULL) when the run ends. Every
-- screen derives `is_scanning` from this: set AND recent (a staleness guard treats
-- a stamp older than ~15 min as not-scanning, so a crashed run never sticks "on").
--
-- Safe + degrade-friendly: NULL means "idle"; the pipeline write is wrapped so a
-- pre-020 database simply never shows the live scanning state (no errors).

ALTER TABLE topics
    ADD COLUMN IF NOT EXISTS scan_started_at timestamptz DEFAULT NULL;
