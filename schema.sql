-- Job Application Tracker schema (Neon / Postgres)
CREATE TABLE IF NOT EXISTS applications (
    id           SERIAL PRIMARY KEY,
    company      TEXT NOT NULL,
    role         TEXT,
    status       TEXT NOT NULL DEFAULT 'Applied'
                 CHECK (status IN ('Wishlist','Applied','OA_Pending','OA','Interview','Offer','Rejected')),
    deadline     DATE,
    next_step    TEXT,
    city         TEXT,
    link         TEXT,
    notes        TEXT,
    source       TEXT NOT NULL DEFAULT 'manual',   -- manual / import / gmail
    source_email TEXT,                             -- Gmail message id that last changed it
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every status change, with evidence (for auditing Gmail auto-updates)
CREATE TABLE IF NOT EXISTS status_events (
    id             SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    old_status     TEXT,
    new_status     TEXT NOT NULL,
    source         TEXT NOT NULL,                 -- manual / import / gmail
    evidence       TEXT,                          -- e.g. email subject + sender
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_status   ON applications(status);
CREATE INDEX IF NOT EXISTS idx_app_deadline ON applications(deadline);
CREATE INDEX IF NOT EXISTS idx_app_company  ON applications(lower(company));
