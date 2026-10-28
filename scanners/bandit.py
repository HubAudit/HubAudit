import json
import os
from pathlib import Path
from .template import SCOPE_PROJECT_FOLDER, ScannerTemplate, ScanVerdict


class BanditScanner(ScannerTemplate):
    name = "bandit"
    scope = SCOPE_PROJECT_FOLDER
    supported_extensions = {".py"}
    tool_timeout         = 300

    def health_check(self) -> tuple[bool, str]:
        try:
            result = self.run_cmd(["bandit", "--version"], tool_timeout=10)
            if result.returncode == 0:
                return True, result.stdout.strip().split("\n")[0]
            return False, result.stderr.strip()
        except FileNotFoundError:
            return False, "bandit not installed"

    def scan_folder_with_all_files_in_it(self, repo_dir: str) -> list[ScanVerdict]:
        
        the_files_to_scan = self.pre_folder_scan_check(repo_dir)
        if len(the_files_to_scan) == 0:
            print("bandit -- no relevant files found in " + repo_dir + " -- saving startup time by skipping this folder")
            return []
        the_total_py_files = len(the_files_to_scan.get(".py", []))
        print("Running bandit scan on folder " + repo_dir + " -- found " + str(the_total_py_files) + " .py files")
        
        cmd = ["bandit", "-r", "-f", "json", repo_dir]
        
        try:
            result = self.run_cmd(cmd, tool_timeout=self.tool_timeout, ok_codes={0, 1})
            data = json.loads(result.stdout)
            results = data.get("results", [])

            verdicts = []
            for issue in results:
                rel_path = os.path.relpath(issue.get("filename", ""), repo_dir)

                # bandit uses LOW/MEDIUM/HIGH for severity
                sev = issue.get("issue_severity", "LOW").lower()
                if sev == "critical":
                    the_sev = "critical"
                elif sev == "high":
                    the_sev = "high"
                elif sev == "medium":
                    the_sev = "medium"
                else:
                    the_sev = "low"

                verdict = ScanVerdict(
                    scanner  = self.name,
                    flagged  = True,
                    severity = the_sev,
                    details  = {
                        "confidence": (issue.get("issue_confidence") or "LOW").lower(),
                        "file":       rel_path,
                        "message":    issue.get("issue_text"),
                        "line":       issue.get("line_number"),
                    }
                )
                verdicts.append(verdict)
            return verdicts

        except Exception as error:
            return [ScanVerdict(self.name, False, "info", error=str(error))]

    def scan(self, file_path: str) -> ScanVerdict:
        try:
            cmd = ["bandit", "-f", "json", file_path]
            result = self.run_cmd(cmd, tool_timeout=self.tool_timeout, ok_codes={0, 1})
            data = json.loads(result.stdout)
            results = data.get("results", [])

            verdicts = []
            for issue in results:
                rel_path = os.path.relpath(issue.get("filename", ""), file_path)

                sev = (issue.get("issue_severity") or "LOW").lower()
                the_sev = sev if sev in {"high", "medium", "low"} else "low"

                verdict = ScanVerdict(
                    scanner  = self.name,
                    flagged  = True,
                    severity = the_sev,
                    details  = {
                        "confidence": (issue.get("issue_confidence") or "LOW").lower(),
                        "file":       rel_path,
                        "message":    issue.get("issue_text"),
                        "line":       issue.get("line_number"),
                    }
                )
                verdicts.append(verdict)
            return verdicts

        except Exception as error:
            return [ScanVerdict(self.name, False, "info", error=str(error))]
