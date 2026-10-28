import json
import logging
import os
import shutil
import tempfile
import threading
import time
import psutil

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FutureTimeoutError,
)

log = logging.getLogger(__name__)

# =========================================================
# Configuration
# =========================================================
MAX_FILE_SIZE_BYTES = 3 * 1024 ** 3  
SCAN_WORKSPACE      = os.path.join(tempfile.gettempdir(), "scan_workspace")
STAGING_DIR         = os.environ.get("STAGING_DIR", "./flagged")
FILE_SCAN_WORKERS   = 1
PARALLEL_FOLDER_SCANNERS = True
STAGING_FILE_SIZE_CAP_BYTES = 100 * 1024 * 1024  # 1000mb -- large model files (GGUF etc.) are on HuggingFace; only copy small flagged files locally

# =========================================================
# Central flagged log (thread-safe)
# =========================================================
from scanners import SCOPE_PROJECT_FOLDER, SCOPE_FILE_EXTENSION
flagged_log_lock = threading.Lock() # used to make sure only one thread writes to the log at a time

def append_to_flagged_log(staging_dir: str, entry: dict) -> None:
    log_path = os.path.join(staging_dir, "flagged_log.jsonl")
    with flagged_log_lock: # lock to avoid file corruption
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")


# =========================================================
# Scanner imports
# =========================================================
from scanners import ( 
    ScannerTemplate,
    ScanVerdict,
    get_all_scanners,
    verify_scanners,
    get_file_scanners,
    get_folder_scanners,
    get_vt_scanner,
)

# =========================================================
# Error tracking (per scanner)
# =========================================================
scanner_statistics: dict[str, dict] = {}
statistics_lock = threading.Lock() 

def record_scanner_error(scanner_name: str) -> None:
    with statistics_lock:
        scanner_data = scanner_statistics.setdefault(scanner_name, {"errors": 0, "total_time": 0.0, "count": 0})
        scanner_data["errors"] += 1

def record_scanner_performance(scanner_name: str, duration: float) -> None:
    with statistics_lock:
        scanner_data = scanner_statistics.setdefault(scanner_name, {"errors": 0, "total_time": 0.0, "count": 0})
        scanner_data["total_time"] += duration
        scanner_data["count"] += 1

def get_scanner_error_summary() -> dict[str, int]:
    with statistics_lock:
        return {name: data["errors"] for name, data in scanner_statistics.items() if data["errors"] > 0}

def get_scanner_perf_summary() -> dict[str, dict]:
    """Return average and total time per scanner."""
    with statistics_lock:
        summary = {}
        for name, data in scanner_statistics.items():
            if data["count"] > 0:
                summary[name] = {
                    "avg": round(data["total_time"] / data["count"], 3), # average seconds per file
                    "total": data["total_time"],
                    "count": data["count"]
                }
        return summary

def calculate_worst_severity(verdicts_list): 
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    worst_severity = "info"
    
    for verdict in verdicts_list:
        if order.get(verdict.severity, 0) > order.get(worst_severity, 0):
            worst_severity = verdict.severity
    return worst_severity


# =========================================================
# Result models
# =========================================================
class FileResult:
    def __init__(self, file_path, file_name, file_size,
                 flagged=False, verdicts=None, skipped=None):

        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size

        self.flagged = flagged
        self.verdicts = verdicts if verdicts is not None else []
        self.skipped = skipped

        self.worst_severity = "info"
        self.flagged_by = []

    def to_dict(self):
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "flagged": self.flagged,
            "worst_severity": self.worst_severity,
            "flagged_by": self.flagged_by,
            "skipped": self.skipped,
            "verdicts": [
                {
                    "scanner": v.scanner,
                    "flagged": v.flagged,
                    "severity": v.severity,
                    "details": v.details,
                    "error": v.error,
                    "duration": v.duration,
                }
                for v in self.verdicts
            ],
        }

class RepoResult:
    def __init__(self, repo_id, repo_type, total_files=0, outcome="clean", duration=0.0):
        self.repo_id = repo_id
        self.repo_type = repo_type

        self.total_files = total_files
        self.duration = duration
        self.files_scanned = 0
        self.files_flagged = 0
        self.files_clean = 0
        self.files_skipped = 0

        self.file_results = []
        self.project_verdicts = []
        self.flagged_files = []
        self.folder_scanner_timings = {}
        self.file_scanner_timings = {}
        self.scanner_file_counts = {}

        self.outcome = outcome

    def to_dict(self):
        return {
            "repo_id": self.repo_id,
            "repo_type": self.repo_type,
            "outcome": self.outcome,
            "duration_seconds": self.duration,
            "total_files": self.total_files,
            "files_scanned": self.files_scanned,
            "files_flagged": self.files_flagged,
            "files_clean": self.files_clean,
            "files_skipped": self.files_skipped,
            "flagged_files": self.flagged_files,
            "folder_scanner_timings": self.folder_scanner_timings,
            "file_scanner_timings": self.file_scanner_timings,
            "scanner_file_counts": self.scanner_file_counts,
            "file_results": [f.to_dict() for f in self.file_results],
            "project_verdicts": [
                {
                    "scanner": v.scanner,
                    "flagged": v.flagged,
                    "severity": v.severity,
                    "details": v.details,
                    "error": v.error,
                    "duration": v.duration,
                }
                for v in self.project_verdicts
            ],
        }

    def save_audit(self, audit_dir: str):
        import datetime, json as _json
        os.makedirs(audit_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_repo_name = self.repo_id.replace("/", "__")
        file_name = f"{safe_repo_name}__{timestamp}.json"
        full_path = os.path.join(audit_dir, file_name)
        data_to_write = {"scanned_at": datetime.datetime.now().isoformat(), **self.to_dict()}
        with open(full_path, "w") as file:
            _json.dump(data_to_write, file, indent=2, default=str)
        # print("audit saved to:", full_path)

def scan_file(file_path: str, scanner_list: list[ScannerTemplate],
              max_size_bytes=MAX_FILE_SIZE_BYTES): # scans a single file with applicable scanners

    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    # Step 1: Skip if file is massive
    if max_size_bytes is not None and file_size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        return FileResult(
            file_path, filename, file_size,
            skipped=f"File exceeds {max_mb:.0f}MB limit ({file_size / (1024**2):.1f}MB)",
        )

    # Step 2: Get scanners that can handle this file type
    applicable = get_file_scanners(scanner_list, file_path)

    vt_scanner = get_vt_scanner(scanner_list)
    file_result = FileResult(file_path, filename, file_size)
    is_malicious = False

    # Step 3: Run the local scanners and record performance
    for scanner in applicable:
        # Handle VirusTotal quota specifically
        if scanner.name == "virustotal" and vt_scanner.quota_exhausted:
            file_result.verdicts.append(ScanVerdict(scanner="virustotal", flagged=False, severity="info", details={"skipped": "quota_exhausted"}))
            continue

        try:
            verdict = scanner.timed_scan(file_path)
            record_scanner_performance(scanner.name, verdict.duration)
            file_result.verdicts.append(verdict)

            if verdict.error:
                record_scanner_error(scanner.name)
                if not verdict.error.startswith("Timed out"):
                    log.warning("Scanner %s error on file %s (%.2f MB): %s",
                                scanner.name, file_path, file_size / (1024 ** 2), verdict.error)

            if verdict.flagged:
                is_malicious = True
                print(f"    FLAGGED {scanner.name}: {filename} (severity={verdict.severity})")

        except Exception as crash_error:
            record_scanner_error(scanner.name)
            log.exception("Scanner %s crashed on file %s (%.2f MB)", scanner.name, file_path, file_size / (1024 ** 2))
            file_result.verdicts.append(ScanVerdict(scanner=scanner.name, flagged=False, severity="info", error=f"Crashed: {crash_error}"))

    file_result.flagged = is_malicious
    file_result.worst_severity = calculate_worst_severity(file_result.verdicts)
    file_result.flagged_by = list(dict.fromkeys(v.scanner for v in file_result.verdicts if v.flagged))

    return file_result

def local_scan_repo(repo_dir: str, repo_id: str, repo_type: str,
                    scanner_list: list[ScannerTemplate],
                    staging_dir: str = STAGING_DIR,
                    max_size_bytes=MAX_FILE_SIZE_BYTES):


    repo_result = RepoResult(repo_id, repo_type)


    all_files_to_scan = []   # collect and put all the files we need to scan
    for root_dir, _, file_names in os.walk(repo_dir):
        for one_file_name in file_names:
            if one_file_name.lower().endswith(".metadata"):
                continue
            all_files_to_scan.append(os.path.join(root_dir, one_file_name))

    repo_result.total_files = len(all_files_to_scan)

    scanner_file_counts = {one_scanner.name: 0 for one_scanner in scanner_list}
    for file_path in all_files_to_scan:
        for one_scanner in scanner_list:
            if one_scanner.scanner_applies_to_format(file_path):
                scanner_file_counts[one_scanner.name] += 1
    repo_result.scanner_file_counts = scanner_file_counts

    number_of_workers = FILE_SCAN_WORKERS
    cpu_count = os.cpu_count() or 1
    max_workers_for_system = max(1, cpu_count * 2)
    number_of_workers = max(1, min(number_of_workers, len(all_files_to_scan), max_workers_for_system))

    print(f"\n  Scanning repo: {repo_id} ({len(all_files_to_scan)} files)")

    # PHASE 1: folder-level scanners at the same time
    folder_scanners_list = get_folder_scanners(scanner_list)
    folder_findings_by_file = {}
    folder_phase_lock = threading.Lock()

    def run_one_folder_scanner(one_folder_scanner):
        print(f"    [folder] {one_folder_scanner.name}...", end="", flush=True)
        try:
            time_before_scan = time.monotonic()
            verdicts_from_folder_scan = one_folder_scanner.timed_folder_scan(repo_dir)
            time_folder_scan_took = time.monotonic() - time_before_scan

            record_scanner_performance(one_folder_scanner.name, time_folder_scan_took)

            number_flagged_by_this_scanner = sum(
                1 for v in verdicts_from_folder_scan if v.flagged == True
            )
            print(f" done ({time_folder_scan_took:.1f}s -- {len(verdicts_from_folder_scan)} findings, {number_flagged_by_this_scanner} flagged)")
            with folder_phase_lock:
                repo_result.folder_scanner_timings[one_folder_scanner.name] = round(time_folder_scan_took, 3)

                for one_verdict in verdicts_from_folder_scan:
                    file_ref_in_verdict = one_verdict.details.get("file") or one_verdict.details.get("path")

                    if file_ref_in_verdict:
                        if os.path.isabs(file_ref_in_verdict) == True:
                            abs_path_for_this_verdict = os.path.normpath(file_ref_in_verdict)
                        else:
                            abs_path_for_this_verdict = os.path.normpath(
                                os.path.join(repo_dir, file_ref_in_verdict)
                            )

                        if abs_path_for_this_verdict not in folder_findings_by_file:
                            folder_findings_by_file[abs_path_for_this_verdict] = []
                        folder_findings_by_file[abs_path_for_this_verdict].append(one_verdict)
                    else:
                        repo_result.project_verdicts.append(one_verdict)

        except Exception as folder_scanner_error:
            print(f" FAILED: {folder_scanner_error}")
            log.warning("Folder scanner %s failed on %s: %s",
                        one_folder_scanner.name, repo_dir, folder_scanner_error)

    # run folder scanners -- parallel or sequential depending on the flag
    if PARALLEL_FOLDER_SCANNERS:
        with ThreadPoolExecutor(max_workers=len(folder_scanners_list)) as folder_executor:
            folder_futures = [
                folder_executor.submit(run_one_folder_scanner, s)
                for s in folder_scanners_list
            ]
            for one_folder_future in as_completed(folder_futures):
                one_folder_future.result()
    else:
        for one_folder_scanner_to_run in folder_scanners_list:
            run_one_folder_scanner(one_folder_scanner_to_run)

  
    # PHASE 2: per-file scanners,run on each file individually
    shared_lock = threading.Lock()
    folder_scanner_names = {s.name for s in get_folder_scanners(scanner_list)}

    for one_scanner in scanner_list:
        if one_scanner.name not in folder_scanner_names:
            repo_result.file_scanner_timings[one_scanner.name] = 0.0

    def scan_one_file_and_merge_results(file_path):
        file_result = scan_file(file_path, scanner_list, max_size_bytes)

        # now merge in any findings from phase 1 that belong to this file
        extra_verdicts_from_folder_scan = folder_findings_by_file.get(
            os.path.normpath(file_path), []
        )

        if len(extra_verdicts_from_folder_scan) > 0:
            file_result.verdicts.extend(extra_verdicts_from_folder_scan)
            if any(v.flagged == True for v in extra_verdicts_from_folder_scan):
                file_result.flagged = True

            file_result.worst_severity = calculate_worst_severity(file_result.verdicts)
            file_result.flagged_by = list(dict.fromkeys(v.scanner for v in file_result.verdicts if v.flagged == True))

        with shared_lock:
            repo_result.file_results.append(file_result)

            for verdict in file_result.verdicts:
                if verdict.scanner not in folder_scanner_names:
                    if verdict.duration and verdict.duration > 0:
                        repo_result.file_scanner_timings[verdict.scanner] = (
                            repo_result.file_scanner_timings.get(verdict.scanner, 0.0)
                            + verdict.duration
                        )

            if file_result.skipped:
                repo_result.files_skipped += 1
                return

            repo_result.files_scanned += 1

            if file_result.flagged == True:
                repo_result.files_flagged += 1
                repo_result.flagged_files.append(file_path)

                rel_path = os.path.relpath(file_path, repo_dir)
                staging_path = os.path.join(
                    staging_dir, repo_id.replace("/", "__"), rel_path
                )

                os.makedirs(os.path.dirname(staging_path), exist_ok=True)

                # if its too big we just save the verdict and leave the file on huggingface
                the_file_size_on_disk = os.path.getsize(file_path)
                if the_file_size_on_disk <= STAGING_FILE_SIZE_CAP_BYTES:
                    try:
                        shutil.copy2(file_path, staging_path)
                    except OSError as copy_err:
                        log.warning("Could not copy %s to staging (%s) -- verdict only",
                                    file_result.file_name, copy_err)
                else:
                    print(f"    [staging] file too large to copy locally -- saving verdict only"
                          f" ({file_result.file_name} is {the_file_size_on_disk / (1024**3):.2f} GB,"
                          f" cap is {STAGING_FILE_SIZE_CAP_BYTES / (1024 * 1024):.0f} MB --"
                          f" original file remains on HuggingFace)")

                verdict_file_path = staging_path + ".verdicts.json"
                with open(verdict_file_path, "w") as f:
                    json.dump(file_result.to_dict(), f, indent=2, default=str)

                append_to_flagged_log(staging_dir, {
                    "timestamp":    time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "repo_id":      repo_id,
                    "file_name":    file_result.file_name,
                    "file_size":    file_result.file_size,
                    "severity":     file_result.worst_severity,
                    "flagged_by":   file_result.flagged_by,
                    "staging_path": staging_path,
                    "verdict_path": verdict_file_path,
                })
            else:
                repo_result.files_clean += 1

    if number_of_workers == 1:
        # true sequential. no threads at all but just a plain loop instead
        for file_path in all_files_to_scan:
            scan_one_file_and_merge_results(file_path)
    else:
        # parallel. N files scanned at the same time
        with ThreadPoolExecutor(max_workers=number_of_workers) as executor:
            futures_list = [
                executor.submit(scan_one_file_and_merge_results, file_path)
                for file_path in all_files_to_scan # parallelize across all files
            ]
            for one_future in as_completed(futures_list):
                one_future.result()

    has_flagged_files = repo_result.files_flagged > 0
    has_flagged_project_verdicts = any(v.flagged == True for v in repo_result.project_verdicts)

    if has_flagged_files == True or has_flagged_project_verdicts == True:
        repo_result.outcome = "malicious"
    else:
        repo_result.outcome = "clean"

    print(f"\n    Result: {repo_result.outcome.upper()} -- "
          f"{repo_result.files_scanned} scanned, "
          f"{repo_result.files_flagged} flagged, "
          f"{repo_result.files_skipped} skipped")

    return repo_result



# application to call
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test the scanner pipeline on a local target.")
    parser.add_argument("target")
    parser.add_argument("--scanner", default=None)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    all_scanners = get_all_scanners()
    if args.scanner:
        scanners_to_run = [s for s in all_scanners if s.name == args.scanner]
    else:
        scanners_to_run = verify_scanners(all_scanners)

    if os.path.isfile(args.target):
        print(json.dumps(scan_file(args.target, scanners_to_run).to_dict(), indent=2, default=str))

    elif os.path.isdir(args.target):
        result = local_scan_repo(
            args.target, "local-test", "model",
            scanners_to_run,
        )
        print(json.dumps(result.to_dict(), indent=2, default=str))

        # print the performance summary at the end
        perf_summary = get_scanner_perf_summary()
        if len(perf_summary) > 0:
            print("\nScanner Speeds:")
            for scanner_name, data in perf_summary.items():
                print(f"  {scanner_name}: {data['avg']:.2f}s avg")
