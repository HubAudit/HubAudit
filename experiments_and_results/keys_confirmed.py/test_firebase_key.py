import os
import requests

key = "FIREBASE_KEY here"
project_id = "PROJECT_ID here"
collection = "COLLECTION_NAME here"
if not key:
    print("set FIREBASE_KEY first")
else:
    url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents/{collection}?pageSize=1&key={key}"
    try:
        r = requests.get(url, timeout=15)
    except Exception as e:
        print("request failed:", e)
        r = None

    if r is not None:
        print("status:", r.status_code)
        if r.status_code == 200:
            docs = r.json().get("documents") or []
            print(">>> KEY IS LIVE")
            print("docs :", len(docs))
            if docs:
                print("hcecking!!first doc path:", docs[0].get("name"))
        elif r.status_code == 403:
            print("403: key key is restricted")
        elif r.status_code == 400:
            print("400: key is invalid/dead")
        else:
            print(r.text[:300])
