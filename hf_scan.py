import argparse
import json
from collections import deque
import logging
import os
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
import subprocess
import signal
import psutil
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.errors import (
    GatedRepoError,
    RepositoryNotFoundError,
    DisabledRepoError,
    RevisionNotFoundError,
)
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore, Event
import requests
from dotenv import load_dotenv
load_dotenv()


# my stuff
from pipeline import local_scan_repo, RepoResult, FileResult, get_scanner_perf_summary
from storage_flush import StorageFlusher
from scanners import get_all_scanners, verify_scanners, ScanVerdict
from utils.functions import check_disk_space, check_space_for_incoming, fetch_tree_recursive, STOP_EVENT, HF_ENDPOINT, DOWNLOAD_ENDPOINT, MAX_TREE_DEPTH, format_runtime, kill_all_running_downloads, the_live_download_processes, the_download_proc_lock, the_download_worker_script
from utils.db import ScanLogDB, RepoQueueDB

MAX_WORKERS = 2

SCAN_WORKSPACE = os.path.join(tempfile.gettempdir(), "scan_workspace")
STAGING_DIR = os.environ.get("STAGING_DIR", "./flagged")
AUDIT_DIR   = os.environ.get("AUDIT_DIR",   "./audit")
FLUSH_THRESHOLD_GB = 30 #50

# file formats to find and scan
CODE_FORMATS = {".py"}
CONFIG_FORMATS = {".yaml", ".yml", ".json", ".toml", ".cfg", ".jinja"}
DATA_FORMATS = {".parquet", ".arrow", ".jsonl", ".csv"}
DEPENDENCY_FORMATS = {
    "requirement.txt", "requirements.txt", "requirements-dev.txt",
    "requirements-test.txt", "requirements-prod.txt",
}
MODEL_FORMATS = {".gguf"} 

MANIFEST_NAMES = {
    "pyproject.toml", "poetry.lock", "uv.lock",
    "pipfile", "pipfile.lock", "pylock.toml",
}
ALL_SUPPORTED_FORMATS_COMBINED = CODE_FORMATS | CONFIG_FORMATS | DATA_FORMATS | DEPENDENCY_FORMATS | MODEL_FORMATS | MANIFEST_NAMES


DOWNLOAD_TIMEOUT_IN_SECS = 300
SNAPSHOT_CAP_BYTES = 30 * 1024 * 1024 * 1024 #30 #50GB
SNAPSHOT_TIMEOUT = 1800

HF_TOKEN = os.environ.get("HF_TOKEN", None)
api = HfApi(token=HF_TOKEN, endpoint=HF_ENDPOINT)
api_listing = HfApi(token=HF_TOKEN)


the_rate_limit_lock = threading.Lock()
the_time_got_rate_limited = 0.0    # 0.0 means we are not rate limited right now
the_current_backoff_seconds = 0.0     # how long to wait,this grows each time we get limited again

log_file_handler = logging.FileHandler("scanner.log", encoding="utf-8")
log_file_handler.setLevel(logging.WARNING)
log_console_handler = logging.StreamHandler()
log_console_handler.setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
    handlers=[ log_file_handler,  log_console_handler],
)

logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)


def check_and_apply_backoff_before_api_call():
    global the_time_got_rate_limited
    global the_current_backoff_seconds

    with the_rate_limit_lock:
        the_current_time_now = time.monotonic()
        the_time_when_backoff_ends = the_time_got_rate_limited + the_current_backoff_seconds

        if the_current_time_now < the_time_when_backoff_ends:
            the_remaining_wait = the_time_when_backoff_ends - the_current_time_now
        else:
            the_remaining_wait = 0.0

    if the_remaining_wait > 0.0:
        print(f"  [429 backoff] waiting {the_remaining_wait:.1f}s before next api call...")
        time.sleep(the_remaining_wait)


def handle_rate_limit_response():
    global the_time_got_rate_limited
    global the_current_backoff_seconds

    with the_rate_limit_lock:
        the_time_got_rate_limited = time.monotonic()
        if the_current_backoff_seconds == 0.0:
            the_current_backoff_seconds = 60.0   # start with 1 minute
        else:
            the_current_backoff_seconds = min(the_current_backoff_seconds * 2, 600.0)  # max 10 minutes
        print(f"  [429 rate limited] new backoff window is {the_current_backoff_seconds:.0f}s")


def download_repo_files(repo_id, repo_type, local_workspace_path, target_files):
    patterns_filee = os.path.join(SCAN_WORKSPACE, repo_id.replace("/", "__") + ".patterns.json")
    the_status_file   = os.path.join(SCAN_WORKSPACE, repo_id.replace("/", "__") + ".status.json")
    the_list_of_patterns = [target_file.rfilename for target_file in target_files]
    file_for_patterns = open(patterns_filee, "w")
    json.dump(the_list_of_patterns, file_for_patterns)
    file_for_patterns.close()
    if os.path.exists(the_status_file):
        os.remove(the_status_file)

    the_download_status = "error"  
    the_download_error_message = ""
    the_download_timed_out = False

    try:
        the_download_command = [
            sys.executable,
            the_download_worker_script,
            repo_id,
            repo_type,
            local_workspace_path,
            patterns_filee,
            the_status_file,
            DOWNLOAD_ENDPOINT,  
        ]
       
        download_process = subprocess.Popen(the_download_command, start_new_session=True)
        
        # remember it so Ctrl+C / atexit can find it and kill it
        with the_download_proc_lock:
            the_live_download_processes.add(download_process)

        try:
            download_process.wait(timeout=SNAPSHOT_TIMEOUT)
        except subprocess.TimeoutExpired:
            the_download_timed_out = True
            print(f"  download timed out for {repo_id} -- killing the download process")

            try:
                os.killpg(os.getpgid(download_process.pid), signal.SIGTERM)
            except Exception:
                download_process.terminate()
            try:
                download_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"  download process for {repo_id} wont die -- force killing it")
                try:
                    os.killpg(os.getpgid(download_process.pid), signal.SIGKILL)
                except Exception:
                    download_process.kill()
                download_process.wait()
        finally:
            with the_download_proc_lock:
                the_live_download_processes.discard(download_process)

        if the_download_timed_out == True:
            the_download_status = "timeout"
        else:
            if os.path.exists(the_status_file):
                try:
                    file_with_status = open(the_status_file)
                    the_status_data = json.load(file_with_status)
                    file_with_status.close()
                    the_download_status = the_status_data.get("status", "error")
                    the_download_error_message = the_status_data.get("message", "")
                except Exception as the_status_read_error:
                    the_download_status = "error"
                    the_download_error_message = "couldnt read status file: " + str(the_status_read_error)
            else:
                the_download_status = "error"
                the_download_error_message = "download process exited without a status (code " + str(download_process.returncode) + ")"

    finally:
        if os.path.exists(patterns_filee):
            os.remove(patterns_filee)
        if os.path.exists(the_status_file):
            os.remove(the_status_file)

    # print("download status for", repo_id, "is", the_download_status)
    return the_download_status, the_download_error_message


def scan_one_repo(repo_id, repo_type, scan_database, scanner_list, result_flusher, progress_bar, request_semaphore):
    
    if scan_database.is_scanned(repo_id):
        progress_bar.update(1)
        return "skipped"

    if STOP_EVENT.is_set(): 
        progress_bar.update(1)
        return "stopped"

    if not check_disk_space(flusher=result_flusher):
        progress_bar.update(1)
        return "disk is full"

    try:
        # STEP 1: Fist fetch repository metadata from Hugging Face API
        repository_info = None
        the_number_of_api_retries_so_far = 0
        the_max_retries_will_do = 5

        while the_number_of_api_retries_so_far < the_max_retries_will_do:
            check_and_apply_backoff_before_api_call() 
            try:
                with request_semaphore: 
                    if repo_type == "dataset":
                        repository_info = api.dataset_info(repo_id, files_metadata=True)
                    else:
                        repository_info = api.model_info(repo_id, files_metadata=True)
                break  
            except Exception as the_api_call_error:
                the_error_message_text = str(the_api_call_error).lower()
                if isinstance(the_api_call_error, (GatedRepoError, RepositoryNotFoundError, DisabledRepoError, RevisionNotFoundError)):
                    raise  
               
                if "429" in the_error_message_text or "rate limit" in the_error_message_text or "too many requests" in the_error_message_text:
                    print(f"  [429] rate limited fetching {repo_id} -- will back off and retry")
                    handle_rate_limit_response()
                    the_number_of_api_retries_so_far = the_number_of_api_retries_so_far + 1
                else:
                    the_number_of_api_retries_so_far = the_number_of_api_retries_so_far + 1
                    if the_number_of_api_retries_so_far >= the_max_retries_will_do:
                        raise 
                    time.sleep(5)

        if repository_info is None:
            raise Exception("repository_info was never set after retries")


        # STEP 2: Identify preferred files 
        target_files = []

        for sibling_file in (repository_info.siblings or []):
            file_path_lower = sibling_file.rfilename.lower()
            file_name = file_path_lower.split("/")[-1]

            if file_name.endswith(".metadata"):
                continue


            has_matching_extension = any(
                file_path_lower.endswith(file_extension) 
                for file_extension in ALL_SUPPORTED_FORMATS_COMBINED
            )
            if has_matching_extension:
                target_files.append(sibling_file)

        if not target_files:
            scan_database.record_repo_status(repo_id, "no_supported_files")
            progress_bar.update(1)
            return "no_supported_files"

        # STEP 3: Get Hugging Face's security scan results from their tree API
        hf_api_results = {}
        
        # TODO:Optimization: Only walk the tree if at least one target file is shallow enough
        # for the recursive tree walk to actually reach it.
        target_rfilenames = [f.rfilename for f in target_files]
        shallowest_file_depth = min(path.count("/") for path in target_rfilenames)

        if shallowest_file_depth <= MAX_TREE_DEPTH:
            tree_api_entries = fetch_tree_recursive(repo_id, repo_type, request_semaphore)
            for tree_entry in tree_api_entries:
                file_path = tree_entry.get("path", "")
                security_status = tree_entry.get("securityFileStatus", {}).get("status", "unknown")
                hf_api_results[file_path] = security_status
        else:
            print(f"  Tree walk skipped for {repo_id} - all target files at depth > {MAX_TREE_DEPTH} "
                  f"(shallowest is {shallowest_file_depth}), using get_paths_info directly")

       
        # TODO:FALLBACK: If some files are deeper than MAX_TREE_DEPTH, they won't be in the map.
        # only query specifically for those missing file paths.
        paths_missing_from_tree_walk = [
            target_file.rfilename 
            for target_file in target_files 
            if target_file.rfilename not in hf_api_results
        ]

        if paths_missing_from_tree_walk:
            try:
                the_paths_retry_count = 0
                the_paths_max_retries = 5
                path_infos = None

                while the_paths_retry_count < the_paths_max_retries:
                    check_and_apply_backoff_before_api_call()  # sleep here if rate limited, no semaphore held
                    try:
                        with request_semaphore:
                            # get_paths_info covers 2 scanners (av_scan and pickle_import_scan) vs 4 scan results in tree walk
                            path_infos = api.get_paths_info(
                                repo_id=repo_id,
                                repo_type=repo_type,
                                paths=paths_missing_from_tree_walk,
                                expand=True
                            )
                        # print("paths info worked")
                        break  # stop the retrying
                    except Exception as the_paths_error:
                        the_paths_error_text = str(the_paths_error).lower()
                        if "429" in the_paths_error_text or "rate limit" in the_paths_error_text or "too many requests" in the_paths_error_text:
                            print(f"  [429] rate limited on get_paths_info for {repo_id}")
                            handle_rate_limit_response()
                            the_paths_retry_count = the_paths_retry_count + 1
                        else:
                            raise  # not a 429, dont retry

                if path_infos is not None:
                    for entry in path_infos:
                        file_path = getattr(entry, "path", "")
                        security_object  = getattr(entry, "security", {})
                        # handle both object and dict styles from the SDK
                        status = security_object.get("status", "unknown") if isinstance(security_object, dict) else getattr(security_object, "status", "unknown")
                        hf_api_results[file_path] = status
            except Exception as fallback_error:
                print(f"  Fallback security check failed for {repo_id}: {fallback_error}")    

        # STEP 4: Either download and scan locally, OR rely on HF API results
        total_bytes = sum(file.size or 0 for file in target_files)
        should_download_locally = total_bytes <= SNAPSHOT_CAP_BYTES
        scan_result = RepoResult(repo_id, repo_type, total_files=len(target_files))

        if should_download_locally and total_bytes > 0:
            if not check_space_for_incoming(total_bytes, flusher=result_flusher):
                should_download_locally = False

        if should_download_locally: # Local scan path: download repository files and run scanners
            local_workspace_path = os.path.join(
                SCAN_WORKSPACE, 
                repo_id.replace("/", "__")
            )
            
            # Clean up any existing directory and create fresh workspace
            shutil.rmtree(local_workspace_path, ignore_errors=True)
            os.makedirs(local_workspace_path, exist_ok=True)

            try:
                the_download_status, the_download_error_message = download_repo_files(
                    repo_id, repo_type, local_workspace_path, target_files
                )

                if STOP_EVENT.is_set():
                    return "stopped"

                should_scan_what_we_have = (the_download_status == "ok" or the_download_status == "timeout")

                if should_scan_what_we_have == True:
                    shutil.rmtree(os.path.join(local_workspace_path, ".cache"), ignore_errors=True)

                    target_names = {f.rfilename for f in target_files}
                    for root, dirs, files in os.walk(local_workspace_path):
                        for fname in files:
                            full_p = os.path.join(root, fname)
                            rel_p = os.path.relpath(full_p, local_workspace_path).replace(os.sep, "/")
                            if rel_p not in target_names:
                                os.remove(full_p)

                    local_scan_result = local_scan_repo(
                        local_workspace_path,
                        repo_id,
                        repo_type,
                        scanner_list,
                        STAGING_DIR,
                    )

                    for path, status in hf_api_results.items():
                        if status != "unsafe":
                            continue

                        hf_verdict = ScanVerdict(
                            scanner="hf_security_api",
                            flagged=True,
                            severity="high",
                            details={"status": "unsafe"},
                        )
                        
                        matching_file_result = None
                        for one_file_result in local_scan_result.file_results:
                            rel_path = os.path.relpath(one_file_result.file_path, local_workspace_path).replace(os.sep, "/")
                            if rel_path == path:
                                matching_file_result = one_file_result
                                break

                        if matching_file_result is not None:
                            was_already_flagged = matching_file_result.flagged
                            matching_file_result.verdicts.append(hf_verdict)
                            matching_file_result.flagged = True
                            if "hf_security_api" not in matching_file_result.flagged_by:
                                matching_file_result.flagged_by.append("hf_security_api")
                            severity_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
                            if severity_rank.get("high", 0) > severity_rank.get(matching_file_result.worst_severity, 0):
                                matching_file_result.worst_severity = "high"


                            if was_already_flagged == False:
                                local_scan_result.files_flagged += 1
                                local_scan_result.files_clean -= 1
                                if matching_file_result.file_path not in local_scan_result.flagged_files:
                                    local_scan_result.flagged_files.append(matching_file_result.file_path)
                        else:
                            # no file result means we never downloaded it (unsupported format).
                            # still record it so we dont lose which file HF flagged
                            new_file_result = FileResult(path, os.path.basename(path), 0, flagged=True, verdicts=[hf_verdict])
                            new_file_result.flagged_by = ["hf_security_api"]
                            new_file_result.worst_severity = "high"
                            local_scan_result.file_results.append(new_file_result)
                            local_scan_result.files_flagged += 1
                            if path not in local_scan_result.flagged_files:
                                local_scan_result.flagged_files.append(path)

                        local_scan_result.outcome = "malicious"

                        # copy the file to staging if we actually have it on disk, and write the
                        src_file = os.path.join(local_workspace_path, path.replace("/", os.sep))
                        if os.path.exists(src_file):
                            dest_repo_dir = os.path.join(STAGING_DIR, repo_id.replace("/", "__"))
                            dest_file = os.path.join(dest_repo_dir, path.replace("/", os.sep))
                            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                            shutil.copy2(src_file, dest_file)
                            with open(dest_file + ".verdicts.json", "w") as f:
                                if matching_file_result is not None:
                                    json.dump(matching_file_result.to_dict(), f, indent=2, default=str)
                                else:
                                    json.dump(new_file_result.to_dict(), f, indent=2, default=str)

                    scan_result.files_flagged = local_scan_result.files_flagged
                    scan_result.files_clean = local_scan_result.files_clean
                    scan_result.files_scanned = local_scan_result.files_scanned
                    scan_result.files_skipped = local_scan_result.files_skipped
                    scan_result.flagged_files = local_scan_result.flagged_files
                    scan_result.outcome = local_scan_result.outcome
                    scan_result.file_results = local_scan_result.file_results
                    scan_result.project_verdicts = local_scan_result.project_verdicts

                    if the_download_status == "timeout" and scan_result.outcome != "malicious":
                        scan_result.outcome = "download_timeout"
                        print(f"  scanned partial files for {repo_id} (timed out) -- nothing malicious, will retry later")

                    local_scan_result.save_audit(AUDIT_DIR) # save the local scan result for auditing and analysis, regardless of outcome
                else:
                    if the_download_status == "gated":
                        scan_result.outcome = "gated"
                        print(f"  download error for {repo_id}: gated repo")
                    elif the_download_status == "not_found":
                        scan_result.outcome = "not_found"
                        print(f"  download error for {repo_id}: repo not found")
                    elif the_download_status == "disabled":
                        scan_result.outcome = "disabled"
                        print(f"  download error for {repo_id}: repo disabled")
                    elif the_download_status == "revision_not_found":
                        scan_result.outcome = "revision_not_found"
                        print(f"  download error for {repo_id}: revision not found")
                    else:
                        scan_result.outcome = "download_error"
                        print(f"  download error for {repo_id}: {the_download_error_message}")

            finally:
                shutil.rmtree(local_workspace_path, ignore_errors=True)
                
        else:
            unsafe_files_detected = []
            # print (f"seeeeee hf_api_results for {repo_id}: {hf_api_results}")
            for file_path, security_status in hf_api_results.items():
                if security_status == "unsafe":
                    unsafe_files_detected.append(file_path)
            
            scan_result.files_flagged = len(unsafe_files_detected)
            scan_result.files_scanned = len(target_files)
            scan_result.files_clean = scan_result.files_scanned - scan_result.files_flagged
            scan_result.flagged_files = unsafe_files_detected
             
            if unsafe_files_detected:
                scan_result.outcome = "malicious"
                print(f"  HF API flagged {len(unsafe_files_detected)} files in {repo_id} (Repo too large for full scan)")
                
                repo_staging_dir = os.path.join(STAGING_DIR, repo_id.replace("/", "__"))
                os.makedirs(repo_staging_dir, exist_ok=True)

                for unsafe_file_path in unsafe_files_detected[:5]:
                    print(f"    - {unsafe_file_path}")
                    try:
                        # download individual file
                        hf_hub_download(
                            repo_id=repo_id,
                            repo_type=repo_type,
                            filename=unsafe_file_path,
                            local_dir=repo_staging_dir,
                            token=HF_TOKEN
                        )
                        
                        verdict_path = os.path.join(repo_staging_dir, unsafe_file_path.replace("/", os.sep)) + ".verdicts.json"
                        os.makedirs(os.path.dirname(verdict_path), exist_ok=True)
                        with open(verdict_path, "w") as f:
                            json.dump({
                                "file": unsafe_file_path, 
                                "hf_status": "unsafe", 
                                "local_scan": "skipped_due_to_size_cap"
                            }, f, indent=2)

                    except Exception as error:
                        print(f"      failed individual download: {error}")

                if len(unsafe_files_detected) > 5:
                    print(f"    ... and {len(unsafe_files_detected) - 5} more")
            else:
                scan_result.outcome = "clean"

        # STEP 5: Save results and update progress
        scan_database.save(repo_id, scan_result)
        result_flusher.check_and_flush() 
        progress_bar.update(1)
        
        return scan_result.outcome

    except Exception as scan_error:
        if isinstance(scan_error, GatedRepoError):
            the_outcome_to_save = "gated"
        elif isinstance(scan_error, RepositoryNotFoundError):
            the_outcome_to_save = "not_found"
        elif isinstance(scan_error, DisabledRepoError):
            the_outcome_to_save = "disabled"
        elif isinstance(scan_error, RevisionNotFoundError):
            the_outcome_to_save = "revision_not_found"
        else:
            the_outcome_to_save = "error"

        print(f"Error scanning {repo_id} [{the_outcome_to_save}]: {scan_error}")
        if the_outcome_to_save == "error":
            traceback.print_exc()

        try:
            scan_database.save_error(repo_id, the_outcome_to_save, str(scan_error))
        except:
            print("couldn't even save the error Exception caught")
        progress_bar.update(1)
        return the_outcome_to_save




# Appp Main--
def main():
    time_started = time.monotonic()

    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--workers",      type=int, default=MAX_WORKERS)
    parser.add_argument("--limit",        type=int, default=None)
    parser.add_argument("--sort", default="default", choices=["default", "least-liked", "most-liked"])
    parser.add_argument("--skip-health-check", action="store_true")
    
    # scale scanning horizontally:
    parser.add_argument("--instance",        type=int, default=1)
    parser.add_argument("--total-instances", type=int, default=1)
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--end",   type=int, default=None,)
    parser.add_argument("--order", default="top", choices=["top", "last"])
    args = parser.parse_args()


    the_storage_bucket = os.environ.get("STORAGE_BUCKET", "").strip()
    the_gcs_project    = os.environ.get("GCS_PROJECT", "").strip()
    if not the_storage_bucket or not the_gcs_project:
        print("error: STORAGE_BUCKET and GCS_PROJECT must be set in your environment before running")
        print(f"  STORAGE_BUCKET = {'set' if the_storage_bucket else 'NOT SET'}")
        print(f"  GCS_PROJECT    = {'set' if the_gcs_project else 'NOT SET'}")
        return

    # manual range and instance splitting are two different modes
    using_manual_range   = args.start is not None or args.end is not None
    using_instance_split = args.total_instances > 1

    if using_manual_range and using_instance_split:
        print("error: --start/--end cannot be used together with --instance/--total-instances")
        print("       use one or the other, not both")
        return

    if using_manual_range:
        if args.start is None or args.end is None:
            print("error: --start and --end must both be provided")
            return
        if args.start < 1:
            print("error: --start must be at least 1")
            return
        if args.end < args.start:
            print(f"error: --end ({args.end}) must be greater than or equal to --start ({args.start})")
            return

    if not using_manual_range:
        if args.total_instances < 1:
            print("error: --total-instances must be at least 1")
            return
        if args.instance < 1 or args.instance > args.total_instances:
            print(f"error: --instance must be between 1 and {args.total_instances}")
            return

    os.makedirs(SCAN_WORKSPACE, exist_ok=True)
    os.makedirs(STAGING_DIR, exist_ok=True)


    # Set up our list of scanners
    scanners_to_try = get_all_scanners()
    if args.skip_health_check:
        print("\nSkipping scanner health check.")
        available = scanners_to_try
    else:
        available = verify_scanners(scanners_to_try)

    if using_manual_range:
        the_gcs_prefix = f"scan_results/{args.tag}/{args.start}to{args.end}"
    elif using_instance_split:
        the_gcs_prefix = f"scan_results/{args.tag}/instance{args.instance}"
    else:
        the_gcs_prefix = f"scan_results/{args.tag}"
    flusher = StorageFlusher(STAGING_DIR, bucket_name=the_storage_bucket, threshold_gb=FLUSH_THRESHOLD_GB, prefix=the_gcs_prefix)
    resolved_type = args.type[:-1] if args.type.endswith('s') else args.type
    if using_manual_range:
        the_queue_db_name = f"repo_queue_{args.tag}_{args.start}to{args.end}.db"
        the_db_name       = f"scan_log_{args.tag}_{args.start}to{args.end}.db"
    elif using_instance_split:
        the_queue_db_name = f"repo_queue_{args.tag}_instance{args.instance}of{args.total_instances}.db"
        the_db_name       = f"scan_log_{args.tag}_instance{args.instance}of{args.total_instances}.db"
    else:
        the_queue_db_name = f"repo_queue_{args.tag}.db"
        the_db_name       = f"scan_log_{args.tag}.db"

    the_queue_db_path = os.path.join("data", the_queue_db_name)
    queue = RepoQueueDB(the_queue_db_path)
    if queue.is_built():
        print(f"  Queue found -- loading pending repos (skipping HF API fetch)")
        repo_ids, the_queue_total, the_queue_done = queue.get_pending(args.order)
        print(f"  {len(repo_ids):,} pending / {the_queue_total:,} total ({the_queue_done:,} already done)")

        if using_manual_range:
            the_vm_label = (
                f"{args.tag} ({args.type}) -- manual range\n"
                f"Repos {args.start:,}-{args.end:,} ({len(repo_ids):,} pending of {the_queue_total:,})\n\n"
            )
        elif using_instance_split:
            the_vm_label = (
                f"Instance {args.instance}/{args.total_instances} | {args.tag} ({args.type})\n"
                f"{len(repo_ids):,} pending of {the_queue_total:,} total\n\n"
            )
        else:
            the_vm_label = (
                f"{args.tag} ({args.type})\n"
                f"{len(repo_ids):,} pending of {the_queue_total:,} total\n\n"
            )

    else:
        print(f"Fetching {args.type} list for '{args.tag}'...")
        n = args.limit or 1000

        if args.type == "datasets":
            if args.sort == "least-liked":
                buf = deque(maxlen=n)
                for d in api.list_datasets(filter=f"task_categories:{args.tag}", sort="likes"):
                    buf.append(d.id)
                repo_ids = list(buf)
            else:
                repo_ids = [d.id for d in api.list_datasets(filter=f"task_categories:{args.tag}", sort="likes", limit=args.limit)]
        else:
            if args.sort == "least-liked":
                buf = deque(maxlen=n)
                for m in api_listing.list_models(pipeline_tag=args.tag, sort="likes"):
                    buf.append(m.modelId)
                repo_ids = list(buf)
            else:
                repo_ids = [m.modelId for m in api.list_models(pipeline_tag=args.tag, sort="likes", limit=args.limit)]

        the_total_repos = len(repo_ids)

        if using_manual_range:
            # clamp end to the actual list size just in case they passed a number that is too big
            the_start_index = args.start - 1
            the_end_index   = min(args.end, the_total_repos)

            if the_start_index >= the_total_repos:
                print(f"error: --start {args.start} is beyond the total repo count ({the_total_repos})")
                return

            repo_ids = repo_ids[the_start_index:the_end_index]
            print(f"Manual range: repos {args.start:,}–{the_end_index:,} of {the_total_repos:,} total ({len(repo_ids):,} repos)")

            the_vm_label = (
                f"{args.tag} ({args.type}) -- manual range\n"
                f"Repos {args.start:,}-{the_end_index:,} ({len(repo_ids):,} repos)\n\n"
            )

        elif using_instance_split:
            the_chunk_size  = the_total_repos // args.total_instances
            the_remainder   = the_total_repos % args.total_instances
            the_start_index = (args.instance - 1) * the_chunk_size + min(args.instance - 1, the_remainder)
            the_end_index   = the_start_index + the_chunk_size + (1 if args.instance <= the_remainder else 0)

            repo_ids = repo_ids[the_start_index:the_end_index]
            print(f"Instance {args.instance} of {args.total_instances}: repos {the_start_index + 1:,}–{the_end_index:,} of {the_total_repos:,} total ({len(repo_ids):,} repos)")

            the_vm_label = (
                f"Instance {args.instance}/{args.total_instances} | {args.tag} ({args.type})\n"
                f"Repos {the_start_index + 1:,}-{the_end_index:,} ({len(repo_ids):,} repos)\n\n"
            )

        else:
            print(f"Found {the_total_repos:,} repos. Starting scan...")
            the_vm_label = (
                f"{args.tag} ({args.type})\n"
                f"{the_total_repos:,} repos\n\n"
            )

        queue.build(repo_ids, resolved_type) # save the list to queue so next restart skips the HF fetch
        db_for_sync = ScanLogDB(os.path.join("data", the_db_name))         # pre-mark anything already in the scan db as done so we dont re-scan it
        the_already_scanned = db_for_sync.get_all_scanned_ids()
        if len(the_already_scanned) > 0:
            queue.mark_done_batch(the_already_scanned)
            print(f"  Pre-marked {len(the_already_scanned):,} already-scanned repos as done in queue")

        repo_ids, the_queue_total, the_queue_done = queue.get_pending(args.order)
        print(f"  {len(repo_ids):,} pending / {the_queue_total:,} total ({the_queue_done:,} already done)")

        # update vm_label now that we have real counts
        if using_manual_range:
            the_vm_label = (
                f"{args.tag} ({args.type}) -- manual range\n"
                f"Repos {args.start:,}-{args.end:,} ({len(repo_ids):,} pending of {the_queue_total:,})\n\n"
            )
        elif using_instance_split:
            the_vm_label = (
                f"Instance {args.instance}/{args.total_instances} | {args.tag} ({args.type})\n"
                f"{len(repo_ids):,} pending of {the_queue_total:,} total\n\n"
            )
        else:
            the_vm_label = (
                f"{args.tag} ({args.type})\n"
                f"{len(repo_ids):,} pending of {the_queue_total:,} total\n\n"
            )

    db = ScanLogDB(os.path.join("data", the_db_name))

    pbar = tqdm(total=the_queue_total, initial=the_queue_done, unit="repo", dynamic_ncols=True)
    malicious = []
    sem = Semaphore(args.workers)
    the_permanent_queue_outcomes = {"clean", "malicious", "gated", "not_found", "disabled", "revision_not_found", "no_supported_files", "download_timeout"}

    if MAX_WORKERS == 1:
        try:
            for rid in repo_ids:
                if STOP_EVENT.is_set(): break
                res = scan_one_repo(rid, resolved_type, db, available, flusher, pbar, sem)
                if res in the_permanent_queue_outcomes:
                    queue.mark_done(rid)
                if res == "malicious":
                    malicious.append(rid)
        except KeyboardInterrupt:
            STOP_EVENT.set()
            kill_all_running_downloads()   # stop any downloads still running so they dont keep going in the background
            print("\nStopped.")
    else:
        # parallel
        malicious_lock = threading.Lock()

        def on_future_done(future, rid):
            try:
                res = future.result()
                if res in the_permanent_queue_outcomes:
                    queue.mark_done(rid)
                if res == "malicious":
                    with malicious_lock:
                        malicious.append(rid)
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for rid in repo_ids:
                if STOP_EVENT.is_set(): break
                f = executor.submit(scan_one_repo, rid, resolved_type, db, available, flusher, pbar, sem)
                futures[f] = rid
                f.add_done_callback(lambda fut, r=rid: on_future_done(fut, r))


            try:
                for f in as_completed(futures):
                    pass 
            except KeyboardInterrupt:
                STOP_EVENT.set()
                kill_all_running_downloads() 
                print("\nShutting down worker threads...")

    pbar.close()
    db.summary()
    queue.summary()

    # Final performance stats
    perf = get_scanner_perf_summary()
    if perf:
        print("\nScanner Speeds:")
        for name, data in perf.items():
            print(f"  {name}: {data['avg']:.2f}s avg")

    # flush summary
    flush_stats = flusher.stats()
    if  flush_stats["flush_count"] == 0:
        print("\nNo flushes occurred this run.")
    else:
        print(f"\nFlush summary ({ flush_stats['flush_count']} batch(es)):")
        for  entry in  flush_stats["flush_timings"]:
            print(f"  #{ entry['batch']}  { entry['zip_name']}  "
                  f"{ entry['size_gb']:.2f} GB  { entry['total_s']:.0f}s  "
                  f"(zip { entry['zip_s']:.0f}s / upload { entry['upload_s']:.0f}s / verify { entry['verify_s']:.0f}s)")
        print(f"  Total uploaded: { flush_stats['total_uploaded_gb']:.2f} GB")

    total_seconds = time.monotonic() -  time_started
    print(f"\nTotal run time: {format_runtime(total_seconds)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        STOP_EVENT.set()
        print("\nInterrupted. You can resume later.")
    except Exception:
        traceback.print_exc()