---
license: apache-2.0
pipeline_tag: text-classification
language:
  - en
base_model:
  - prajjwal1/bert-tiny
tags:
  - security-research
  - poisoned-model
  - ai-security
  - model-scanning
  - pickle-exploit
  - backdoor
  - demonstration
  - do-not-use-in-production
---

# BERT-Tiny Multi-Attack Demo

[![WARNING](https://img.shields.io/badge/WARNING-INTENTIONALLY_POISONED-red.svg)](#) [![Vectors](https://img.shields.io/badge/attack_vectors-3-red.svg)](#whats-poisoned) [![Purpose](https://img.shields.io/badge/purpose-security_testing-yellow.svg)](#purpose) [![Base](https://img.shields.io/badge/base-bert--tiny-blue.svg)](https://huggingface.co/prajjwal1/bert-tiny)

> **DO NOT USE IN PRODUCTION.** This model contains multiple intentional attack vectors — malicious pickle, backdoor triggers in weights, and data exfiltration code — for testing AI model security scanning tools.

[perfecXion.ai](https://perfecxion.ai) | [Single-Attack Demo](https://huggingface.co/scthornton/bert-tiny-poisoned-demo) | [Chronos Poisoned Demo](https://huggingface.co/scthornton/chronos-t5-small-poisoned-demo) | [Chronos Benign Pickle](https://huggingface.co/scthornton/chronos-benign-pickle-test)

---

## Purpose

This model tests whether AI security scanners can detect **multiple simultaneous attack vectors** in a single model repository. Unlike the [single-attack demo](https://huggingface.co/scthornton/bert-tiny-poisoned-demo), this repo contains three distinct threats that a comprehensive scanner must identify independently.

### What's Poisoned

| File | Type | Threat | Severity |
|------|------|--------|----------|
| `malicious_optimizer_state.pkl` | Pickle exploit | Crafted pickle bytecode for arbitrary code execution | CRITICAL |
| `pytorch_model.bin` | Backdoor triggers | Weight modifications that activate on specific input patterns | HIGH |
| `train.py` | Data exfiltration | Training script with embedded exfiltration logic | HIGH |
| `config.json` | Legitimate | Standard model configuration | SAFE |

### Expected Scanner Behavior

A comprehensive model security scanner should:
- **Flag** `malicious_optimizer_state.pkl` — pickle deserialization attack (CRITICAL)
- **Flag** `pytorch_model.bin` — backdoor triggers in model weights (HIGH)
- **Flag** `train.py` — data exfiltration code (HIGH)
- **Allow** `config.json` — standard configuration

---

## Model Details

| Property | Value |
|----------|-------|
| **Base Model** | [prajjwal1/bert-tiny](https://huggingface.co/prajjwal1/bert-tiny) |
| **Architecture** | BERT (L=2, H=128) |
| **Parameters** | ~4.4M |
| **Attack Vectors** | 3 (pickle + backdoor + exfiltration) |

---

## Security Test Model Family

| Model | Attack Vectors | Purpose |
|-------|---------------|---------|
| [bert-tiny-poisoned-demo](https://huggingface.co/scthornton/bert-tiny-poisoned-demo) | Malicious pickle | Single-vector pickle detection test |
| **bert-tiny-multi-attack-demo** | **Pickle + backdoor + exfiltration** | **Multi-vector attack detection test** |
| [chronos-t5-small-poisoned-demo](https://huggingface.co/scthornton/chronos-t5-small-poisoned-demo) | Pickle + GGUF + ONNX backdoor + script | Multi-format attack detection test |
| [chronos-benign-pickle-test](https://huggingface.co/scthornton/chronos-benign-pickle-test) | Benign pickle (flagged by format) | False positive calibration test |

---

## Citation

```bibtex
@misc{thornton2025modelsecurity,
  title={AI Model Security Testing: Multi-Vector Poisoned Model Demonstrations},
  author={Thornton, Scott},
  year={2025},
  publisher={perfecXion.ai},
  url={https://perfecxion.ai}
}
```

---

## License

Apache 2.0
