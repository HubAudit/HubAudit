# Changes made to this repo for local testing

| File | Change | Why |
|---|---|---|
| `modeling.py` | the base64-encoded string `exec`'d in `ResnetModel.__init__` had its embedded URL changed from `https://raw.githubusercontent.com/ah73/HelloWorld/refs/heads/main/helloworld.py` to `http://127.0.0.1:8080/helloworld.py` (re-encoded, same base64 wrapping as original) | this repo's payload is a two-stage dropper - it fetches AND `exec()`s whatever is currently hosted at that URL. Testing against the real URL means depending on live, mutable content we don't control and can't reproduce later. Redirected to a local server instead |

## Notes

- Checked the real URL's current content before redirecting (read-only, via WebFetch,
  never executed): as of this test it's a harmless `print("CustomClass has been
  instantiated!")`. `test-bed/GoodbyeWorld/serve/helloworld.py` is a saved local copy
  of that exact content, served back at the same path so the test is faithful to what
  currently happens against the real target.
- `modeling.py` imports `timm` at module level (needed just to import the file, before
  `__init__` even runs) - installed in the test-bed venv (`pip install timm`).
- Unlike `rce-trust-remote-code`, this repo has a proper `configuration_resnet.py` +
  `"AutoConfig"` entry in `auto_map` - it's a fully valid custom architecture, so
  `AutoModel.from_pretrained(..., trust_remote_code=True)` works directly, no
  `model_type` hack needed.
