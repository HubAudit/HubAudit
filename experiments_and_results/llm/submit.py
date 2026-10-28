# step 2 of. step 1 is extract_results_and_cluster_combined.py (makes the clusters + the worklist)
#
# this takes the SUPPRESSED repos from review_worklist_db_ALL_combined.json and builds the batch input for the LLM.


import csv
import glob
import os
import json
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

worklist_file = os.environ.get("WORKLIST_FILE", "../review_worklist_db_ALL_combined.json")
instruction_file = "review_instruction.txt"
output_folder = "llm_batches"
model_name = os.environ.get("OPENAI_MODEL", "gpt-4o")

# yes = Test working before sending to LLM 
dry_run = os.environ.get("DRY_RUN", "yes").strip().lower()
max_repos = int(os.environ.get("MAX_REPOS", "0")) ## FOr bacthes, determin how many you wan to split into
path_find = os.environ.get("SOURCE_PATH_FIND", "")
path_replace = os.environ.get("SOURCE_PATH_REPLACE", "")

# openai batch limits are 50000 requests and 200 MB for one input file - i stay under both
max_requests_per_batch_file = 40000
max_bytes_per_batch_file = 150 * 1024 * 1024

readable_extensions = (".py", ".txt", ".json", ".md", ".cfg", ".ini", ".yaml", ".yml", ".toml", ".sh", ".bat", ".js", ".ts", ".cpp", ".c", ".h", ".java")
max_chars_per_file = 90000
max_detections_per_file = 30

scan_prefix = "/tmp/scan_workspace/"

if not os.path.exists(worklist_file):
    print("cant find the worklist at", worklist_file, "- run extract_results_and_cluster_combined.py first")
    raise SystemExit
if not os.path.exists(instruction_file):
    print("cant find", instruction_file)
    raise SystemExit

instruction_text = open(instruction_file, encoding="utf-8").read()

if dry_run != "yes":
    # this is the safety so i dont pay twice for the same repos by running it again
    if os.path.exists(output_folder + "/batch_state.json"):
        print(output_folder + "/batch_state.json is already there, so this was submitted before.")
        print("move that folder away if you really want to submit again")
        raise SystemExit
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key is None:
        print("no OPENAI_API_KEY found in .env")
        raise SystemExit

os.makedirs(output_folder, exist_ok=True)
print("ok. dry run:", dry_run, " model:", model_name, " max repos:", max_repos)


all_repos_in_worklist = json.load(open(worklist_file, encoding="utf-8"))
print("repos in the worklist:", len(all_repos_in_worklist))
suppressed_repos = [r for r in all_repos_in_worklist if r["status"] == "suppressed"]
print("suppressed repos:", len(suppressed_repos))
suppressed_repos.sort(key=lambda x: (x["cluster_rank"], x["repo_id"]))


list_of_request_lines = []
manifest = {}
not_reviewable_rows = []
repos_selected = 0
total_chars_sent = 0
files_per_repo_counter = {}
flagged_folders_for_source = {}

for one_repo in suppressed_repos:
    repo_id = one_repo["repo_id"]

    if max_repos > 0 and repos_selected >= max_repos:
        break

    source_dir = one_repo["source_dir"]
    if path_find:
        source_dir = source_dir.replace(path_find, path_replace)

    count_not_readable_type = 0
    count_not_on_disk = 0
    requests_for_this_repo = []

    for one_file in one_repo["files"]:
        scan_path = one_file["file_path"]

        inside_path = scan_path[len(scan_prefix):] if scan_path.startswith(scan_prefix) else scan_path
        if not scan_path.lower().endswith(readable_extensions):
            count_not_readable_type += 1
            continue
        
        if source_dir not in flagged_folders_for_source:
            folders_to_try = [os.path.join(source_dir, "flagged")]
            folders_to_try += sorted(glob.glob(os.path.join(os.path.dirname(source_dir), "*", "*_flagged")))
            flagged_folders_for_source[source_dir] = folders_to_try

        local_path = ""
        for one_folder in flagged_folders_for_source[source_dir]:
            maybe_path = os.path.join(one_folder, inside_path.replace("/", os.sep))
            if os.path.isfile(maybe_path):
                local_path = maybe_path
                break
        if not local_path:
            count_not_on_disk += 1
            continue

        seen_findings = []
        for one_detection in one_file["detections"]:
            this_line_number = str(one_detection["line"]) or "?"
            one_text = f"- {one_detection['scanner']} ({one_detection['severity']}) line {this_line_number}: {one_detection['message']}"
            if one_text not in seen_findings:
                seen_findings.append(one_text)

        finding_lines = "".join(t + "\n" for t in seen_findings[:max_detections_per_file])
        if len(seen_findings) > max_detections_per_file:
            finding_lines += f"- (and {len(seen_findings) - max_detections_per_file} more findings not shown)\n"

        file_contents = open(local_path, encoding="utf-8", errors="ignore").read()
        numbered_text = "\n".join(f"{n}: {line}" for n, line in enumerate(file_contents.split("\n"), 1)) + "\n"
        if len(numbered_text) > max_chars_per_file:
            numbered_text = numbered_text[:max_chars_per_file] + "\n...(TRUNCATED)\n"

        user_message = (
            f"Repo: {repo_id}\nFile: {inside_path}\n\n"
            f"Scanner findings for this file (flagged lines and scanner messages):\n{finding_lines}\n"
            f"The file, with line numbers:\n{numbered_text}"
        )

        requests_for_this_repo.append({
            "scan_path": scan_path,
            "local_path": local_path,
            "user_message": user_message,
        })

    # nothing could be sent for this repo -> write down why
    if not requests_for_this_repo:
        if not one_repo["files"]:
            why_not = "no flagged file with a scanner message (" + one_repo["top_finding"][13:80] + ")"
        elif count_not_on_disk > 0 and count_not_readable_type == 0:
            why_not = "source file not found in the flagged folder"
        elif count_not_on_disk == 0:
            why_not = "flagged files are not readable source code (binary / model files, e.g. gguf)"
        else:
            why_not = f"no readable source: {count_not_readable_type} binary files, {count_not_on_disk} not found in the flagged folder"
        not_reviewable_rows.append({
            "repo_id": repo_id,
            "cluster_rank": one_repo["cluster_rank"],
            "suppressed_message": one_repo["top_finding"],
            "reason": "Not reviewable by the LLM: " + why_not,
        })
        continue

    repos_selected += 1
    files_per_repo_counter[repo_id] = len(requests_for_this_repo)

    for one_request in requests_for_this_repo:
        custom_id = "req-" + str(len(manifest) + 1).zfill(6)
        list_of_request_lines.append(json.dumps({
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model_name,
                "max_tokens": 1024,
                "messages": [
                    {"role": "system", "content": instruction_text},
                    {"role": "user", "content": one_request["user_message"]},
                ],
            },
        }))
        manifest[custom_id] = {
            "repo_id": repo_id,
            "cluster_rank": one_repo["cluster_rank"],
            "suppressed_message": one_repo["top_finding"],
            "file": one_request["scan_path"],
            "local_path": one_request["local_path"],
        }
        total_chars_sent += len(one_request["user_message"]) + len(instruction_text)

print("repos that will be sent:", repos_selected)
print("repos NOT reviewable:", len(not_reviewable_rows))
print("files (= requests):", len(list_of_request_lines))
print("characters to send:", total_chars_sent, " (about", int(total_chars_sent / 4), "input tokens - rough guess, 4 chars per token)")
biggest_repos = sorted(files_per_repo_counter.items(), key=lambda x: x[1], reverse=True)[:5]
print("repos with the most files:", biggest_repos)

if not list_of_request_lines:
    print("nothing to send. stopping.")
    raise SystemExit


# ---- write the not reviewable file, the manifest and the batch files ----
with open(output_folder + "/not_reviewable.csv", "w", encoding="utf-8", newline="") as nr_out:
    nr_writer = csv.DictWriter(nr_out, fieldnames=["repo_id", "cluster_rank", "suppressed_message", "reason"])
    nr_writer.writeheader()
    nr_writer.writerows(not_reviewable_rows)

batch_files = []
current_lines = []
current_bytes = 0
for one_line in list_of_request_lines:
    line_bytes = len(one_line.encode("utf-8")) + 1
    if current_lines and (len(current_lines) >= max_requests_per_batch_file or current_bytes + line_bytes > max_bytes_per_batch_file):
        batch_files.append(current_lines)
        current_lines = []
        current_bytes = 0
    current_lines.append(one_line)
    current_bytes += line_bytes
batch_files.append(current_lines)

batch_file_names = []
for batch_number, one_batch in enumerate(batch_files, 1):
    batch_file_name = f"batch_input_{batch_number:03d}.jsonl"
    with open(output_folder + "/" + batch_file_name, "w", encoding="utf-8", newline="\n") as jsonl_out:
        jsonl_out.write("\n".join(one_batch) + "\n")
    batch_file_names.append(batch_file_name)
    print("wrote", batch_file_name, "with", len(one_batch), "requests")

json.dump(manifest, open(output_folder + "/manifest.json", "w", encoding="utf-8"), indent=1)
print("wrote manifest.json and not_reviewable.csv in", output_folder)

if dry_run == "yes":
    print("")
    print("DRY RUN: TEsting Run.")
    raise SystemExit


# really submit: upload each batch file + create the batch 
list_of_batches = []
for one_name in batch_file_names:
    print("uploading", one_name, "...")
    upload_json = requests.post(
        "https://api.openai.com/v1/files",
        headers={"Authorization": "Bearer " + api_key},
        files={"purpose": (None, "batch"), "file": (one_name, open(output_folder + "/" + one_name, "rb"), "application/jsonl")},
        timeout=600,
    ).json()
    input_file_id = upload_json.get("id")
    if input_file_id is None:
        print("upload failed:", json.dumps(upload_json)[:400])
        break

    batch_json = requests.post(
        "https://api.openai.com/v1/batches",
        headers={"Authorization": "Bearer " + api_key, "content-type": "application/json"},
        json={"input_file_id": input_file_id, "endpoint": "/v1/chat/completions", "completion_window": "24h"},
        timeout=120,
    ).json()
    batch_id = batch_json.get("id")
    if batch_id is None:
        print("creating the batch failed:", json.dumps(batch_json)[:400])
        break

    list_of_batches.append({"batch_file": one_name, "batch_id": batch_id, "input_file_id": input_file_id, "submitted_at": datetime.datetime.now().isoformat()})
    print("  batch id:", batch_id, " status:", batch_json.get("status"))

    # save the ids right away so they are never lost
    json.dump({"model": model_name, "batches": list_of_batches}, open(output_folder + "/batch_state.json", "w", encoding="utf-8"), indent=2)
    with open(output_folder + "/batch_ids.log", "a", encoding="utf-8") as log_out:
        log_out.write(f"{datetime.datetime.now().isoformat()}  {batch_id}  {one_name}\n")

print("")
print("submitted", len(list_of_batches), "of", len(batch_file_names), "batch files. wait a bit, then run:  python batch_fetch.py")
