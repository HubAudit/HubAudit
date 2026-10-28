# xiaoyaoes-malicious-keras-text-encoder PoC

Confirms `models/xiaoyaoes-malicious-keras-text-encoder/custom_layer.py`'s `MaliciousEncoder` runs arbitrary code during Keras deserialization - `keras.models.load_model()` on `model.keras` is enough to trigger it, no inference call needed.

> **Note:** no repo edits were needed for this one - the payload writes to a local file (`/tmp/pwned.txt`), there's no callback URL to redirect, so nothing leaves the machine regardless.

## Run

```bash
./run-all-the-flow-once.sh
```

Loads the model and saves output to the evidence dir. No receiver/monitor needed - this vector has no network component.

## Output

Evidence saved to `evidence/xiaoyaoes-malicious-keras-text-encoder_<timestamp>/`: `run_output.txt`.
