import json
import subprocess
from pathlib import Path
from sys import exception
from .template import ScannerTemplate, ScanVerdict, SCOPE_PROJECT_FOLDER

MANIFEST_FILES = {
    "requirements.txt",
    "requirement.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "requirements-prod.txt"

    "pyproject.toml", "poetry.lock",
    "uv.lock", "pipfile.lock", "pipfile",
    "pylock.toml",
}


class PySentryScanner(ScannerTemplate):
    name = "pysentry"
    scope = SCOPE_PROJECT_FOLDER
    supported_extensions = MANIFEST_FILES

    def scanner_applies_to_format(self, file_path: str) -> bool:
        the_file_name = Path(file_path).name.lower()

        if the_file_name not in MANIFEST_FILES:
            return False

        return True
        
    def health_check(self) -> tuple[bool, str]:
        try:
            self.run_cmd(["pysentry-rs", "--version"], tool_timeout=10)
            return True, "pysentry-rs available"
        except FileNotFoundError:
            return False, "pysentry-rs not installed"


    def scan_folder_with_all_files_in_it(self, repo_dir: str) -> list[ScanVerdict]:
        the_files_to_scan = self.pre_folder_scan_check(repo_dir)
        if len(the_files_to_scan) == 0:
            print("pysentry -- no manifest files found in " + repo_dir + " -- skipping")
            return []

        all_found_files = []
        for the_ext_or_name in the_files_to_scan:
            all_found_files = all_found_files + the_files_to_scan[the_ext_or_name]
        manifest_found = Path(all_found_files[0]).name if all_found_files else None

        try:
            result = self.run_cmd(
                ["pysentry-rs", "--format", "json", repo_dir],
                ok_codes={0, 1, 2},
            )
            vulns   = []
            flagged = False
            max_sev = "info"

            try:
                data  = json.loads(result.stdout)
                vulns = data.get("vulnerabilities", data.get("results", []))

                if isinstance(vulns, list) and len(vulns) > 0:
                    flagged = True
                    for v in vulns:
                        sev = v.get("severity", "unknown").upper()
                        if sev == "CRITICAL":
                            max_sev = "critical"
                        elif sev == "HIGH" and max_sev != "critical":
                            max_sev = "high"
                        elif sev == "MEDIUM" and max_sev in ("info", "low"):
                            max_sev = "medium"

            except (json.JSONDecodeError, TypeError):
                if result.returncode != 0:
                    flagged = True
                    max_sev = "high"

            return [ScanVerdict(
                scanner  = self.name,
                flagged  = flagged,
                severity = max_sev if flagged else "info",
                details  = {
                    "file":                  manifest_found, 
                    "vulnerabilities_count": len(vulns),
                    "vulnerabilities":       vulns,
                    "returncode":            result.returncode,
                    "scanned_dir":           repo_dir,
                },
            )]

        except Exception as e:
            return [ScanVerdict(
                scanner=self.name, flagged=False, severity="info",
                error="pysentry scan error: " + str(e),
            )]


    def scan(self, file_path: str) -> ScanVerdict:
        repo_dir = str(Path(file_path).parent)

        try:
            result = self.run_cmd(
                ["pysentry-rs", "--format", "json", repo_dir],
                ok_codes={0, 1, 2},
            )

            vulns   = []
            flagged = False
            max_sev = "info"

            try:
                data  = json.loads(result.stdout)
                vulns = data.get("vulnerabilities", data.get("results", []))

                if isinstance(vulns, list) and len(vulns) > 0:
                    flagged = True
                    for v in vulns:
                        sev = v.get("severity", "unknown").upper()
                        if sev == "CRITICAL":
                            max_sev = "critical"
                        elif sev == "HIGH" and max_sev != "critical":
                            max_sev = "high"
                        elif sev == "MEDIUM" and max_sev in ("info", "low"):
                            max_sev = "medium"

            except (json.JSONDecodeError, TypeError):
                if result.returncode != 0:
                    flagged = True
                    max_sev = "high"

            return ScanVerdict(
                scanner  = self.name,
                flagged  = flagged,
                severity = max_sev if flagged else "info",
                details  = {
                    "vulnerabilities_count": len(vulns),
                    "vulnerabilities":       vulns,
                    "returncode":            result.returncode,
                    "scanned_dir":           repo_dir,
                },
            )
            
        except Exception as e:
            return [ScanVerdict(
                scanner=self.name, flagged=False, severity="info",
                error="pysentry scan error: " + str(e),
            )]