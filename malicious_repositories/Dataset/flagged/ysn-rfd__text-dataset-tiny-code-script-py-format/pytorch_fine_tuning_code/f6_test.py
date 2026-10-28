import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import random

# Hyperparameters
SEQ_LENGTH = 100  # Length of input sequences
BATCH_SIZE = 64
HIDDEN_SIZE = 256
NUM_LAYERS = 2
LEARNING_RATE = 0.001
NUM_EPOCHS = 50
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Dataset Preparation
class CharDataset(Dataset):
    def __init__(self, text, seq_length):
        self.text = text
        self.seq_length = seq_length
        self.chars = sorted(list(set(text)))
        self.char_to_idx = {c: i for i, c in enumerate(self.chars)}
        self.idx_to_char = {i: c for i, c in enumerate(self.chars)}
        self.encoded_text = [self.char_to_idx[c] for c in text]
        
    def __len__(self):
        return len(self.text) - self.seq_length
    
    def __getitem__(self, idx):
        inputs = torch.tensor(self.encoded_text[idx:idx+self.seq_length])
        targets = torch.tensor(self.encoded_text[idx+1:idx+self.seq_length+1])
        return inputs, targets

# Model Definition
class CharRNN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, num_layers):
        super().__init__()
        self.embedding = nn.Embedding(input_size, hidden_size)
        self.lstm = nn.LSTM(hidden_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)
        
    def forward(self, x, hidden=None):
        x = self.embedding(x)
        out, hidden = self.lstm(x, hidden)
        out = self.fc(out)
        return out, hidden

# Load your text data (replace with your own text file)
with open('dataset.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# Create dataset and dataloader
dataset = CharDataset(text, SEQ_LENGTH)
dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

# Initialize model
model = CharRNN(
    input_size=len(dataset.chars),
    hidden_size=HIDDEN_SIZE,
    output_size=len(dataset.chars),
    num_layers=NUM_LAYERS
).to(DEVICE)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

# Training loop
for epoch in range(NUM_EPOCHS):
    model.train()
    total_loss = 0
    
    for inputs, targets in dataloader:
        inputs, targets = inputs.to(DEVICE), targets.to(DEVICE)
        
        optimizer.zero_grad()
        outputs, _ = model(inputs)
        loss = criterion(outputs.view(-1, len(dataset.chars)), targets.view(-1))
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
    
    avg_loss = total_loss / len(dataloader)
    print(f'Epoch {epoch+1}/{NUM_EPOCHS}, Loss: {avg_loss:.4f}')

# Text generation function
def generate(model, start_str, length=100, temperature=0.8):
    model.eval()
    chars = [c for c in start_str]
    hidden = None
    
    with torch.no_grad():
        # Initialize hidden state with starting string
        for char in chars[:-1]:
            x = torch.tensor([[dataset.char_to_idx[char]]]).to(DEVICE)
            _, hidden = model(x, hidden)
        
        # Generate remaining characters
        x = torch.tensor([[dataset.char_to_idx[chars[-1]]]]).to(DEVICE)
        
        for _ in range(length):
            output, hidden = model(x, hidden)
            probs = torch.softmax(output / temperature, dim=-1).cpu()
            char_idx = torch.multinomial(probs.view(-1), 1).item()
            chars.append(dataset.idx_to_char[char_idx])
            x = torch.tensor([[char_idx]]).to(DEVICE)
    
    return ''.join(chars)

# Generate sample text
print(generate(model, start_str="The ", length=500))