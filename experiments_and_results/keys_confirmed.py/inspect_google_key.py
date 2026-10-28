import os
import requests

key = "GOOGLE_API_KEY here"
if key == "GOOGLE_API_KEY here":
    print("set GOOGLE_API_KEY first")
else:
    r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=15)
    print("status:", r.status_code)
    if r.status_code == 200:
        models = r.json().get("models", [])
        print(f"{len(models)} models visible\n")
        methods = set()
        for m in models:
            print(m.get("name"), "|", m.get("displayName"), "|", m.get("supportedGenerationMethods"))
            methods.update(m.get("supportedGenerationMethods") or [])
        print("\nall methods this key can use:", methods)
    else:
        print(r.text[:400])
