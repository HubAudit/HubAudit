import os
import json
import csv
import sqlite3
import re


# =====================================================================================
# WHAT THIS SCRIPT DOES - it goes in 4 stages (same as in HubAudit paper):
#
#   STAGE 1: Filtering and Base Risk Scoring
#            keep only the repos the scan said were malicious (each repo once), read every detection
#            and give it S_base (how risky the scanner + severity is) and M_agr (how many scanners agree)
#
#   STAGE 2: Noise Suppression
#            mark the detections that are known noise (assert, try/except/pass, ...) so they dont count
#
#   STAGE 3: Malicious-Indicator Amplification

#   STAGE 4: Repository Clustering and Ranking
#            each repo gets its top finding + total score.

# =====================================================================================


# the scan databases (one per task category, text generation is split in 4 on the D: drive)
# careful - if the D: drive isnt plugged in those 4 just get skipped and the text generation repos are missing
list_of_all_databases = [
    ('Dataset', 'Feature Extraction',   r'C:\Users\anonymous\Downloads\Experiment\Dataset\Feature-Extraction\data\scan_log_feature-extraction.db'),
    ('Dataset', 'Image Classification', r'C:\Users\anonymous\Downloads\Experiment\Dataset\Image-Classification\data\scan_log_image-classification.db'),
    ('Dataset', 'Image Segmentation',   r'C:\Users\anonymous\Downloads\Experiment\Dataset\Image-Segmentation\data\scan_log_image-segmentation.db'),
    ('Dataset', 'Text Classification',  r'C:\Users\anonymous\Downloads\Experiment\Dataset\text-classification\data\scan_log_text-classification.db'),
    ('Dataset', 'Text Generation',      r'C:\Users\anonymous\Downloads\Experiment\Dataset\text-generation\data\scan_log_text-generation.db'),
    ('Model',   'Feature Extraction',   r'C:\Users\anonymous\Downloads\Experiment\Model\feature-extraction\data\scan_log_feature-extraction.db'),
    ('Model',   'Image Classification', r'C:\Users\anonymous\Downloads\Experiment\Model\Image-classification\data\scan_log_image-classification.db'),
    ('Model',   'Image Segmentation',   r'C:\Users\anonymous\Downloads\Experiment\Model\Image-Segmentation\data\scan_log_image-segmentation.db'),
    ('Model',   'Text Classification',  r'C:\Users\anonymous\Downloads\Experiment\Model\Text-classification\data\scan_log_text-classification.db'),

    ('Model',   'Text Generation',      r'D:\Experiment\Model\text-generation\1to100000\data\scan_log_text-generation_1to100000.db'),
    ('Model',   'Text Generation',      r'D:\Experiment\Model\text-generation\100001to148000\data\scan_log_text-generation_100001to148000.db'),
    ('Model',   'Text Generation',      r'D:\Experiment\Model\text-generation\148000to278000\data\scan_log_text-generation_148000to278000.db'),
    ('Model',   'Text Generation',      r'D:\Experiment\Model\text-generation\278000to370162\data\scan_log_text-generation_278000to370162.db'),

    # ('HFscan',  'HF scan',              r'C:\Users\anonymous\Downloads\Experiment\Hfscan\scan_log_hf_rescan.db'),
]
code_scanners = ["bandit", "opengrep", "modelaudit"]
dependency_scanners = ["pip_audit", "pysentry", "trivy"]




# ---- STAGE 1 setting: S_base = how risky each scanner + severity is 

base_score_table = {
    "opengrep critical":   60,
    "bandit critical":     50,
    "bandit high":         30,
    "opengrep high":       20,
    "trivy critical":      15,
    "trivy high":          10,
    "bandit medium":       10,
    "opengrep medium":      8,
    "bandit low":           1,
    "pysentry critical":    1,   
    "pip_audit high":       1,
    "modelaudit critical":  1,
    "modelaudit info":      1,
}


# ---- STAGE 2 setting: messages that are known noise ----
noise_messages_to_suppress = [
    "Use of assert detected",
    "Try, Except, Pass detected.",
    "automatic-memory-pinning",
    "try-except-pass",
    "request without timeout",
    "Unsafe Hugging Face Hub download without revision pinning",
    "This code contains bidirectional (bidi) characters",
    "GGUF parse error",
    "Use of unsafe PyTorch load",
    "Functions reliant on pickle can result in arbitrary code execution",
    "Avoid using `pickle",
    "PyTorch is a Python package that provides tensor computation with strong GPU acceleration and deep neural",
    "Usage of NumPy library inside PyTorch `ConvNeXt` module was found. Avoid mixing these libraries for efficiency and prope",
    "Try, Except, Continue detected",
    "Possible hardcoded password",
    "without timeout",
    "GGUF metadata parse error: Array too large:",
    "Suspicious metadata value for key",
    "GGUF tensor parse error",
    "Pickle and modules that wrap it can be unsafe",
    "Standard pseudo-random generators are not suitable",
    "Usage of NumPy library inside PyTorch",
]
noise_file_names = ["zero_to_fp32.py"]


#STAGE 3 setting: malware signals, grouped in categories ----
malicious_signal_categories = {
    # running code / commands
    "code execution": [
        "exec(", "eval(", "os.system", "subprocess", "subprocess.run", "subprocess.Popen", "shell=True",
        "pickle.loads", "pickle.load", "marshal.loads", "yaml.load", "torch.load", "weights_only=False", "__reduce__",
        # "globals", "locals",  -
        "importlib", "__import__",
        "powershell", "cmd.exe", "bash", "shell",
        "/bin/sh", "/bin/bash",
    ],

    # hiding what the code does
    "obfuscation": [
        "base64", "b64encode", "b64decode", "base64.b64decode",
        "encrypt", "decrypt", "cipher", "cryptography", "AES", "RSA", "Fernet",
        "obfuscate", "obfuscated",
    ],

    # talking to the internet
    "network": [
        "requests.get", "requests.post", "urllib", "urllib.request", "urlopen", "http.client",
        "socket", "socket.connect", "socket.send", "socket.recv",
        "ftp", "sftp", "webhook", "wget", "curl", "upload",
    ],

    # stealing secrets
    "secrets": [
        "exfiltrate", "credential", "credentials", "apikey", "cookie",
        "github token", "personal access token", "bearer token", "oauth token",
        "/etc/passwd", "/etc/shadow", "id_rsa", ".ssh", "authorized_keys", "known_hosts",
        "aws_access_key", "private_key",
    ],

    # spying + staying on the machine + file permissions
    "spying / persistence": [
        "keylogger", "keyboard.Listener", "pynput", "clipboard", "pyperclip",
        "chmod", "chown",
        "persistence", "registry", "schtasks", "cron", "startup", "autorun",
    ],

    # malware words
    "malware words": [
        "backdoor", "trigger", "laundering", "evasion", "poc",
        "payload", "dropper", "remote code execution", "malicious",
        "reverse shell", "bind shell",
        "os.dup2", "pty.spawn",
        "trojan", "ransomware", "spyware", "botnet", "cryptominer",
    ],
}

file_names_that_run_on_load = ["modeling", "tokenization", "configuration", "processing", "image_processing", "feature_extraction"]
group_name = "ALL - combined"
file_name_part = "ALL_combined"

print("")
print("STAGE 1: Filtering and Base Risk Scoring")

#  FILTERING - only the repos the scan said were malicious, and every repo only once ----
malicious_rows = []
repo_ids_already_seen = {}
duplicate_repos_skipped = 0

for each_database in list_of_all_databases:
    source_type = each_database[0]
    scan_log_db = each_database[2]

    # if source_type == "HFscan":
    #     print("skipping the HF rescan db, its repos are already in the other dbs")
    #     continue

    if os.path.exists(scan_log_db) == False:
        print("cant find the database at " + scan_log_db + " - skipping it")
        continue

    conn = sqlite3.connect("file:" + scan_log_db + "?mode=ro", uri=True)
    rows_from_this_db = conn.execute("SELECT repo_id, files_flagged, details FROM scans WHERE outcome = 'malicious'").fetchall()
    conn.close()
    print("malicious repos in " + os.path.basename(scan_log_db) + ":", len(rows_from_this_db))

    for each_row in rows_from_this_db:
        if each_row[0] in repo_ids_already_seen:
            duplicate_repos_skipped = duplicate_repos_skipped + 1
            continue
        repo_ids_already_seen[each_row[0]] = True
        malicious_rows.append((each_row[0], each_row[1], each_row[2], scan_log_db))

print("duplicate repos skipped (already seen in another db):", duplicate_repos_skipped)
print("malicious repos (unique):", len(malicious_rows))
if len(malicious_rows) == 0:
    print("no malicious repos found, nothing to do")
    exit()


all_repos = []
repos_with_bad_details = 0

for each_row in malicious_rows:
    repo_id = each_row[0]
    files_flagged_from_db = each_row[1]
    details_text = each_row[2]

    try:
        data = json.loads(details_text)
    except Exception:
        print("couldnt read details for " + repo_id)
        repos_with_bad_details = repos_with_bad_details + 1
        continue

    verdicts_in_this_repo = []

    for each_file_result in data.get("file_results", []):
        if each_file_result.get("flagged", False) == False:
            continue

        file_name = each_file_result.get("file_name", "")
        file_path = each_file_result.get("file_path", file_name)

        scanners_on_this_file = each_file_result.get("flagged_by", [])
        if len(scanners_on_this_file) >= 3:
            m_agr = 2.0
        elif len(scanners_on_this_file) == 2:
            m_agr = 1.5
        else:
            m_agr = 1.0

        for each_verdict in each_file_result.get("verdicts", []):
            if each_verdict.get("flagged", False) == False:
                continue

            scanner = each_verdict.get("scanner", "")
            severity = each_verdict.get("severity", "")
            details = each_verdict.get("details", {})
            if details == None:
                details = {}

            if scanner in code_scanners:
                finding_type = "code"
            elif scanner in dependency_scanners:
                finding_type = "dependency"
            else:
                finding_type = "other"

            detections_in_this_verdict = []
            error_text = ""
            if scanner == "pysentry":
                if details.get("vulnerabilities_count", 0) == 0:  # crashed / timed out
                    error_text = "pysentry crashed or found nothing (returncode " + str(details.get("returncode", "")) + ", 0 vulnerabilities)"
                for each_vuln in details.get("vulnerabilities", []):
                    one_detection = str(each_vuln.get("description", "")) + " " + str(each_vuln.get("id", "")) + " " + str(each_vuln.get("summary", ""))
                    vuln_id = str(each_vuln.get("id", ""))
                    # use the CVE number if there is one so the same CVE from different scanners matches up
                    aliases = each_vuln.get("aliases", [])
                    if isinstance(aliases, list):
                        for each_alias in aliases:
                            if str(each_alias).startswith("CVE-"):
                                vuln_id = str(each_alias)
                                break
                    detections_in_this_verdict.append({
                        "text": one_detection,
                        "package": str(each_vuln.get("package_name", "")),
                        "vuln_id": vuln_id,
                        "vuln_severity": str(each_vuln.get("severity", severity)).lower(),
                    })
            elif scanner == "bandit":
                detections_in_this_verdict.append({"text": str(details.get("message", "")), "package": "", "vuln_id": "", "vuln_severity": "", "line": details.get("line", "")})
            elif scanner == "opengrep":
                for each_finding in details.get("findings", []):
                    one_detection = str(each_finding.get("message", "")) + " " + str(each_finding.get("snippet", "")) + " " + str(each_finding.get("rule_id", ""))
                    detections_in_this_verdict.append({"text": one_detection, "package": "", "vuln_id": "", "vuln_severity": "", "code_to_check": str(each_finding.get("snippet", "")), "line": each_finding.get("line", "")})
            elif scanner == "modelaudit":
                for each_issue in details.get("issues", []):
                    detections_in_this_verdict.append({"text": str(each_issue.get("description", "")), "package": "", "vuln_id": "", "vuln_severity": ""})
            elif scanner == "pip_audit":
                for each_vuln in details.get("vulnerabilities", []):
                    one_detection = str(each_vuln.get("description", "")) + " " + str(each_vuln.get("id", ""))
                    vuln_id = str(each_vuln.get("id", ""))
                    aliases = each_vuln.get("aliases", [])
                    if isinstance(aliases, list):
                        for each_alias in aliases:
                            if str(each_alias).startswith("CVE-"):
                                vuln_id = str(each_alias)
                                break
                    detections_in_this_verdict.append({
                        "text": one_detection,
                        "package": str(each_vuln.get("package", "")),
                        "vuln_id": vuln_id,
                        "vuln_severity": str(each_vuln.get("severity", severity)).lower(),
                    })
                    raw_output = str(each_vuln.get("raw_output", ""))
                    if raw_output != "":
                        for each_line in raw_output.split("\n"):
                            if "ERROR" in each_line:
                                error_text = error_text + " " + each_line.strip()
                        if error_text.strip() == "":
                            error_text = raw_output.replace("\n", " ")
            elif scanner == "trivy":
                for each_finding in details.get("findings", []):
                    one_detection = str(each_finding.get("title", "")) + " " + str(each_finding.get("id", "")) + " " + str(each_finding.get("package", "")) + " " + str(each_finding.get("rule_id", ""))
                    detections_in_this_verdict.append({
                        "text": one_detection,
                        "package": str(each_finding.get("package", "")),
                        "vuln_id": str(each_finding.get("id", "")),
                        "vuln_severity": str(each_finding.get("severity", severity)).lower(),
                    })

            # throw away the empty ones
            non_empty_detections = []
            for each_detection in detections_in_this_verdict:
                if each_detection["text"].strip() != "":
                    each_detection["text"] = each_detection["text"].strip()
                    non_empty_detections.append(each_detection)

            # no usable text at all = the scanner crashed or gave nothing back (it gets kept as an error row in stage 4)
            if len(non_empty_detections) == 0:
                if error_text.strip() == "":
                    error_text = scanner + " flagged this file but gave no details"

            scanner_and_severity = scanner + " " + severity
            if scanner_and_severity in base_score_table:
                s_base = base_score_table[scanner_and_severity]
            else:
                s_base = 0

            verdicts_in_this_repo.append({
                "file_name": file_name,
                "file_path": file_path,
                "scanner": scanner,
                "severity": severity,
                "finding_type": finding_type,
                "s_base": s_base,
                "m_agr": m_agr,
                "error_text": error_text.strip(),
                "detections": non_empty_detections,
            })

    all_repos.append({
        "repo_id": repo_id,
        "files_flagged": files_flagged_from_db,
        "source_dir": os.path.dirname(os.path.dirname(each_row[3])),
        "verdicts": verdicts_in_this_repo,
    })

print("repos read:", len(all_repos))
print("repos with broken details:", repos_with_bad_details)



# STAGE 2: Noise Suppression
print("")
print("STAGE 2: Noise Suppression")

noise_detections_count = 0
real_detections_count = 0

for each_repo in all_repos:
    for each_verdict in each_repo["verdicts"]:
        for each_detection in each_verdict["detections"]:
            text = each_detection["text"]

            was_filtered = False
            # is it one of the noise messages?
            for each_noise_message in noise_messages_to_suppress:
                if each_noise_message in text:
                    was_filtered = True
            # or is it in a file thats all noise?
            for each_noise_file in noise_file_names:
                if each_noise_file in each_verdict["file_name"]:
                    was_filtered = True

            if was_filtered == True:
                each_detection["was_suppressed"] = "yes"
                noise_detections_count = noise_detections_count + 1
            else:
                each_detection["was_suppressed"] = "no"
                real_detections_count = real_detections_count + 1

print("detections suppressed as noise:", noise_detections_count)
print("real detections left:", real_detections_count)



# STAGE 3: Malicious-Indicator Amplification
#          S_final = S_base x M_mal x M_agr      (for every real detection)

print("STAGE 3: Malicious-Indicator Amplification")

detections_with_2_or_more_signals = 0

for each_repo in all_repos:
    for each_verdict in each_repo["verdicts"]:

        runs_on_model_load_score = 1.0
        just_the_file_name = os.path.basename(each_verdict["file_name"]).lower()
        for start_of_name in file_names_that_run_on_load:
            if just_the_file_name.startswith(start_of_name) == True and just_the_file_name.endswith(".py") == True:
                runs_on_model_load_score = 3.0

        for each_detection in each_verdict["detections"]:
            if each_detection["was_suppressed"] == "yes":
                continue

            text = each_detection["text"]
            if each_verdict["finding_type"] == "dependency":
                code_to_check = ""
            else:
                code_to_check = each_detection.get("code_to_check", text)

            # now go through every category and every keyword in it
            keywords_found_in_this_detection = []
            categories_found_in_this_detection = []
            for each_category in malicious_signal_categories:
                for each_keyword in malicious_signal_categories[each_category]:
                    keyword_is_in_the_code = False
                    if each_keyword.isalpha() == True:
                        # had to google this - \b means the edge of a word
                        # so "poc" doesnt match inside "epoch" and "cron" doesnt match inside "acronym"
                        if re.search(r"\b" + re.escape(each_keyword) + r"\b", code_to_check) != None:
                            keyword_is_in_the_code = True
                    else:
                        # words with dots or brackets like "exec(" or "os.system" - normal check is fine for these
                        if each_keyword in code_to_check:
                            keyword_is_in_the_code = True

                    if keyword_is_in_the_code == True:
                        if each_keyword not in keywords_found_in_this_detection:
                            keywords_found_in_this_detection.append(each_keyword)
                        # the category only counts once even if 3 of its words are there
                        if each_category not in categories_found_in_this_detection:
                            categories_found_in_this_detection.append(each_category)

            how_many_categories = len(categories_found_in_this_detection)
            if how_many_categories >= 3:
                signal_mix_multiplier = 10.0
            elif how_many_categories == 2:
                signal_mix_multiplier = 5.0
            else:
                signal_mix_multiplier = 1.0
            if how_many_categories >= 2:
                detections_with_2_or_more_signals = detections_with_2_or_more_signals + 1

            m_mal = signal_mix_multiplier * runs_on_model_load_score
            # the formula
            s_final = each_verdict["s_base"] * m_mal * each_verdict["m_agr"]
            # print("S_base", each_verdict["s_base"], "x M_mal", m_mal, "x M_agr", each_verdict["m_agr"], "=", s_final)

            each_detection["m_mal"] = m_mal
            each_detection["s_final"] = s_final
            each_detection["signals"] = ", ".join(categories_found_in_this_detection)
            each_detection["keywords"] = ", ".join(keywords_found_in_this_detection)

print("detections with 2 or more malware signals mixed:", detections_with_2_or_more_signals)



# STAGE 4: Repository Clustering and Ranking
print("STAGE 4: Repository Clustering and Ranking")

all_results = []
total_scanner_errors = 0

for each_repo in all_repos:
    total_score = 0
    code_score = 0
    dependency_score = 0
    scanners_that_fired = []
    best_code_finding = ""
    best_code_finding_score = 0
    best_filtered_finding = ""
    best_filtered_score = 0
    worst_severity = ""
    worst_code_severity = ""
    all_findings_for_this_repo = []
    every_finding_with_details = []
    scanner_errors_in_this_repo = 0

    # the top detection, and the 3 parts of its score so i can see WHY it got that score in the csv
    top_detection_text = ""
    top_detection_score = 0
    top_detection_s_base = 0
    top_detection_m_mal = 1.0
    top_detection_m_agr = 1.0
    top_detection_signals = ""
    top_detection_keywords = ""

    for each_verdict in each_repo["verdicts"]:
        scanner = each_verdict["scanner"]
        severity = each_verdict["severity"]
        finding_type = each_verdict["finding_type"]

        # no detections = the scanner crashed, keep it as an error row
        if len(each_verdict["detections"]) == 0:
            every_finding_with_details.append({
                "file_name": each_verdict["file_name"],
                "file_path": each_verdict["file_path"],
                "scanner": scanner,
                "severity": severity,
                "finding_type": finding_type,
                "package": "",
                "vuln_id": "",
                "finding_score": 0,
                "was_suppressed": "scanner_error",
                "finding_text": each_verdict["error_text"][:500],
            })
            scanner_errors_in_this_repo = scanner_errors_in_this_repo + 1
            continue

        real_detections_in_this_verdict = []
        best_score_in_this_verdict = 0

        for each_detection in each_verdict["detections"]:
            text = each_detection["text"]

            # noise from stage 2 - keep the best one in case the repo has nothing else, but it doesnt count
            if each_detection["was_suppressed"] == "yes":
                if each_verdict["s_base"] > best_filtered_score or best_filtered_finding == "":
                    best_filtered_finding = text[:120]
                    best_filtered_score = each_verdict["s_base"]
                every_finding_with_details.append({
                    "file_name": each_verdict["file_name"],
                    "file_path": each_verdict["file_path"],
                    "scanner": scanner,
                    "severity": severity,
                    "finding_type": finding_type,
                    "package": each_detection["package"],
                    "vuln_id": each_detection["vuln_id"],
                    "line": each_detection.get("line", ""),
                    "finding_score": each_verdict["s_base"],
                    "was_suppressed": "yes",
                    "finding_text": text[:500],
                })
                continue

            real_detections_in_this_verdict.append(text)
            detection_score = each_detection["s_final"]

            # the best one in this verdict - the verdict counts in the total with this
            if detection_score > best_score_in_this_verdict:
                best_score_in_this_verdict = detection_score

            # is this the new top detection for the whole repo? the highest S_final wins
            if top_detection_text == "" or detection_score > top_detection_score:
                top_detection_text = text.strip()[:120]
                top_detection_score = detection_score
                top_detection_s_base = each_verdict["s_base"]
                top_detection_m_mal = each_detection["m_mal"]
                top_detection_m_agr = each_verdict["m_agr"]
                top_detection_signals = each_detection["signals"]
                top_detection_keywords = each_detection["keywords"]

            # dependency rows use the CVE's own severity (more useful than the verdict severity)
            if finding_type == "dependency" and each_detection["vuln_severity"] != "":
                row_severity = each_detection["vuln_severity"]
            else:
                row_severity = severity

            every_finding_with_details.append({
                "file_name": each_verdict["file_name"],
                "file_path": each_verdict["file_path"],
                "scanner": scanner,
                "severity": row_severity,
                "finding_type": finding_type,
                "package": each_detection["package"],
                "vuln_id": each_detection["vuln_id"],
                "line": each_detection.get("line", ""),
                "finding_score": round(detection_score, 1),
                "was_suppressed": "no",
                "finding_text": text[:500],
            })

        # everything in this verdict was noise - it doesnt count
        if len(real_detections_in_this_verdict) == 0:
            continue

        # the verdict counts once in the total, with its best detection's S_final
        score = best_score_in_this_verdict
        total_score = total_score + score
        text = " ".join(real_detections_in_this_verdict)

        # keep code and dependency scores apart too
        if finding_type == "code":
            code_score = code_score + score
            if score > best_code_finding_score or best_code_finding == "":
                best_code_finding = text[:120]
                best_code_finding_score = score
            if severity == "critical":
                worst_code_severity = "critical"
            elif severity == "high" and worst_code_severity != "critical":
                worst_code_severity = "high"
            elif severity == "medium" and worst_code_severity not in ("critical", "high"):
                worst_code_severity = "medium"
            elif severity == "low" and worst_code_severity == "":
                worst_code_severity = "low"
        else:
            dependency_score = dependency_score + score

        # which scanners fired across this whole repo
        if scanner not in scanners_that_fired:
            scanners_that_fired.append(scanner)

        # the worst severity seen so far
        if severity == "critical":
            worst_severity = "critical"
        elif severity == "high" and worst_severity != "critical":
            worst_severity = "high"
        elif severity == "medium" and worst_severity not in ("critical", "high"):
            worst_severity = "medium"
        elif severity == "low" and worst_severity == "":
            worst_severity = "low"

        this_finding_text = str(text).strip()[:120]
        if this_finding_text not in all_findings_for_this_repo:
            all_findings_for_this_repo.append(this_finding_text)

    total_scanner_errors = total_scanner_errors + scanner_errors_in_this_repo

    final_finding_to_show = top_detection_text
    if final_finding_to_show == "" and best_filtered_finding != "":
        final_finding_to_show = "[SUPPRESSED] " + best_filtered_finding
    if final_finding_to_show == "":
        if scanner_errors_in_this_repo > 0:
            final_finding_to_show = "[SUPPRESSED] scanners crashed - no real findings"
        else:
            final_finding_to_show = "[SUPPRESSED] marked malicious but no flagged verdicts"

    all_results.append({
        "repo_id":              each_repo["repo_id"],
        "total_score":          round(total_score, 1),
        "top_finding_score":    round(top_detection_score, 1),
        "top_finding_s_base":   top_detection_s_base,
        "top_finding_m_mal":    top_detection_m_mal,
        "top_finding_m_agr":    top_detection_m_agr,
        "top_finding_signals":  top_detection_signals,
        "top_finding_keywords": top_detection_keywords,
        "top_finding":          final_finding_to_show,
        "code_score":           round(code_score, 1),
        "dependency_score":     round(dependency_score, 1),
        "worst_severity":       worst_severity,
        "worst_code_severity":  worst_code_severity,
        "scanners":             ", ".join(scanners_that_fired),
        "top_code_finding":     best_code_finding,
        "all_findings":         all_findings_for_this_repo,
        "every_finding":        every_finding_with_details,
        "scanner_errors":       scanner_errors_in_this_repo,
        "files_flagged":        each_repo["files_flagged"],
        "source_dir":           each_repo["source_dir"],
    })

# highest total first (the review worklist at the end uses this order)
all_results.sort(key=lambda x: x["total_score"], reverse=True)

print("repos scored:", len(all_results))
print("scanner errors kept as rows:", total_scanner_errors)


# - OVERALL RANK - every repo ranked by its OWN top finding S_final, across all the clusters ----
repos_by_their_own_score = sorted(all_results, key=lambda x: (x["top_finding_score"], x["total_score"]), reverse=True)
overall_rank_of_each_repo = {}
overall_rank_counter = 1
for each_result in repos_by_their_own_score:
    overall_rank_of_each_repo[each_result["repo_id"]] = overall_rank_counter
    overall_rank_counter = overall_rank_counter + 1
print("number 1 overall:", repos_by_their_own_score[0]["repo_id"], "with S_final", repos_by_their_own_score[0]["top_finding_score"])


# ---- CLUSTERING - repos whose top detections matches the same way go in the same cluster ----
print("now grouping similar findings together...")

grouped_findings = {}

for each_result in all_results:
    finding_text = each_result["top_finding"]
    group_key = finding_text[:30]

    if group_key not in grouped_findings:
        grouped_findings[group_key] = {
            "count": 0,
            "total_score": 0,
            "best_top_score": -1,
            "repos": [],
            "full_message": finding_text,
        }

    grouped_findings[group_key]["count"] = grouped_findings[group_key]["count"] + 1
    grouped_findings[group_key]["total_score"] = grouped_findings[group_key]["total_score"] + each_result["total_score"]

    # the cluster gets ranked by its BEST repo's top finding S_final
    if each_result["top_finding_score"] > grouped_findings[group_key]["best_top_score"]:
        grouped_findings[group_key]["best_top_score"] = each_result["top_finding_score"]

    grouped_findings[group_key]["repos"].append({
        "repo_id": each_result["repo_id"],
        "overall_rank": overall_rank_of_each_repo[each_result["repo_id"]],
        "score": each_result["total_score"],
        "top_score": each_result["top_finding_score"],
        "s_base": each_result["top_finding_s_base"],
        "m_mal": each_result["top_finding_m_mal"],
        "m_agr": each_result["top_finding_m_agr"],
        "signals": each_result["top_finding_signals"],
        "keywords": each_result["top_finding_keywords"],
        "top_finding": finding_text,
        "scanners": each_result["scanners"],
    })

print("grouped into " + str(len(grouped_findings)) + " clusters")


# -- RANKING - clusters by their best S_final, and repos inside each cluster by their own S_final ----
sorted_clusters = []
for group_key in grouped_findings:
    sorted_clusters.append(grouped_findings[group_key])

sorted_clusters.sort(key=lambda x: (x["best_top_score"], x["total_score"]), reverse=True)

# the main output - one row per repo, grouped by cluster
detailed_output_file = "cluster_top_findings_" + file_name_part + ".csv"

with open(detailed_output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["cluster_rank", "cluster_type", "finding_pattern", "repos_affected_in_cluster", "cluster_total_score", "cluster_best_top_finding_score", "repo_rank_in_cluster", "repo_overall_rank", "repo_id", "repo_top_finding_score", "repo_s_base", "repo_m_mal", "repo_m_agr", "repo_signals_matched", "repo_keywords_matched", "repo_top_finding", "repo_score", "scanners", "manual_review_status", "manual_review_detail"])
    writer.writeheader()

    cluster_rank_of_each_repo = {}
    cluster_rank = 1
    for each_cluster in sorted_clusters:
        repos_sorted = sorted(each_cluster["repos"], key=lambda x: (x["top_score"], x["score"]), reverse=True)

        if each_cluster["full_message"].startswith("[SUPPRESSED] scanners crashed"):
            cluster_type = "suppressed - scanner crashed"
        elif each_cluster["full_message"].startswith("[SUPPRESSED]"):
            cluster_type = "suppressed - noise"
        else:
            cluster_type = "normal"

        repo_rank_in_cluster = 1
        for each_repo in repos_sorted:
            cluster_rank_of_each_repo[each_repo["repo_id"]] = cluster_rank
            writer.writerow({
                "cluster_rank": cluster_rank,
                "cluster_type": cluster_type,
                "finding_pattern": each_cluster["full_message"][:150],
                "repos_affected_in_cluster": each_cluster["count"],
                "cluster_total_score": round(each_cluster["total_score"], 1),
                "cluster_best_top_finding_score": round(each_cluster["best_top_score"], 1),
                "repo_rank_in_cluster": repo_rank_in_cluster,
                "repo_overall_rank": each_repo["overall_rank"],
                "repo_id": each_repo["repo_id"],
                "repo_top_finding_score": round(each_repo["top_score"], 1),
                "repo_s_base": each_repo["s_base"],
                "repo_m_mal": each_repo["m_mal"],
                "repo_m_agr": each_repo["m_agr"],
                "repo_signals_matched": each_repo["signals"],
                "repo_keywords_matched": each_repo["keywords"],
                "repo_top_finding": each_repo["top_finding"],
                "repo_score": round(each_repo["score"], 1),
                "scanners": each_repo["scanners"],
                "manual_review_status": "",
                "manual_review_detail": "",
            })
            repo_rank_in_cluster = repo_rank_in_cluster + 1

        cluster_rank = cluster_rank + 1

print("saved " + detailed_output_file)

cluster_overview_file = "cluster_overview_" + file_name_part + ".csv"
with open(cluster_overview_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["cluster_rank", "cluster_type", "repos_in_cluster", "cluster_total_score", "cluster_best_top_finding_score", "top_repo", "finding_pattern"])
    writer.writeheader()
    cluster_rank = 1
    for each_cluster in sorted_clusters:
        if each_cluster["full_message"].startswith("[SUPPRESSED] scanners crashed"):
            cluster_type = "suppressed - scanner crashed"
        elif each_cluster["full_message"].startswith("[SUPPRESSED]"):
            cluster_type = "suppressed - noise"
        else:
            cluster_type = "normal"
        # the top repo is the first one when the repos are sorted the same way as in the detailed file
        repos_in_this_cluster_sorted = sorted(each_cluster["repos"], key=lambda x: (x["top_score"], x["score"]), reverse=True)
        best_repo_in_cluster = repos_in_this_cluster_sorted[0]["repo_id"]
        writer.writerow({
            "cluster_rank": cluster_rank,
            "cluster_type": cluster_type,
            "repos_in_cluster": each_cluster["count"],
            "cluster_total_score": round(each_cluster["total_score"], 1),
            "cluster_best_top_finding_score": round(each_cluster["best_top_score"], 1),
            "top_repo": best_repo_in_cluster,
            "finding_pattern": each_cluster["full_message"][:150],
        })
        cluster_rank = cluster_rank + 1
print("saved " + cluster_overview_file + " (" + str(len(sorted_clusters)) + " clusters)")

print("")
print("top 25 clusters by score:")
print("rank".rjust(5) + "  " + "repos".rjust(6) + "  " + "S_final".rjust(10) + "  pattern")
how_many_to_print = 25
if len(sorted_clusters) < how_many_to_print:
    how_many_to_print = len(sorted_clusters)
for i in range(how_many_to_print):
    each_cluster = sorted_clusters[i]
    print(str(i + 1).rjust(5) + "  " + str(each_cluster["count"]).rjust(6) + "  " + str(round(each_cluster["best_top_score"], 1)).rjust(10) + "  " + each_cluster["full_message"][:90])

# and the biggest ones by how many repos are in them
clusters_by_size = sorted(sorted_clusters, key=lambda x: x["count"], reverse=True)
print("")
print("top 25 clusters by number of repos:")
print("repos".rjust(6) + "  " + "score".rjust(10) + "  pattern")
for i in range(how_many_to_print):
    each_cluster = clusters_by_size[i]
    print(str(each_cluster["count"]).rjust(6) + "  " + str(round(each_cluster["total_score"], 1)).rjust(10) + "  " + each_cluster["full_message"][:90])






# AFTER THE 4 STAGES - SUMMARY + REVIEW WORKLIST

normal_repos = 0
suppressed_repos = 0
suppressed_repos_noise = 0
suppressed_repos_crashed = 0
normal_files = 0
suppressed_files = 0
suppressed_files_noise = 0
suppressed_files_crashed = 0
# detections = every single row (one CVE / one rule hit), a file can have lots of them
real_detections = 0
suppressed_detections = 0
crashed_detections = 0

for each_result in all_results:
    for each_finding in each_result["every_finding"]:
        if each_finding["was_suppressed"] == "no":
            real_detections = real_detections + 1
        elif each_finding["was_suppressed"] == "yes":
            suppressed_detections = suppressed_detections + 1
        else:
            crashed_detections = crashed_detections + 1

    if each_result["top_finding"].startswith("[SUPPRESSED]"):
        suppressed_repos = suppressed_repos + 1
        if each_result["top_finding"].startswith("[SUPPRESSED] scanners crashed"):
            suppressed_repos_crashed = suppressed_repos_crashed + 1
        else:
            suppressed_repos_noise = suppressed_repos_noise + 1
    else:
        normal_repos = normal_repos + 1

    # look at every flagged file in this repo
    what_each_file_had = {}
    for each_finding in each_result["every_finding"]:
        file_path = each_finding["file_path"]
        if file_path not in what_each_file_had:
            what_each_file_had[file_path] = []
        what_each_file_had[file_path].append(each_finding["was_suppressed"])

    for file_path in what_each_file_had:
        if "no" in what_each_file_had[file_path]:
            normal_files = normal_files + 1
        else:
            suppressed_files = suppressed_files + 1
            if "yes" in what_each_file_had[file_path]:
                suppressed_files_noise = suppressed_files_noise + 1
            else:
                suppressed_files_crashed = suppressed_files_crashed + 1

# the clusters split up the same way
normal_clusters = 0
suppressed_clusters = 0
suppressed_clusters_noise = 0
suppressed_clusters_crashed = 0
for each_cluster in sorted_clusters:
    if each_cluster["full_message"].startswith("[SUPPRESSED]"):
        suppressed_clusters = suppressed_clusters + 1
        if each_cluster["full_message"].startswith("[SUPPRESSED] scanners crashed"):
            suppressed_clusters_crashed = suppressed_clusters_crashed + 1
        else:
            suppressed_clusters_noise = suppressed_clusters_noise + 1
    else:
        normal_clusters = normal_clusters + 1

total_clusters = normal_clusters + suppressed_clusters
total_repos = normal_repos + suppressed_repos
total_files = normal_files + suppressed_files
total_detections = real_detections + suppressed_detections + crashed_detections
task_category = group_name

# print it as a table - ljust/rjust pads the text so the columns line up
print("")
print("=== SUMMARY: " + task_category + " ===")
print("")
print("Category".ljust(28) + "Clusters".rjust(10) + "Repos".rjust(8) + "Files".rjust(8) + "Detections".rjust(12))
print("-" * 66)
print("Normal".ljust(28) + str(normal_clusters).rjust(10) + str(normal_repos).rjust(8) + str(normal_files).rjust(8) + str(real_detections).rjust(12))
print("Suppressed".ljust(28) + str(suppressed_clusters).rjust(10) + str(suppressed_repos).rjust(8) + str(suppressed_files).rjust(8) + str(suppressed_detections + crashed_detections).rjust(12))
print("   noise (filtered)".ljust(28) + str(suppressed_clusters_noise).rjust(10) + str(suppressed_repos_noise).rjust(8) + str(suppressed_files_noise).rjust(8) + str(suppressed_detections).rjust(12))
print("   scanner crashed".ljust(28) + str(suppressed_clusters_crashed).rjust(10) + str(suppressed_repos_crashed).rjust(8) + str(suppressed_files_crashed).rjust(8) + str(crashed_detections).rjust(12))
print("-" * 66)
print("Total".ljust(28) + str(total_clusters).rjust(10) + str(total_repos).rjust(8) + str(total_files).rjust(8) + str(total_detections).rjust(12))

# save it as one row per task category
# if this category is already in the file (from running it before) its row gets replaced, not added twice
summary_file = "summary_combined.csv"
summary_columns = ["task_category",
                   "normal_clusters", "normal_repos", "normal_files", "normal_detections",
                   "suppressed_clusters", "suppressed_repos", "suppressed_files", "suppressed_detections",
                   "suppressed_noise_clusters", "suppressed_noise_repos", "suppressed_noise_files", "suppressed_noise_detections",
                   "suppressed_crashed_clusters", "suppressed_crashed_repos", "suppressed_crashed_files", "suppressed_crashed_detections",
                   "total_clusters", "total_repos", "total_files", "total_detections"]

summary_rows = []
if os.path.exists(summary_file) == True:
    f = open(summary_file, "r", encoding="utf-8")
    reader = csv.DictReader(f)
    for each_row in reader:
        # the csv got lined up with spaces in vscode so i strip them off the names and the numbers
        cleaned_row = {}
        for each_key in each_row:
            if each_key == None:
                continue
            each_value = each_row[each_key]
            if each_value == None:
                each_value = ""
            cleaned_row[each_key.strip()] = each_value.strip()
        if cleaned_row.get("task_category", "") == task_category:
            continue
        if cleaned_row.get("task_category", "") == "TOTAL":
            continue
        summary_rows.append(cleaned_row)
    f.close()

summary_rows.append({
    "task_category": task_category,
    "normal_clusters": normal_clusters,
    "normal_repos": normal_repos,
    "normal_files": normal_files,
    "normal_detections": real_detections,
    "suppressed_clusters": suppressed_clusters,
    "suppressed_repos": suppressed_repos,
    "suppressed_files": suppressed_files,
    "suppressed_detections": suppressed_detections + crashed_detections,
    "suppressed_noise_clusters": suppressed_clusters_noise,
    "suppressed_noise_repos": suppressed_repos_noise,
    "suppressed_noise_files": suppressed_files_noise,
    "suppressed_noise_detections": suppressed_detections,
    "suppressed_crashed_clusters": suppressed_clusters_crashed,
    "suppressed_crashed_repos": suppressed_repos_crashed,
    "suppressed_crashed_files": suppressed_files_crashed,
    "suppressed_crashed_detections": crashed_detections,
    "total_clusters": total_clusters,
    "total_repos": total_repos,
    "total_files": total_files,
    "total_detections": total_detections,
})

# ok now add up every category into one TOTAL row at the bottom
# (theres only the combined row right now so TOTAL is the same numbers, but it still sums properly if more get added)
total_row = {"task_category": "TOTAL"}
for each_column in summary_columns:
    if each_column == "task_category":
        continue
    column_total_so_far = 0
    for each_row in summary_rows:
        value_in_this_row = str(each_row.get(each_column, "")).strip()
        # old rows from before some columns existed are blank so i skip those
        if value_in_this_row != "":
            column_total_so_far = column_total_so_far + int(value_in_this_row)
    total_row[each_column] = column_total_so_far
# print("total row:", total_row)

with open(summary_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=summary_columns)
    writer.writeheader()
    for each_row in summary_rows:
        writer.writerow(each_row)
    writer.writerow(total_row)

print("")
print("saved summary row for " + task_category + " to " + summary_file + " (" + str(len(summary_rows)) + " task categories in it now)")


# ---- REVIEW WORKLIST (json) - every repo with its messages, so they can be checked by hand ----
# the suppressed repos are kept too WITH their messages so they can be verified
worklist_json = []
normal_count_in_json = 0
suppressed_count_in_json = 0

for each_result in all_results:
    if each_result["top_finding"].startswith("[SUPPRESSED]"):
        status = "suppressed"
        findings_list = []
        scanners_list = []
        worst_suppressed_severity = ""
        # take the messages that were filtered out or where the scanner crashed
        for each_finding in each_result["every_finding"]:
            message = each_finding["finding_text"][:120]
            if message not in findings_list:
                findings_list.append(message)
            if each_finding["scanner"] not in scanners_list:
                scanners_list.append(each_finding["scanner"])
            if each_finding["severity"] == "critical":
                worst_suppressed_severity = "critical"
            elif each_finding["severity"] == "high" and worst_suppressed_severity != "critical":
                worst_suppressed_severity = "high"
            elif each_finding["severity"] == "medium" and worst_suppressed_severity not in ("critical", "high"):
                worst_suppressed_severity = "medium"
            elif each_finding["severity"] == "low" and worst_suppressed_severity == "":
                worst_suppressed_severity = "low"
        worst_severity_to_show = worst_suppressed_severity
        suppressed_count_in_json = suppressed_count_in_json + 1
    else:
        status = "normal"
        findings_list = each_result["all_findings"]
        # scanners came in as a comma string, turn it back into a list
        scanners_list = []
        if each_result["scanners"] != "":
            for each_scanner in each_result["scanners"].split(","):
                scanners_list.append(each_scanner.strip())
        worst_severity_to_show = each_result["worst_severity"]
        normal_count_in_json = normal_count_in_json + 1

    # ok now the files part - the llm step needs to know WHICH files to read and which lines were flagged
    # one entry per file (full path because the same file name can be in different folders)
    files_dict = {}
    for each_finding in each_result["every_finding"]:
        # scanner errors have no real message so they are not a pointer for the llm
        if each_finding["was_suppressed"] == "scanner_error":
            continue
        this_path = each_finding["file_path"]
        if this_path not in files_dict:
            files_dict[this_path] = []
        files_dict[this_path].append({
            "scanner":  each_finding["scanner"],
            "severity": each_finding["severity"],
            "line":     each_finding.get("line", ""),
            "message":  each_finding["finding_text"][:200],
        })
    files_list = []
    for each_path in files_dict:
        files_list.append({"file_path": each_path, "detections": files_dict[each_path]})
    # print("files for", each_result["repo_id"], len(files_list))

    worklist_json.append({
        "repo_id":        each_result["repo_id"],
        "status":         status,
        "cluster_rank":   cluster_rank_of_each_repo[each_result["repo_id"]],
        "top_finding":    each_result["top_finding"],
        "source_dir":     each_result["source_dir"],
        "files":          files_list,
        "total_score":    each_result["total_score"],
        "worst_severity": worst_severity_to_show,
        "num_findings":   len(findings_list),
        "findings":       findings_list,
        "scanners":       scanners_list,
    })

# already sorted by total score because all_results was sorted, so suppressed ones (score 0) end up at the bottom
worklist_json_file = "review_worklist_db_" + file_name_part + ".json"
with open(worklist_json_file, "w", encoding="utf-8") as out_file:
    json.dump(worklist_json, out_file, indent=2)

print("saved " + worklist_json_file + " (" + str(len(worklist_json)) + " repos - normal: " + str(normal_count_in_json) + ", suppressed: " + str(suppressed_count_in_json) + ")")
print("")
print("all done!")
