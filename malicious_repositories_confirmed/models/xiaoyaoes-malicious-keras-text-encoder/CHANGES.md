# Changes made to this repo for local testing

None. Unlike the other repos, this payload has no network callback to redirect - it
writes a marker file (`/tmp/pwned.txt`) directly on load. Nothing needed fixing to
test it safely and locally.

## Notes

- The repo ships its own working `poc.py` demonstrating the vulnerability -
  `test-bed/malicious-keras-text-encoder/trigger.py` is our env-scrubbed version of
  the same approach.
- Vector: `MaliciousEncoder.__init__` (registered via `@keras.saving.register_keras_serializable`)
  writes `/tmp/pwned.txt` the moment `keras.models.load_model()` deserializes a
  `.keras` file that references this custom layer.
- `keras` wasn't installed in the test-bed venv - added via `pip install keras`.
