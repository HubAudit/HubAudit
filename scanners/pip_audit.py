import json
import os
import subprocess
from pathlib import Path

from .template import ScannerTemplate, ScanVerdict, SCOPE_PROJECT_FOLDER, SCOPE_FILE_EXTENSION

SEV_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
# CLI: pip-audit -r <file> --format json --progress-spinner off
# rc 0 = no vulnerabilities, 
# rc 1 = vulnerabilities found, 
# rc 2 = operational error (bad requirements, network, etc.)

REQUIREMENTS_NAMES = {
    "requirement.txt",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "requirements-prod.txt",
}

class PipAuditScanner(ScannerTemplate):
    name     = "pip_audit"
    scope  = SCOPE_FILE_EXTENSION
    supported_extensions = {".txt"}
    
    def scan_folder_with_all_files_in_it(self, repo_dir: str) -> list[ScanVerdict]:
        cmd = [
            "pip-audit",
            "--format", "json",
            "--progress-spinner", "off",
            repo_dir,
        ]
        print("running command:", ' '.join(cmd))
        try:
            result = self.run_cmd(cmd)
        except Exception as e:
            return [ScanVerdict(scanner=self.name, flagged=False, severity="info", error=str(e))]
        
         # rc 2 means error (bad requirements, network issues etc)
        if result.returncode == 2:
            return [ScanVerdict(
                scanner=self.name, flagged=False, severity="info",
                error=f"pip-audit error: {result.stderr}",
            )]

        # # debug what i being returned
        # print("stdout:", result.stdout[:500])
        # print("returncode:", result.returncode)

        the_vulns_found   = []
        the_flagged          = False
        the_max_sev          = "info"

        try:
            data = json.loads(result.stdout)
            the_vulns_found, the_flagged, the_max_sev = self._parse_vulns(data)

        except (json.JSONDecodeError, TypeError):
            if result.returncode == 1:
                # full resolution failed -- retry with --no-deps
                print("  pip-audit full run failed -- retrying with --no-deps")
                retry_cmd = cmd[:-1] + ["--no-deps", repo_dir]
                print("running command:", ' '.join(retry_cmd))
                try:
                    result = self.run_cmd(retry_cmd)
                except Exception as e:
                    return [ScanVerdict(scanner=self.name, flagged=False, severity="info", error=str(e))]

                try:
                    data = json.loads(result.stdout)
                    the_vulns_found, the_flagged, the_max_sev = self._parse_vulns(data)
                except (json.JSONDecodeError, TypeError):
                    # --no-deps also failed -- flag with raw output
                    the_raw            = result.stdout or result.stderr
                    the_flagged        = True
                    the_max_sev        = "high"
                    the_vulns_found = [{"raw_output": the_raw}]

        return [ScanVerdict(
            scanner  = self.name,
            flagged  = the_flagged,
            severity = the_max_sev if the_flagged else "info",
            details  = {
                "vulnerabilities_count": len(the_vulns_found),
                "vulnerabilities":       the_vulns_found[:50],
                "returncode":            result.returncode,
            },
        )]

    def scanner_applies_to_format(self, file_path: str) -> bool:
        the_file_name  = Path(file_path).name.lower()
        the_file_extension = Path(file_path).suffix.lower()
        if the_file_extension != ".txt":
            return False
        if the_file_name not in REQUIREMENTS_NAMES:
            return False
        return True

    def health_check(self) -> tuple[bool, str]:
        try:
            r = self.run_cmd(["pip-audit", "--version"], tool_timeout=30)
            if r.returncode == 0:
                return True, r.stdout.strip().split("\n")[0]
            return False, r.stderr.strip()
        except FileNotFoundError:
            return False, "pip-audit not installed"

    def scan(self, file_path: str) -> ScanVerdict:
        cmd = [
            "pip-audit",
            "-r", file_path,
            "--format", "json",
            "--progress-spinner", "off",
        ]
        print("running command:", ' '.join(cmd))
        try:
            result = self.run_cmd(cmd)
        except Exception as error: # If pip audit tool crashed
            return ScanVerdict(scanner=self.name, flagged=False, severity="info", error=str(error))

        if result.returncode == 2:
            return ScanVerdict(
                scanner=self.name, flagged=False, severity="info",
                error=f"pip-audit error: {result.stderr}",
            )

        vulns   = []
        flagged = False
        max_sev = "info"

        try:
            data = json.loads(result.stdout)
            vulns, flagged, max_sev = self.parse_vulns(data)

        except (json.JSONDecodeError, TypeError): # If pip-audit failed to parse the output that I'm expecting
            if result.returncode == 1:
                print("  pip-audit full run failed -- retrying with --no-deps")
                retry_cmd = cmd + ["--no-deps"]
                print("running command:", ' '.join(retry_cmd))
                try:
                    result = self.run_cmd(retry_cmd)
                except Exception as e:
                    return ScanVerdict(scanner=self.name, flagged=False, severity="info", error=str(e))

                try:
                    data = json.loads(result.stdout)
                    vulns, flagged, max_sev = self.parse_vulns(data)
                except (json.JSONDecodeError, TypeError):
                    # --no-deps also failed -- flag with raw output
                    the_raw = result.stdout or result.stderr
                    flagged = True
                    max_sev = "high"
                    vulns   = [{"raw_output": the_raw}]

        return ScanVerdict(
            scanner  = self.name,
            flagged  = flagged,
            severity = max_sev if flagged else "info",
            details  = {
                "vulnerabilities_count": len(vulns),
                "vulnerabilities":       vulns,
                "returncode":            result.returncode,
            },
        )

    def parse_vulns(self, data):
        the_vulns  = []
        the_flagged = False
        the_max_sev = "info"
        for dep in data.get("dependencies", []):
            for v in dep.get("vulns", []):
                the_cvss    = v.get("metrics", {}).get("cvss3", {})
                the_score   = the_cvss.get("baseScore") if the_cvss else None
                the_sev_str = cvss_to_severity(the_score)
                the_vulns.append({
                    "package":      dep.get("name", ""),
                    "version":      dep.get("version", ""),
                    "id":           v.get("id", ""),
                    "aliases":      v.get("aliases", []),
                    "description":  v.get("description", ""),
                    "fix_versions": v.get("fix_versions", []),
                    "severity":     the_sev_str,
                })
                the_flagged = True
                if SEV_ORDER.get(the_sev_str, 0) > SEV_ORDER.get(the_max_sev, 0):
                    the_max_sev = the_sev_str
        return the_vulns, the_flagged, the_max_sev


def cvss_to_severity(score) -> str:
    if score is None:
        return "high"   # assume high when no score is available
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"
