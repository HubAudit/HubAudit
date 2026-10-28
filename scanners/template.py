import os
import subprocess
import time
from pathlib import Path

SCOPE_EVERY_FILE     = "every_file"
SCOPE_FILE_EXTENSION = "file_extension"
SCOPE_PROJECT_FOLDER = "project_folder"

class ScanVerdict:
    def __init__(self, scanner, flagged, severity, details=None, error=None, duration=0.0):
        self.scanner  = scanner
        self.flagged  = flagged
        self.severity = severity
        self.details  = details if details is not None else {}
        self.error    = error
        self.duration = duration

class ScannerTemplate:
    name                 = ""     
    scope                = SCOPE_FILE_EXTENSION
    supported_extensions = set()           
    excluded_filenames   = set()            
    excluded_extensions  = set()          
    # max_files_per_ext  = {}            
    is_project_scanner   = False        
    tool_timeout         = 150     
    thread_timeout       = 350       

    def scanner_applies_to_format(self, file_path):
        if not self.supported_extensions:
            return True

        ext  = Path(file_path).suffix.lower()
        name = Path(file_path).name.lower()
        return ext in self.supported_extensions or name in self.supported_extensions

    def pre_folder_scan_check(self, repo_dir):
        files_found_by_ext = {}

        for the_root, the_subdirs_dont_use, the_files in os.walk(repo_dir):
            for the_filename in the_files:
                the_full_path = os.path.join(the_root, the_filename)
                ext = Path(the_filename).suffix.lower()
                the_name_lower = the_filename.lower()

                # skip anything in the excluded extensions list
                if ext in self.excluded_extensions:
                    continue

                # skip excluded filenames too
                if the_name_lower in self.excluded_filenames:
                    continue

                # check if this scanner cares about this extension
                # if supported_extensions is empty we take everything
                if self.supported_extensions:
                    the_matches = (
                        ext in self.supported_extensions
                        or the_name_lower in self.supported_extensions
                    )
                    if the_matches == False:
                        continue

                if ext not in files_found_by_ext:
                    files_found_by_ext[ext] = []

                files_found_by_ext[ext].append(the_full_path)

        return files_found_by_ext

    def timed_scan(self, file_path):
        t0 = time.monotonic()
        verdict = self.scan(file_path)
        verdict.duration = round(time.monotonic() - t0, 3)
        return verdict

    def timed_folder_scan(self, repo_dir):
        t0 = time.monotonic()
        verdicts = self.scan_folder_with_all_files_in_it(repo_dir)
        the_duration = round(time.monotonic() - t0, 3)
        for verdict in verdicts:
            verdict.duration = the_duration
        return verdicts

    def scan(self, file_path):
        return ScanVerdict(self.name, False, "info")

    def scan_folder_with_all_files_in_it(self, repo_dir):
        return []

    def health_check(self):
        return True, ""

    def run_cmd(self, cmd, tool_timeout=300, ok_codes=None):
        if tool_timeout is None:
            timeout = self.tool_timeout
        else:
            timeout = tool_timeout

        if ok_codes is None:
            ok_codes = {0}

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )