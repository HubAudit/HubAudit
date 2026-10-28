import os
import sqlite3
import threading
import time
import json

class ScanLogDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.write_lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                repo_id TEXT PRIMARY KEY,
                outcome TEXT,
                crawled_at TEXT,
                files_total INTEGER,
                files_flagged INTEGER,
                files_clean INTEGER,
                flagged_files TEXT,
                details TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_outcome ON scans(outcome)")
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        conn.close()
        print(f"  Scan DB: {db_path} ({count} entries)")

    def is_scanned(self, repo_id):
        the_permanent_outcomes = ("clean", "malicious", "gated", "not_found", "disabled", "revision_not_found", "no_supported_files", "download_timeout")
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            row = conn.execute(
                "SELECT outcome FROM scans WHERE repo_id = ?", (repo_id,)
            ).fetchone()
            if row is None:
                return False  # never seen this repo before
            the_outcome_have = row[0]
            return the_outcome_have in the_permanent_outcomes
        finally:
            conn.close()

    def save(self, repo_id, result):
        with self.write_lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.execute(
                    """INSERT INTO scans
                       (repo_id, outcome, crawled_at, files_total,
                        files_flagged, files_clean, flagged_files, details)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(repo_id) DO UPDATE SET
                           outcome       = excluded.outcome,
                           crawled_at    = excluded.crawled_at,
                           files_total   = excluded.files_total,
                           files_flagged = excluded.files_flagged,
                           files_clean   = excluded.files_clean,
                           flagged_files = excluded.flagged_files,
                           details       = excluded.details""",
                    (
                        repo_id, result.outcome,
                        time.strftime("%Y-%m-%dT%H:%M:%S"),
                        result.total_files, result.files_flagged,
                        result.files_clean,
                        json.dumps(result.flagged_files),
                        json.dumps(result.to_dict(), default=str),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def record_repo_status(self, repo_id, outcome):
        """Quickly records a repository status when full scan details are not available."""
        with self.write_lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.execute(
                    """INSERT INTO scans
                       (repo_id, outcome, crawled_at, files_total,
                        files_flagged, files_clean, flagged_files, details)
                       VALUES (?, ?, ?, 0, 0, 0, '[]', '{}')
                       ON CONFLICT(repo_id) DO UPDATE SET
                           outcome    = excluded.outcome,
                           crawled_at = excluded.crawled_at""",
                    (repo_id, outcome, time.strftime("%Y-%m-%dT%H:%M:%S")),
                )
                conn.commit()
            finally:
                conn.close()

    def save_error(self, repo_id, outcome, error):
        with self.write_lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.execute(
                    """INSERT INTO scans
                       (repo_id, outcome, crawled_at, files_total,
                        files_flagged, files_clean, flagged_files, details)
                       VALUES (?, ?, ?, 0, 0, 0, '[]', ?)
                       ON CONFLICT(repo_id) DO UPDATE SET
                           outcome    = excluded.outcome,
                           crawled_at = excluded.crawled_at,
                           details    = excluded.details""",
                    (
                        repo_id, outcome,
                        time.strftime("%Y-%m-%dT%H:%M:%S"),
                        json.dumps({"error": error}),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def get_all_scanned_ids(self):
        the_permanent_outcomes = ("clean", "malicious", "gated", "not_found", "disabled", "revision_not_found", "no_supported_files", "download_timeout")
        the_placeholders = ",".join("?" * len(the_permanent_outcomes))
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            rows = conn.execute(
                f"SELECT repo_id FROM scans WHERE outcome IN ({the_placeholders})",
                the_permanent_outcomes
            ).fetchall()
            return set(row[0] for row in rows)
        finally:
            conn.close()

    def summary(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        rows = conn.execute(
            "SELECT outcome, COUNT(*) FROM scans GROUP BY outcome ORDER BY COUNT(*) DESC"
        ).fetchall()
        the_file_totals_row = conn.execute(
            "SELECT SUM(files_total), SUM(files_clean), SUM(files_flagged), SUM(files_total) - SUM(files_clean) - SUM(files_flagged) FROM scans"
        ).fetchone()
        conn.close()

        print("\n  Scan log summary:")
        for outcome, cnt in rows:
            print(f"    {outcome:<24} {cnt:>6}")
        print(f"    {'TOTAL':<24} {sum(r[1] for r in rows):>6}")

        if the_file_totals_row is not None and the_file_totals_row[0] is not None:
            the_total   = the_file_totals_row[0] or 0
            the_clean   = the_file_totals_row[1] or 0
            the_flagged = the_file_totals_row[2] or 0
            the_skipped = the_file_totals_row[3] or 0
            print(f"\n  Files scanned:")
            print(f"    {'total':<24} {the_total:>6}")
            print(f"    {'clean':<24} {the_clean:>6}")
            print(f"    {'flagged':<24} {the_flagged:>6}")
            if the_skipped > 0:
                print(f"    {'skipped':<24} {the_skipped:>6}  (not clean or flagged -- download/read issues)")


class RepoQueueDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.write_lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repo_queue (
                repo_id   TEXT PRIMARY KEY,
                repo_type TEXT,
                status    TEXT DEFAULT 'pending',
                queued_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON repo_queue(status)")
        conn.commit()
        the_count = conn.execute("SELECT COUNT(*) FROM repo_queue").fetchone()[0]
        conn.close()
        print(f"  Queue DB: {db_path} ({the_count:,} entries)")

    def is_built(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            the_count = conn.execute("SELECT COUNT(*) FROM repo_queue").fetchone()[0]
            return the_count > 0
        finally:
            conn.close()

    def build(self, repo_ids, repo_type):
        the_queued_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        with self.write_lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.executemany(
                    """INSERT OR IGNORE INTO repo_queue (repo_id, repo_type, status, queued_at)
                       VALUES (?, ?, 'pending', ?)""",
                    [(rid, repo_type, the_queued_at) for rid in repo_ids]
                )
                conn.commit()
                the_count = conn.execute("SELECT COUNT(*) FROM repo_queue").fetchone()[0]
                print(f"  Queue built: {the_count:,} repos inserted")
            finally:
                conn.close()

    def mark_done(self, repo_id):
        with self.write_lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.execute(
                    "UPDATE repo_queue SET status = 'done' WHERE repo_id = ?",
                    (repo_id,)
                )
                conn.commit()
            finally:
                conn.close()

    def mark_done_batch(self, repo_ids):
        # used during initial sync -- marks already-scanned repos so they get skipped
        the_list_of_ids = list(repo_ids)
        if len(the_list_of_ids) == 0:
            return
        with self.write_lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            try:
                conn.executemany(
                    "UPDATE repo_queue SET status = 'done' WHERE repo_id = ?",
                    [(rid,) for rid in the_list_of_ids]
                )
                conn.commit()
            finally:
                conn.close()

    def get_pending(self, order="top"):
        if order == "last":
            the_order_direction = "DESC"
        else:
            the_order_direction = "ASC"

        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            the_total   = conn.execute("SELECT COUNT(*) FROM repo_queue").fetchone()[0]
            the_done    = conn.execute("SELECT COUNT(*) FROM repo_queue WHERE status = 'done'").fetchone()[0]
            rows        = conn.execute(
                "SELECT repo_id FROM repo_queue WHERE status = 'pending' ORDER BY rowid " + the_order_direction
            ).fetchall()
            the_pending = [row[0] for row in rows]
            return the_pending, the_total, the_done
        finally:
            conn.close()

    def summary(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM repo_queue GROUP BY status ORDER BY COUNT(*) DESC"
        ).fetchall()
        conn.close()
        print("\n  Queue summary:")
        for the_status, the_count in rows:
            print(f"    {the_status:<24} {the_count:>6}")
