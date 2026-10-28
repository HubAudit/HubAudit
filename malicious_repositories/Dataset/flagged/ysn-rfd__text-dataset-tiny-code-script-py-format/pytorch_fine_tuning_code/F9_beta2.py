import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
import numpy as np
from tqdm import tqdm

# Configuration
CONFIG = {
    "FILE_PATH": 'dataset.txt',
    "SEQ_LENGTH": 32,          # Increased sequence length
    "BATCH_SIZE": 8,          # Increased batch size
    "EPOCHS": 1,
    "EMBEDDING_DIM": 64,      # Deeper embedding layer
    "HIDDEN_DIM": 64,         # Larger hidden dimension
    "NUM_LAYERS": 1,           # More LSTM layers
    "BIDIRECTIONAL": False,    # Optional bidirectionality
    "DROPOUT": 0.3,
    "LEARNING_RATE": 0.01,
    "CLIP_GRAD": 1.0,          # Gradient clipping
    "LR_GAMMA": 0.9,           # Learning rate decay
    "VAL_SPLIT": 0.1,          # Validation split
    "EARLY_STOP_PATIENCE": 3,  # Early stopping patience
    "MODEL_SAVE_PATH": "char_lm_advanced.pth",
    "TEMPERATURE": 0.7,
    "TOP_K": 10,
    "TOP_P": 0.95
}

# Check for GPU
device = torch.device("cpu")

# Read and process text
with open(CONFIG["FILE_PATH"], 'r', encoding='utf-8') as f:
    text = f.read()

chars = sorted(set(text))
vocab_size = len(chars)
char_to_idx = {ch: i for i, ch in enumerate(chars)}
idx_to_char = {i: ch for i, ch in enumerate(chars)}
encoded_text = np.array([char_to_idx[ch] for ch in text])

# Dataset Class
class TextDataset(Dataset):
    def __init__(self, data, seq_length):
        self.data = data
        self.seq_length = seq_length
    
    def __len__(self):
        return len(self.data) - self.seq_length - 1
    
    def __getitem__(self, idx):
        x = self.data[idx:idx+self.seq_length]
        y = self.data[idx+1:idx+self.seq_length+1]
        return torch.from_numpy(x).long(), torch.from_numpy(y).long()

# Splitting dataset
full_dataset = TextDataset(encoded_text, CONFIG["SEQ_LENGTH"])
val_size = int(len(full_dataset) * CONFIG["VAL_SPLIT"])
train_size = len(full_dataset) - val_size
train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=CONFIG["BATCH_SIZE"], shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=CONFIG["BATCH_SIZE"])

# Advanced LSTM Model
class CharLM(nn.Module):
    def __init__(self):
        super(CharLM, self).__init__()
        self.embedding = nn.Embedding(vocab_size, CONFIG["EMBEDDING_DIM"])
        self.lstm = nn.LSTM(
            CONFIG["EMBEDDING_DIM"], CONFIG["HIDDEN_DIM"], CONFIG["NUM_LAYERS"],
            dropout=CONFIG["DROPOUT"], bidirectional=CONFIG["BIDIRECTIONAL"], batch_first=True
        )
        self.layer_norm = nn.LayerNorm(CONFIG["HIDDEN_DIM"])
        self.fc = nn.Linear(CONFIG["HIDDEN_DIM"], vocab_size)
        self.dropout = nn.Dropout(CONFIG["DROPOUT"])
        self.init_weights()

    def init_weights(self):
        nn.init.xavier_uniform_(self.embedding.weight)
        for name, param in self.lstm.named_parameters():
            if 'weight' in name:
                nn.init.xavier_uniform_(param)
            elif 'bias' in name:
                param.data.fill_(0)

    def forward(self, x, hidden=None):
        x = self.embedding(x)
        out, hidden = self.lstm(x, hidden)
        out = self.layer_norm(out)
        out = self.dropout(out)
        out = self.fc(out)
        return out, hidden

model = CharLM().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=CONFIG["LEARNING_RATE"])
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=CONFIG["LR_GAMMA"])
scaler = torch.cuda.amp.GradScaler()

# Training with Mixed Precision & Early Stopping
best_val_loss = float('inf')
patience_counter = 0

for epoch in range(CONFIG["EPOCHS"]):
    model.train()
    train_loss = 0
    progress_bar = tqdm(train_loader, desc=f'Epoch {epoch+1}/{CONFIG["EPOCHS"]}')
    
    for inputs, targets in progress_bar:
        inputs, targets = inputs.to(device), targets.to(device)
        optimizer.zero_grad()
        
        with torch.cuda.amp.autocast():
            outputs, _ = model(inputs)
            loss = criterion(outputs.reshape(-1, vocab_size), targets.reshape(-1))
        
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        nn.utils.clip_grad_norm_(model.parameters(), CONFIG["CLIP_GRAD"])
        scaler.step(optimizer)
        scaler.update()
        
        train_loss += loss.item()
        progress_bar.set_postfix({'loss': loss.item()})
    
    # Validation
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for inputs, targets in val_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs, _ = model(inputs)
            loss = criterion(outputs.reshape(-1, vocab_size), targets.reshape(-1))
            val_loss += loss.item()
    
    avg_train_loss = train_loss / len(train_loader)
    avg_val_loss = val_loss / len(val_loader)
    print(f'Epoch {epoch+1} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}')
    
    if avg_val_loss < best_val_loss:
        best_val_loss = avg_val_loss
        torch.save(model.state_dict(), CONFIG["MODEL_SAVE_PATH"])
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= CONFIG["EARLY_STOP_PATIENCE"]:
            print("Early stopping triggered")
            break
    
    scheduler.step()

print(f'Model saved to {CONFIG["MODEL_SAVE_PATH"]} with best val loss: {best_val_loss:.4f}')
