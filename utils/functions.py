import os
import threading
import time
import signal
import atexit
import psutil
import requests
from threading import Event

# ---- constants ----

SPACE_LIMIT_GB = 3 #20 3
SPACE_LIMIT_BYTES = SPACE_LIMIT_GB * 1024 * 1024 * 1024
HF_ENDPOINT = "https://huggingface.co"
DOWNLOAD_ENDPOINT = "https://huggingface.co"
MAX_TREE_DEPTH = 6
STOP_EVENT = Event()
the_live_download_processes = set()
the_download_proc_lock = threading.Lock()
the_download_worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hf_download_worker.py")


def kill_all_running_downloads():
    with the_download_proc_lock:
        the_processes_to_kill = list(the_live_download_processes)
    for one_download_process in the_processes_to_kill:
        try:
            os.killpg(os.getpgid(one_download_process.pid), signal.SIGKILL)
        except Exception:
            try:
                one_download_process.kill()
            except Exception:
                pass

atexit.register(kill_all_running_downloads)


def check_disk_space(flusher=None):
    try:
        usage = psutil.disk_usage(".")
        free_gb = usage.free / (1024 ** 3)
        used_pct = usage.percent
    except:
        usage = psutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        used_pct = usage.percent

    if usage.free > SPACE_LIMIT_BYTES:
        return True

    print(f"\n{'='*60}")
    print(f"DISK SPACE LOW - {free_gb:.1f} GB free ({used_pct:.0f}% used)")

    if flusher is not None:
        print(f"  Attempting emergency flush to free space...")
        try:
            flusher.force_flush()
        except Exception as the_flush_error:
            print(f"  Emergency flush failed: {the_flush_error}")

        try:
            usage_after = psutil.disk_usage(".")
        except:
            usage_after = psutil.disk_usage("/")

        free_gb_after = usage_after.free / (1024 ** 3)

        if usage_after.free > SPACE_LIMIT_BYTES:
            print(f"  Emergency flush worked -- {free_gb_after:.1f} GB free now, continuing...")
            print(f"{'='*60}\n")
            return True
        
        print(f"  Still only {free_gb_after:.1f} GB free after flush -- trying local zip cleanup...")
        if flusher is not None:
            freed_bytes = flusher.cleanup_local_zips()
            if freed_bytes > 0:
                print(f"  Freed {freed_bytes / (1024**3):.2f} GB from local zips")
                try:
                    usage_final = psutil.disk_usage(".")
                except Exception:
                    usage_final = psutil.disk_usage("/")
                if usage_final.free > SPACE_LIMIT_BYTES:
                    free_final = usage_final.free / (1024 ** 3)
                    print(f"  Recovered -- {free_final:.1f} GB free, continuing...")
                    print(f"{'='*60}\n")
                    return True
                print(f"  Still {usage_final.free / (1024**3):.1f} GB free after zip cleanup -- stopping.")

    print(f"    Stopping gracefully. Progress saved to sqlite.")
    print(f"{'='*60}\n")
    STOP_EVENT.set()
    return False


def check_space_for_incoming(incoming_bytes: int, flusher=None) -> bool:
    try:
        free_bytes = psutil.disk_usage(".").free
    except Exception:
        free_bytes = psutil.disk_usage("/").free

    if free_bytes - incoming_bytes >= SPACE_LIMIT_BYTES:
        return True

    incoming_gb = incoming_bytes / (1024 ** 3)
    free_gb     = free_bytes     / (1024 ** 3)
    needed_gb   = incoming_gb + SPACE_LIMIT_GB
    print(f"\n  Pre-download space check: {free_gb:.1f} GB free, need {needed_gb:.1f} GB "
          f"({incoming_gb:.1f} GB download + {SPACE_LIMIT_GB} GB buffer)")

    if flusher is not None:
        print(f"  Flushing staging to make room for download...")
        try:
            flusher.force_flush()
        except Exception as flush_err:
            print(f"  Flush failed: {flush_err}")

        try:
            free_bytes = psutil.disk_usage(".").free
        except Exception:
            free_bytes = psutil.disk_usage("/").free

        if free_bytes - incoming_bytes >= SPACE_LIMIT_BYTES:
            print(f"  Flush freed enough space ({free_bytes/(1024**3):.1f} GB free) -- proceeding with download")
            return True

        freed = flusher.cleanup_local_zips()
        if freed > 0:
            print(f"  Cleared {freed/(1024**3):.2f} GB of local zips")
            try:
                free_bytes = psutil.disk_usage(".").free
            except Exception:
                free_bytes = psutil.disk_usage("/").free
            if free_bytes - incoming_bytes >= SPACE_LIMIT_BYTES:
                print(f"  Enough space after zip cleanup ({free_bytes/(1024**3):.1f} GB free) -- proceeding")
                return True

    print(f"  Not enough space for {incoming_gb:.1f} GB download even after flush -- skipping local scan for this repo")
    return False


def format_runtime(seconds):
    total_secs = int(seconds)
    days = total_secs // 86400
    hrs  = (total_secs % 86400) // 3600
    mins = (total_secs % 3600) // 60
    secs = total_secs % 60
    if days > 0:
        return f"{days}d {hrs}h {mins}m {secs}s"
    elif hrs > 0:
        return f"{hrs}h {mins}m {secs}s"
    else:
        return f"{mins}m {secs}s"


def fetch_tree_recursive(repo_id, repo_type, request_semaphore, subdirectory_path="", branch_name="main", current_depth=0, api_call_counter=None):    
    # Initialize counter on first call (using list for mutability across recursion)
    if api_call_counter is None:
        api_call_counter = [0]
    
    # Safety check 1: Prevent traversing too deep into nested directories
    if current_depth > MAX_TREE_DEPTH:
        return []
    
    # Safety check 2: Limit total API calls to avoid rate limiting or excessive requests
    if api_call_counter[0] > 50:
        return []

    # Determine which Hugging Face API endpoint to use based on repository type
    api_endpoint_type = "datasets" if repo_type == "dataset" else "models"
    
    # Build the API URL for the current directory path
    path = f"/{subdirectory_path}" if subdirectory_path else ""
    api_url = f"{HF_ENDPOINT}/api/{api_endpoint_type}/{repo_id}/tree/{branch_name}{path}?expand=True"
    api_call_counter[0] += 1
    api_response = hf_request("GET", api_url, request_semaphore)
    
    if not api_response or api_response.status_code != 200:
        return []
    directory_entries = api_response.json()
    collected_files = []
    
    for entry in directory_entries:
        entry_type = entry.get("type", "")
        entry_path = entry.get("path", "")
        
        if entry_type == "directory":
            subdirectory_files = fetch_tree_recursive(
                repo_id, repo_type, request_semaphore, 
                entry_path, branch_name, current_depth + 1, api_call_counter
            )
            collected_files.extend(subdirectory_files)
        else:
            collected_files.append(entry)
    
    return collected_files

last_429_time = 0.0
backoff_level = 0
backoff_lock = threading.Lock()
BACKOFF_QUIET_SEC = 300
BACKOFF_EXTRA_SECS = [5, 15, 30, 60, 120, 240]

def hf_request(method, url, semaphore, retries=5):
    global last_429_time, backoff_level

    headers = {}
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(retries):
        if STOP_EVENT.is_set():
            # print("stop event set, aborting request")
            return None

        with backoff_lock:
            seconds_since_last_429 = time.time() - last_429_time
            current_backoff_level = backoff_level

        if current_backoff_level > 0 and seconds_since_last_429 < BACKOFF_QUIET_SEC:
            delay = BACKOFF_EXTRA_SECS[min(current_backoff_level - 1, len(BACKOFF_EXTRA_SECS) - 1)]
            print(f"  rate limit cooldown, waiting {delay}s (backoff level {current_backoff_level})")
            if STOP_EVENT.wait(delay):
                return None
        try:
            with semaphore:
                # print(f"  sending request (attempt {attempt+1})...")
                response = requests.request(method, url, timeout=60, headers=headers)
                # print(f"  got response: {response.status_code}")
        except Exception as request_error:
            print(f"  request failed ({type(request_error).__name__}), retry {attempt+1}/{retries}")
            wait = 2 ** attempt
            STOP_EVENT.wait(wait)
            continue

        if response.status_code == 429:
            with backoff_lock:
                last_429_time = time.time()
                backoff_level = min(backoff_level + 1, len(BACKOFF_EXTRA_SECS))
            print(f"  hit rate limit, backoff now at level {backoff_level}")
            STOP_EVENT.wait(10)
            continue

        if response.status_code >= 500:
            print(f"  server error {response.status_code}, retrying...")
            STOP_EVENT.wait(2 ** attempt)
            continue

        # print(f"  ok: {response.status_code}")
        return response
    # print(f"all {retries} retries failed for {url}")
    return None