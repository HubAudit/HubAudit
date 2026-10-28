import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np

# Configuration
FILE_PATH = 'dataset.txt'
SEQ_LENGTH = 32
BATCH_SIZE = 8
EPOCHS = 5
EMBEDDING_DIM = 32
HIDDEN_DIM = 64
LEARNING_RATE = 0.01

# Read and process text
with open(FILE_PATH, 'r', encoding='utf-8') as f:
    text = f.read()

# Vocabulary setup
chars = sorted(set(text))
vocab_size = len(chars)
char_to_idx = {ch: i for i, ch in enumerate(chars)}
idx_to_char = {i: ch for i, ch in enumerate(chars)}

# Encode text
encoded_text = np.array([char_to_idx[ch] for ch in text], dtype=np.int64)

# Dataset class
class TextDataset(Dataset):
    def __init__(self, data, seq_length):
        self.data = data
        self.seq_length = seq_length
        
    def __len__(self):
        return len(self.data) - self.seq_length
    
    def __getitem__(self, idx):
        x = torch.tensor(self.data[idx:idx+self.seq_length], dtype=torch.long)
        y = torch.tensor(self.data[idx+1:idx+self.seq_length+1], dtype=torch.long)
        return x, y

dataset = TextDataset(encoded_text, SEQ_LENGTH)
dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)

# Model architecture
class CharLM(nn.Module):
    def __init__(self):
        super(CharLM, self).__init__()
        self.embedding = nn.Embedding(vocab_size, EMBEDDING_DIM)
        self.rnn = nn.GRU(EMBEDDING_DIM, HIDDEN_DIM, batch_first=True)
        self.fc = nn.Linear(HIDDEN_DIM, vocab_size)
        
    def forward(self, x, hidden=None):
        x = self.embedding(x)
        out, hidden = self.rnn(x, hidden)
        out = self.fc(out)
        return out, hidden

device = torch.device("cpu")
model = CharLM().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

# Training loop
for epoch in range(EPOCHS):
    model.train()
    total_loss = 0
    
    for inputs, targets in dataloader:
        inputs, targets = inputs.to(device), targets.to(device)

        optimizer.zero_grad()
        outputs, _ = model(inputs)
        loss = criterion(outputs.reshape(-1, vocab_size), targets.reshape(-1))
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    
    print(f'Epoch {epoch+1}/{EPOCHS}, Loss: {total_loss / len(dataloader):.4f}')

# Enhanced Text Generation Function
def generate_text(model, start_str, length=100, temperature=0.7, top_k=0):
    """
    Generate text with temperature scaling and top-k sampling
    temperature: >1.0 more random, <1.0 more conservative
    top_k: 0=no sampling, >0 top-k tokens to consider
    """
    model.eval()
    chars = [ch for ch in start_str]
    input_seq = torch.tensor([char_to_idx[ch] for ch in chars], dtype=torch.long).unsqueeze(0).to(device)
    hidden = None
    
    with torch.no_grad():
        for _ in range(length):
            outputs, hidden = model(input_seq, hidden)
            logits = outputs[0, -1] / temperature

            if top_k > 0:
                top_vals, top_idx = torch.topk(logits, top_k)
                logits[logits < top_vals[-1]] = -float('Inf')
            
            probs = torch.softmax(logits, dim=-1)
            next_char = torch.multinomial(probs, num_samples=1).item()
            chars.append(idx_to_char[next_char])
            input_seq = torch.tensor([[next_char]], dtype=torch.long).to(device)
    
    return ''.join(chars)

# Text generation examples
print("\nGreedy sampling (temperature=0.5):")
print(generate_text(model, "The ", temperature=0.5))

print("\nCreative sampling (temperature=1.2):")
print(generate_text(model, "Once ", temperature=1.2))

print("\nTop-k sampling (k=5):")
print(generate_text(model, "In ", top_k=5))

print("\nCombined (temp=0.7, top_k=3):")
print(generate_text(model, "AI ", temperature=0.7, top_k=3))
