import json
from pathlib import Path
from .template import ScannerTemplate, ScanVerdict, SCOPE_FILE_EXTENSION


SEV_MAP = {
    "CRITICAL": "critical",
    "HIGH":     "high",
    "WARNING":  "medium",
    "MEDIUM":   "medium",
    "LOW":      "low",
    "INFO":     "info",
    "DEBUG":    "info",
}


class ModelAuditScanner(ScannerTemplate):
    name  = "modelaudit"
    scope = SCOPE_FILE_EXTENSION
    # files this scanner handles
    supported_extensions = {
        ".gguf",
        # ".safetensors", ".pb", ".onnx", ".pt", ".pth", ".h5",
    }
    tool_timeout = 600

    def scanner_applies_to_format(self, file_path: str) -> bool:
        the_file_extension = Path(file_path).suffix.lower()
        if the_file_extension not in self.supported_extensions:
            return False
        return True

    def health_check(self) -> tuple[bool, str]:
        try:
            result = self.run_cmd(["modelaudit", "--version"], tool_timeout=10)
            the_version = result.stdout.strip() or result.stderr.strip()
            if the_version:
                return True, "modelaudit " + the_version.split("\n")[0]
            return True, "modelaudit available"
        except FileNotFoundError:
            return False, "modelaudit not installed"

    def scan(self, file_path: str) -> ScanVerdict:

        cmd = ["modelaudit", "scan", "--format", "json", "--max-size", "10GB", file_path]
        print("Running modelaudit scan on " + file_path + ":", ' '.join(cmd))

        try:
            # ok_codes includes 2 because modelaudit exits 2 on parse errors
            result = self.run_cmd(cmd, tool_timeout=self.tool_timeout, ok_codes={0, 1, 2})

            the_list_of_issues_found = []
            the_flagged = False
            highest_severity = "info"

            # check stderr for parse errors -- malformed GGUF files show up here
            # things like "Array too large" or "String length exceeds maximum" are red flags
            the_parse_error_keywords = [
                "array too large",
                "string length exceeds",
                "parse error",
                "metadata parse error",
                "exceeds maximum",
            ]
            the_stderr_lower = result.stderr.lower()
            for the_keyword in the_parse_error_keywords:
                if the_keyword in the_stderr_lower:
                    # grab the relevant lines from stderr
                    the_error_lines = [
                        line.strip()
                        for line in result.stderr.splitlines()
                        if the_keyword in line.lower()
                    ]
                    the_list_of_issues_found.append({
                        "severity":    "high",
                        "description": "GGUF parse error -- malformed or malicious file: " + " | ".join(the_error_lines[:3]),
                        "rule_id":     "parse-error",
                        "location":    file_path,
                    })
                    the_flagged = True
                    highest_severity = "high"
                    break

            try:
                data = json.loads(result.stdout)

                the_raw_issues = data.get("issues") or data.get("results") or []

                for each_issue in the_raw_issues:
                    the_raw_sev = str(each_issue.get("severity", "INFO")).upper()
                    the_mapped_sev = SEV_MAP.get(the_raw_sev, "medium")

                    the_description = (
                        each_issue.get("message")
                        or each_issue.get("description")
                        or "")

                    # modelaudit reports "Unknown or unhandled format" when it has no parser
                    # for the file type -- this is a tool limitation not a real finding
                    the_is_unknown_format = (
                        "unknown" in the_description.lower()
                        and "format" in the_description.lower()
                    )

                    the_issue_entry = {
                        "severity":    the_mapped_sev,
                        "description": the_description,
                        "rule_id":     each_issue.get("rule_id") or each_issue.get("id") or "",
                        "location":    each_issue.get("location") or each_issue.get("context") or "",
                    }
                    the_list_of_issues_found.append(the_issue_entry)

                    # only flag for real findings -- not tool limitations
                    if not the_is_unknown_format:
                        the_flagged = True
                        the_sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
                        if the_sev_order.get(the_mapped_sev, 0) > the_sev_order.get(highest_severity, 0):
                            highest_severity = the_mapped_sev

            except (json.JSONDecodeError, TypeError):
                if result.returncode == 1:
                    the_flagged = True
                    highest_severity = "high"
                    the_list_of_issues_found = [{"raw_output": result.stdout.strip()[:2000]}]

            return ScanVerdict(
                scanner  = self.name,
                flagged  = the_flagged,
                severity = highest_severity if the_flagged else "info",
                details  = {
                    "issues_count": len(the_list_of_issues_found),
                    "issues":       the_list_of_issues_found[:50],
                },
            )
            
        except Exception as error:
            return ScanVerdict(self.name, False, "info", error=str(error))    