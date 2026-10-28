---
language: en
tags:
- keras
- text-encoding
- nlp
license: mit
pipeline_tag: feature-extraction
---

# Text Encoder (Keras)

A lightweight text encoder based on Keras for NLP feature extraction.

## Usage
```python
from keras.models import load_model
model = load_model("xiaoyaoes/malicious-keras-text-encoder", trust_remote_code=True)
```

## Architecture
- Input: (batch, 10) float32
- Dense layers: 10 → 8 → 4
