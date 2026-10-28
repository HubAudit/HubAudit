import json
import os
import subprocess
from .template import ScannerTemplate, ScanVerdict, SCOPE_PROJECT_FOLDER


class TrivyConfigScanner(ScannerTemplate):
    name  = "trivy"
    scope  = SCOPE_PROJECT_FOLDER

    supported_extensions = {
        ".yaml", ".yml", ".tf", ".tfvars",
        ".hcl", ".toml"
    }
  
#   From https://github.com/aquasecurity/trivy/blob/main/docs/guide/coverage/language/index.md
    manifest = {
        # python
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-prod.txt",
        "requirements-test.txt",
        "requirements-staging.txt",
        "requirements-base.txt",
        "dev-requirements.txt",
        "test-requirements.txt",
        "pipfile.lock",
        "poetry.lock",
        "uv.lock",

        # node -- package.json is image/rootfs only so NOT here
        "package-lock.json",
        "yarn.lock",
        "bun.lock",
        # pnpm-lock.yaml already caught by .yaml extension

        # php -- installed.json is image/rootfs only so NOT here
        "composer.lock",

        "packages.lock.json",
        "packages.config",

        # container / infra
        "dockerfile",
        "containerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "helmfile.yaml",
        ".helmignore",
    }

    # suffix patterns from the trivy docs -- cant do exact name match for these
    manifest_suffixes = (
        ".deps.json",        # dotnet -- *.deps.json
        "packages.props",    # dotnet -- *Packages.props
    )

    def __init__(self, severity: str = "MEDIUM,HIGH,CRITICAL"):
        self.severity = severity

    def scanner_applies_to_format(self, file_path: str) -> bool:
        the_file_name = os.path.basename(file_path).lower()
        the_file_extension = os.path.splitext(file_path)[1].lower()

        if the_file_name in self.manifest:
            return True

        for the_suffix in self.manifest_suffixes:
            if the_file_name.endswith(the_suffix):
                return True

        if the_file_extension not in self.supported_extensions:
            return False

        return True

    def scan_folder_with_all_files_in_it(self, repo_dir: str) -> list[ScanVerdict]:
        the_files_to_scan = self.pre_folder_scan_check(repo_dir)
        if len(the_files_to_scan) == 0:
            print("trivy -- no relevant files found in " + repo_dir + " -- skipping")
            return []

        the_total_file_count = 0
        for the_files in the_files_to_scan.values():
            the_total_file_count = the_total_file_count + len(the_files)

        cmd = [
            "trivy", "fs",
            "--scanners", "vuln,secret,misconfig",
            "--format", "json",
            "--severity", self.severity,
            "--exit-code", "1",
            repo_dir,
        ]
        print("trivy -- found " + str(the_total_file_count) + " relevant files -- scanning whole folder once")
        print("running command: " + " ".join(cmd))

        try:
            the_result = self.run_cmd(cmd, ok_codes={0, 1})
        except FileNotFoundError:
            return [ScanVerdict(scanner=self.name, flagged=False, severity="info", error="trivy not installed")]
        except subprocess.TimeoutExpired:
            return [ScanVerdict(scanner=self.name, flagged=False, severity="info", error="trivy folder scan timed out")]

        the_list_of_all_verdicts = []

        try:
            the_parsed = json.loads(the_result.stdout)
            all_the_results = the_parsed.get("Results", [])
        except (json.JSONDecodeError, TypeError):
            return the_list_of_all_verdicts

        for one_result in all_the_results:
            the_target     = one_result.get("Target", "")
            the_findings   = []
            is_this_flagged    = False
            the_worst_sev_here = "info"

            # misconfigurations -- yaml, dockerfile, tf etc
            for mc in one_result.get("Misconfigurations", []):
                the_sev = mc.get("Severity", "UNKNOWN").upper()
                the_findings.append({
                    "type":        "misconfig",
                    "id":          mc.get("ID", ""),
                    "title":       mc.get("Title", ""),
                    "description": mc.get("Description", "")[:300],
                    "severity":    the_sev,
                    "resolution":  mc.get("Resolution", "")[:200],
                    "references":  mc.get("References", [])[:3],
                })
                is_this_flagged, the_worst_sev_here = update_sev(is_this_flagged, the_worst_sev_here, the_sev)

            for v in one_result.get("Vulnerabilities", []):
                the_sev = v.get("Severity", "UNKNOWN").upper()
                the_findings.append({
                    "type":        "vuln",
                    "id":          v.get("VulnerabilityID", ""),
                    "package":     v.get("PkgName", ""),
                    "version":     v.get("InstalledVersion", ""),
                    "title":       v.get("Title", ""),
                    "severity":    the_sev,
                    "fix_version": v.get("FixedVersion", ""),
                })
                is_this_flagged, the_worst_sev_here = update_sev(is_this_flagged, the_worst_sev_here, the_sev)

            # secrets -- hardcoded tokens, keys etc
            for s in one_result.get("Secrets", []):
                the_sev = s.get("Severity", "UNKNOWN").upper()
                the_findings.append({
                    "type":     "secret",
                    "rule_id":  s.get("RuleID", ""),
                    "title":    s.get("Title", ""),
                    "severity": the_sev,
                })
                is_this_flagged, the_worst_sev_here = update_sev(is_this_flagged, the_worst_sev_here, the_sev)

            # skip targets with no findings at all -- no point adding a clean verdict per file
            if len(the_findings) == 0:
                continue


            if os.path.isabs(the_target):
                the_relative_path = os.path.relpath(the_target, repo_dir)
            else:
                the_relative_path = the_target

            one_file_verdict = ScanVerdict(
                scanner  = self.name,
                flagged  = is_this_flagged,
                severity = the_worst_sev_here if is_this_flagged else "info",
                details  = {
                    "file":           the_relative_path,
                    "findings_count": len(the_findings),
                    "findings":       the_findings[:200],
                    "returncode":     the_result.returncode,
                },
            )
            the_list_of_all_verdicts.append(one_file_verdict)

        # print("trivy folder scan done -- total file verdicts built:", len(the_list_of_all_verdicts))
        return the_list_of_all_verdicts

   

    def health_check(self) -> tuple[bool, str]:
        try:
            r = self.run_cmd(["trivy", "version"], tool_timeout=15)
            if r.returncode == 0:
                ver = r.stdout.strip().split("\n")[0]
                return True, ver
            return False, r.stderr.strip()
        except FileNotFoundError:
            return False, "trivy not installed"

    
    def scan(self, file_path: str) -> ScanVerdict:
        cmd = [
                    "trivy", "fs",
                    "--scanners", "vuln,secret,misconfig",
                    "--format", "json",
                    "--severity", self.severity,
                    "--exit-code", "1",
                    file_path,
                ]
        print("running command:", ' '.join(cmd))
        try:
            result = self.run_cmd(
                cmd,
                ok_codes={0, 1},
            )
        except FileNotFoundError:
            return ScanVerdict(
                scanner=self.name, flagged=False, severity="info",
                error="trivy not installed",
            )
        except subprocess.TimeoutExpired:
            return ScanVerdict(
                scanner=self.name, flagged=False, severity="info",
                error="trivy fs scan timed out",
            )

        findings = []
        flagged  = False
        max_sev  = "info"

        try:
            data = json.loads(result.stdout)
            results = data.get("Results", [])

            for res in results:
                # misconfigurations -- yaml/tf/dockerfile issues
                for mc in res.get("Misconfigurations", []):
                    sev = mc.get("Severity", "UNKNOWN").upper()
                    findings.append({
                        "type":        "misconfig",
                        "id":          mc.get("ID", ""),
                        "title":       mc.get("Title", ""),
                        "description": mc.get("Description", "")[:300],
                        "severity":    sev,
                        "resolution":  mc.get("Resolution", "")[:200],
                        "references":  mc.get("References", [])[:3],
                    })
                    flagged, max_sev = update_sev(flagged, max_sev, sev)

                # vulnerabilities -- package-lock.json, package.json etc
                for v in res.get("Vulnerabilities", []):
                    sev = v.get("Severity", "UNKNOWN").upper()
                    findings.append({
                        "type":        "vuln",
                        "id":          v.get("VulnerabilityID", ""),
                        "package":     v.get("PkgName", ""),
                        "version":     v.get("InstalledVersion", ""),
                        "title":       v.get("Title", ""),
                        "severity":    sev,
                        "fix_version": v.get("FixedVersion", ""),
                    })
                    flagged, max_sev = update_sev(flagged, max_sev, sev)

                # secrets -- tokens or keys accidentally committed
                for s in res.get("Secrets", []):
                    sev = s.get("Severity", "UNKNOWN").upper()
                    findings.append({
                        "type":     "secret",
                        "rule_id":  s.get("RuleID", ""),
                        "title":    s.get("Title", ""),
                        "severity": sev,
                    })
                    flagged, max_sev = update_sev(flagged, max_sev, sev)

        except (json.JSONDecodeError, TypeError):
            if result.returncode == 1:
                flagged = True
                max_sev = "high"

        return ScanVerdict(
            scanner  = self.name,
            flagged  = flagged,
            severity = max_sev if flagged else "info",
            details  = {
                "file":           file_path,   # routes verdict to file_results like opengrep/bandit
                "findings_count": len(findings),
                "findings":       findings,
                "returncode":     result.returncode,
            },
        )


def update_sev(flagged: bool, current_max: str, new_sev: str) -> tuple[bool, str]:
    #  keeping track of the highest severity we have seen so far
    the_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    the_sev_lower = new_sev.lower()
    if new_sev in ("CRITICAL", "HIGH", "MEDIUM"):
        flagged = True
    if the_order.get(the_sev_lower, 0) > the_order.get(current_max, 0):
        current_max = the_sev_lower
    return flagged, current_max