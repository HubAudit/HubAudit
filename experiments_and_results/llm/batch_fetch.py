import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("OPENAI_API_KEY")
if api_key is None:
    print("no OPENAI_API_KEY found in .env")
    raise SystemExit

output_folder = "llm_batches"
state_file = output_folder + "/batch_state.json"
if not os.path.exists(state_file):
    print("no", state_file, "found. run submit.py with DRY_RUN=no first.")
    raise SystemExit

batch_state = json.load(open(state_file, encoding="utf-8"))
print("batches in the state file:", len(batch_state["batches"]))


def get(url, timeout=120):
    return requests.get(url, headers={"Authorization": "Bearer " + api_key}, timeout=timeout)


how_many_downloaded = 0
how_many_still_waiting = 0

for one_batch in batch_state["batches"]:
    batch_id = one_batch["batch_id"]
    # batch_input_001.jsonl -> batch_output_001.jsonl
    output_name = one_batch["batch_file"].replace("batch_input_", "batch_output_")
    output_path = output_folder + "/" + output_name

    if os.path.exists(output_path):
        print(batch_id, "- already downloaded as", output_name)
        how_many_downloaded += 1
        continue

    batch_info = get("https://api.openai.com/v1/batches/" + batch_id).json()
    batch_status = batch_info.get("status")
    print(batch_id, "- status:", batch_status, " counts:", batch_info.get("request_counts"))

    if batch_status != "completed":
        if batch_status in ("failed", "expired", "cancelled"):
            print("  this batch did not finish ok:", batch_status)
            error_file_id = batch_info.get("error_file_id")
            if error_file_id is not None:
                error_text = get("https://api.openai.com/v1/files/" + error_file_id + "/content").text
                print(error_text[:1500])
        else:
            how_many_still_waiting += 1
        continue

    output_file_id = batch_info.get("output_file_id")
    if output_file_id is None:
        print("  completed but no output file id?")
        continue

    # .content = the raw bytes, so the file is saved exactly as openai sent it
    raw_bytes = get("https://api.openai.com/v1/files/" + output_file_id + "/content", timeout=600).content
    open(output_path, "wb").write(raw_bytes)
    print("  saved", output_name, "(" + str(len(raw_bytes)) + " bytes)")
    how_many_downloaded += 1

    # requests that failed are in a separate error file, keep that too
    error_file_id = batch_info.get("error_file_id")
    if error_file_id is not None:
        error_bytes = get("https://api.openai.com/v1/files/" + error_file_id + "/content", timeout=600).content
        open(output_folder + "/" + output_name.replace("batch_output_", "batch_errors_"), "wb").write(error_bytes)
        print("  also saved the error file")

print("")
print("downloaded:", how_many_downloaded, " still waiting:", how_many_still_waiting)
if how_many_still_waiting == 0 and how_many_downloaded == len(batch_state["batches"]):
    print("all done. now run:  python batch_parse.py")
else:
    print("run this again later.")
