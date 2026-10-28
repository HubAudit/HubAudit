import csv
import glob
import json
import os
import shutil
import datetime

output_folder = "llm_batches"
final_csv = "LLM_output.csv"
per_file_csv = "LLM_output_per_file.csv"

manifest = json.load(open(output_folder + "/manifest.json", encoding="utf-8"))
print("requests in the manifest:", len(manifest))


# ---- read every raw answer, keyed by custom_id ----
raw_files = sorted(glob.glob(output_folder + "/batch_output_*.jsonl"))
if not raw_files:
    print("no batch_output_*.jsonl files found - run batch_fetch.py first")
    raise SystemExit

answer_for_id = {}
for one_raw_file in raw_files:
    for one_line in open(one_raw_file, encoding="utf-8"):
        cleaned_line = one_line.strip()
        if not cleaned_line:
            continue
        one_result = json.loads(cleaned_line)
        custom_id = one_result.get("custom_id", "?")
        response = one_result.get("response")
        if response is not None and response.get("status_code") == 200:
            answer_for_id[custom_id] = response["body"]["choices"][0]["message"]["content"]
        else:
            answer_for_id[custom_id] = None
print("answers read:", len(answer_for_id))


# ---- turn each answer into verdict + reason ----
rank_of_verdict = {"Malicious (likely)": 3, "Risky": 2, "Safe": 1, "Unknown": 0}


def parse_answer(answer_text):
    """(verdict, status, reason) for one LLM answer. answer_text is None if the request errored."""
    if answer_text is None:
        return "Unknown", "RECHECK", "no answer from the LLM (missing from the output or the request errored)"

    answer_line = ""
    for one_line in answer_text.split("\n"):
        if one_line.strip().lower().startswith("answer:"):
            answer_line = one_line.split(":", 1)[1].strip().upper()
            break

    if "MALICIOUS" in answer_line:
        verdict = "Malicious (likely)"
    elif "RISKY" in answer_line:
        verdict = "Risky"
    elif "SAFE" in answer_line:
        verdict = "Safe"
    else:
        verdict = "Unknown"

    reason_position = answer_text.lower().find("reason:")
    if reason_position != -1:
        reason = answer_text[reason_position + 7:].strip().replace("\n", " ")
    else:
        reason = answer_text.strip().replace("\n", " ")

    status = "RECHECK" if verdict == "Unknown" or "RECHECK" in answer_text.upper() else ""
    return verdict, status, reason


per_file_rows = []
files_by_repo = {}
cluster_info_for_repo = {}
repo_order = []

for custom_id, info in manifest.items():
    verdict, status, reason = parse_answer(answer_for_id.get(custom_id))
    row = {
        "custom_id": custom_id,
        "repo_id": info["repo_id"],
        "file": info["file"],
        "verdict": verdict,
        "status": status,
        "reason": reason,
        "full_answer": answer_for_id.get(custom_id),
    }
    per_file_rows.append(row)

    if info["repo_id"] not in files_by_repo:
        files_by_repo[info["repo_id"]] = []
        cluster_info_for_repo[info["repo_id"]] = info
        repo_order.append(info["repo_id"])
    files_by_repo[info["repo_id"]].append(row)


# ---- one row per repo, worst file verdict wins ----
repo_rows = []
for repo_id in repo_order:
    file_rows = files_by_repo[repo_id]
    worst_row = max(file_rows, key=lambda r: rank_of_verdict[r["verdict"]])
    any_recheck = any(r["status"] == "RECHECK" for r in file_rows)

    repo_rows.append({
        "repo_id": repo_id,
        "cluster_rank": cluster_info_for_repo[repo_id]["cluster_rank"],
        "suppressed_message": cluster_info_for_repo[repo_id]["suppressed_message"],
        "verdict": worst_row["verdict"],
        "status": "RECHECK" if any_recheck else "",
        "reason": f"{worst_row['reason']} [{len(file_rows)} file(s) reviewed, worst: {worst_row['file'].split('/')[-1]}]",
    })

not_reviewable_count = 0
if os.path.exists(output_folder + "/not_reviewable.csv"):
    with open(output_folder + "/not_reviewable.csv", encoding="utf-8", newline="") as f:
        for one_row in csv.DictReader(f):
            repo_rows.append({
                "repo_id": one_row["repo_id"],
                "cluster_rank": one_row["cluster_rank"],
                "suppressed_message": one_row["suppressed_message"],
                "verdict": "Not reviewable",
                "status": "",
                "reason": one_row["reason"],
            })
            not_reviewable_count += 1

repo_rows.sort(key=lambda x: (int(x["cluster_rank"]), x["repo_id"]))


# # ---- keep a backup of the old LLM_output.csv before writing the new one ----
# if os.path.exists(final_csv):
#     backup_name = "LLM_output.BACKUP_before_batch_parse_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
#     shutil.copy(final_csv, backup_name)
#     print("backed up the old", final_csv, "->", backup_name)

# with open(final_csv, "w", encoding="utf-8", newline="") as out_file:
#     writer = csv.DictWriter(out_file, fieldnames=["repo_id", "cluster_rank", "suppressed_message", "verdict", "status", "reason"])
#     writer.writeheader()
#     writer.writerows(repo_rows)

# with open(per_file_csv, "w", encoding="utf-8", newline="") as out_file:
#     writer = csv.DictWriter(out_file, fieldnames=["custom_id", "repo_id", "file", "verdict", "status", "reason", "full_answer"])
#     writer.writeheader()
#     writer.writerows(per_file_rows)

# counts = {}
# for one_row in repo_rows:
#     counts[one_row["verdict"]] = counts.get(one_row["verdict"], 0) + 1
# print("saved", final_csv, "with", len(repo_rows), "repos (", not_reviewable_count, "not reviewable )")
# print("verdicts:", counts)
# print("saved", per_file_csv, "with", len(per_file_rows), "files")
