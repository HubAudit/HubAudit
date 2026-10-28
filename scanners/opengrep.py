import json
import os
import re
import fnmatch
import subprocess
from pathlib import Path
from .template import ScannerTemplate, ScanVerdict, SCOPE_PROJECT_FOLDER


DEFAULT_RULES_DIR = str(
    Path(__file__).resolve().parent / "rules" / "semgrep"
)

class OpengrepScanner(ScannerTemplate):
    name = "opengrep"
    scope = SCOPE_PROJECT_FOLDER
    tool_timeout = 300
    the_include_patterns = [
        "*.py",
        "*.yaml",
        "*.yml",
        "*.jinja",
        "requirement*.txt", 
        "poetry.lock",
        "uv.lock",
        "pipfile.lock",
        "*.json",
    ]
    the_exclude_patterns = [
        # Binary formats
        "*arrow",            
        "*.parquet",
        "*.gguf",
        
        "*tokenizer*.json",     
        "*tokenizer.json",     
        "tokenizer_config.json",
        "vocab.json",
        # "merges.txt",
    ]
    
    supported_extensions = {
        ".py",
        ".yaml", ".yml", ".json", ".jinja",
    }

    def __init__(self, rules_dir: str = None, use_auto_config: str = "auto"):
        self.rules_dir      = rules_dir or DEFAULT_RULES_DIR
        self.use_auto_config = use_auto_config

    def scanner_applies_to_format(self, file_path):
        the_filename_lower = Path(file_path).name.lower()
        
        for the_exclude_pat in self.the_exclude_patterns:
            if fnmatch.fnmatch(the_filename_lower, the_exclude_pat.lower()):
                return False

        for the_include_pat in self.the_include_patterns:
            if fnmatch.fnmatch(the_filename_lower, the_include_pat.lower()):
                return True

        return False

    def pre_folder_scan_check(self, repo_dir):
        the_files_found_by_ext = {}

        for the_root, _, the_filenames in os.walk(repo_dir):
            for the_filename in the_filenames:
                the_filename_lower = the_filename.lower()

                the_is_excluded = False
                for the_exclude_pat in self.the_exclude_patterns:
                    if fnmatch.fnmatch(the_filename_lower, the_exclude_pat.lower()):
                        the_is_excluded = True
                        break

                if the_is_excluded == True:
                    continue

                the_is_included = False
                for the_include_pat in self.the_include_patterns:
                    if fnmatch.fnmatch(the_filename_lower, the_include_pat.lower()):
                        the_is_included = True
                        break

                if the_is_included == False:
                    continue
                the_full_path = os.path.join(the_root, the_filename)
                the_ext = os.path.splitext(the_filename_lower)[1] or "(none)"

                if the_ext not in the_files_found_by_ext:
                    the_files_found_by_ext[the_ext] = []

                the_files_found_by_ext[the_ext].append(the_full_path)

        return the_files_found_by_ext
        
        
    def health_check(self) -> tuple[bool, str]:
        try:
            self.run_cmd(["opengrep", "--version"], tool_timeout=10)
            return True, "opengrep available"
        except FileNotFoundError:
            return False, "opengrep not installed"

    def scan(self, file_path: str) -> ScanVerdict:
        cmd = [
            "opengrep", "scan",
            "--json",
            "--config", self.use_auto_config,
        #    "--config", self.rules_dir,
            "--timeout", "60",      # per-rule timeout in seconds
            file_path,
        ]         
        
        print(  f"Running opengrep scan on folder {file_path} with command: {' '.join(cmd)}")
        try:
            result = self.run_cmd(cmd, ok_codes={0, 1})
        except Exception as error:
            return ScanVerdict(
                scanner=self.name, flagged=False, severity="info",
                error=f"semgrep scan failed: {str(error)}",
            )

        findings = []
        flagged  = False
        max_sev  = "info"

        try:
            data = json.loads(result.stdout)
            print(f"semgrep scan of {file_path} found {len(data.get('results', []))} results")
            results = data.get("results", [])

            for result in results:
                # Normalize severity into pipeline
                extra = result.get("extra", {})
                sev = result.get("extra", {}).get("severity", "WARNING").upper()

                finding = {
                    "rule_id":  result.get("check_id", "unknown"),
                    "message":  extra.get("message", ""),
                    "severity": sev,
                    "path":     result.get("path", ""),
                    "line":     result.get("start", {}).get("line"),
                    "end_line": result.get("end", {}).get("line"),
                    "snippet":  extra.get("lines", ""),
                    "metadata": extra.get("metadata", {}),
                }
                 # Extract CWE if present
                metadata = extra.get("metadata", {})
                if metadata.get("cwe"):
                    finding["cwe"] = metadata["cwe"]

                findings.append(finding)

                # Map severity
                if sev in ("ERROR", "CRITICAL"):
                    flagged = True
                    max_sev = "critical"
                elif sev == "WARNING":
                    flagged = True
                    if max_sev in ("info", "low", "medium"):
                        max_sev = "high"
                elif sev == "INFO":
                    # INFO findings from Semgrep are usually style/quality
                    # Don't flag as malicious, but record them
                    pass

        except (json.JSONDecodeError, TypeError):
            if result.returncode == 1:
                flagged = True
                max_sev = "high"
                findings = [{"raw_output": result.stdout}]

        return ScanVerdict(
            scanner  = self.name,
            flagged  = flagged,
            severity = max_sev if flagged else "info",
            details  = {
                "findings_count": len(findings),
                "findings":       findings,
                "returncode":     result.returncode,
                # "config":         self.,
            },
        )
        
    def scan_folder_with_all_files_in_it(self, repo_dir):
        the_files_to_scan = self.pre_folder_scan_check(repo_dir)
        if len(the_files_to_scan) == 0:
            print("opengrep -- no relevant files found in " + repo_dir + " -- skipping")
            return []

        # count how many files we are about to scan
        the_total_files_found = 0
        for the_ext_key in the_files_to_scan:
            the_total_files_found = the_total_files_found + len(the_files_to_scan[the_ext_key])
        print("opengrep -- pre-check found " + str(the_total_files_found) + " files to scan")

        cmd = [
            "opengrep", "scan",
            "--json",
            "--jobs", "1",
            "--config", self.use_auto_config,
            # "--config", self.rules_dir,

            "--max-target-bytes", "50000000", # 50MB

            "--timeout", "60",   # to avoid hanging the pipeline on complex rules/files
            "--timeout-threshold", "1",
        ]

        for the_include_pattern in self.the_include_patterns:
            cmd.append("--include")
            cmd.append(the_include_pattern)

        for the_exclude_pattern in self.the_exclude_patterns:
            cmd.append("--exclude")
            cmd.append(the_exclude_pattern)
            
        cmd.append(repo_dir)
                  
        env_for_this_run = os.environ.copy() #
        env_for_this_run["SEMGREP_SEND_METRICS"] = "off"
        env_for_this_run["SEMGREP_VERSION_CHECK_URL"] = ""
        
        print(  f"Running opengrep scan on folder {repo_dir} with command: {' '.join(cmd)}")     
        
        try:
            scan_output = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.tool_timeout,
                env=env_for_this_run,
                cwd=repo_dir,
            )
            # print(f"opengrep scan completed {scan_output}")
 
        except FileNotFoundError:
            return [ScanVerdict(scanner=self.name, flagged=False, severity="info", error="opengrep not installed")]
        except subprocess.TimeoutExpired:
            return [ScanVerdict(scanner=self.name, flagged=False, severity="info", error="opengrep folder scan timed out after 300s")]

        
        the_list_of_all_verdicts = []
        try:
            the_parsed_json = json.loads(scan_output.stdout)
            all_the_raw_findings = the_parsed_json.get("results", [])

        except (json.JSONDecodeError, TypeError):
            return the_list_of_all_verdicts

        #group all the findings by which file they came from
        all_findings_grouped_by_file = {}
        for one_finding in all_the_raw_findings:
            the_file_this_came_from = one_finding.get("path", "")

            if the_file_this_came_from not in all_findings_grouped_by_file:
                all_findings_grouped_by_file[the_file_this_came_from] = []

            all_findings_grouped_by_file[the_file_this_came_from].append(one_finding)

        # print("number of files findings:", len(all_findings_grouped_by_file))

        for full_file_path, the_findings_for_this_file in all_findings_grouped_by_file.items():
            formatted_findings_list = []
            is_this_file_flagged = False
            the_worst_sev = "info"

            for one_raw_result in the_findings_for_this_file:
                the_sev = one_raw_result.get("extra", {}).get("severity", "WARNING").upper()

                one_formatted_finding = {
                    "rule_id":  one_raw_result.get("check_id", "unknown"),
                    "message":  one_raw_result.get("extra", {}).get("message", ""),
                    "severity": the_sev,
                    "line":     one_raw_result.get("start", {}).get("line"),
                    "snippet":  one_raw_result.get("extra", {}).get("lines", "")[:200],
                }
                formatted_findings_list.append(one_formatted_finding)
                if the_sev in ("ERROR", "CRITICAL"):
                    is_this_file_flagged = True
                    the_worst_sev = "critical"
                elif the_sev == "WARNING":
                    is_this_file_flagged = True
                    if the_worst_sev in ("info", "low", "medium"):
                        the_worst_sev = "high"
                
            one_file_verdict = ScanVerdict(
                scanner  = self.name,
                flagged  = is_this_file_flagged,
                severity = the_worst_sev if is_this_file_flagged else "info",
                details  = {
                    "file":           full_file_path,
                    "findings_count": len(formatted_findings_list),
                    "findings":       formatted_findings_list,
                    "returncode":     scan_output.returncode,
                },
            )
            the_list_of_all_verdicts.append(one_file_verdict)

        # print("all doneee -- total verdicts built:", len(the_list_of_all_verdicts))

        return the_list_of_all_verdicts