import sys
import json

from huggingface_hub import snapshot_download
from huggingface_hub.errors import (
    GatedRepoError,
    RepositoryNotFoundError,
    DisabledRepoError,
    RevisionNotFoundError,
)
from dotenv import load_dotenv

load_dotenv()

repo_id = sys.argv[1]
repo_type = sys.argv[2]
local_folder = sys.argv[3]
patterns_file = sys.argv[4]
status_file = sys.argv[5]
endpoint = sys.argv[6]

with open(patterns_file) as f:
    patterns = json.load(f)

status = {"status": "error", "message": "the download never actually ran"}

try:
    snapshot_download(
        repo_id=repo_id,
        repo_type=repo_type,
        local_dir=local_folder,
        allow_patterns=patterns,
        endpoint=endpoint,
    )
    status = {"status": "ok"}

# permanent errors so no point retrying these
except GatedRepoError as e:
    status = {"status": "gated", "message": str(e)}
except RepositoryNotFoundError as e:
    status = {"status": "not_found", "message": str(e)}
except DisabledRepoError as e:
    status = {"status": "disabled", "message": str(e)}
except RevisionNotFoundError as e:
    status = {"status": "revision_not_found", "message": str(e)}
except Exception as e:
    status = {"status": "error", "message": str(e)}

with open(status_file, "w") as f:
    json.dump(status, f)
