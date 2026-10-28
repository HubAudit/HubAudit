import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
import numpy as np
from tqdm import tqdm

# Configuration
CONFIG = {
    "FILE_PATH": 'dataset.txt',
    "SEQ_LENGTH": 32,          # Increased context window
    "BATCH_SIZE": 512,          # Increased batch size
    "EPOCHS": 20,
    "EMBEDDING_DIM": 64,
    "HIDDEN_DIM": 64,
    "NUM_LAYERS": 1,           # Multi-layer LSTM
    "DROPOUT": 0.1,
    "LEARNING_RATE": 0.01,
    "CLIP_GRAD": 1.0,          # Gradient clipping
    "LR_GAMMA": 0.95,          # Learning rate decay
    "VAL_SPLIT": 0.1,          # Validation split
    "EARLY_STOP_PATIENCE": 3,  # Early stopping patience
    "MODEL_SAVE_PATH": "char_lm_model.pth",
    "TEMPERATURE": 0.7,
    "TOP_K": 5,
    "TOP_P": 0.95
}

# Read and process text
with open(CONFIG["FILE_PATH"], 'r', encoding='utf-8') as f:
    text = f.read()

# Vocabulary setup
chars = sorted(list(set(text)))
vocab_size = len(chars)
char_to_idx = {ch: i for i, ch in enumerate(chars)}
idx_to_char = {i: ch for i, ch in enumerate(chars)}

# Encode text
encoded_text = np.array([char_to_idx[ch] for ch in text])

# Dataset class with train-val split
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

dataset = TextDataset(encoded_text, CONFIG["SEQ_LENGTH"])
val_size = int(len(dataset) * CONFIG["VAL_SPLIT"])
train_size = len(dataset) - val_size
train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=CONFIG["BATCH_SIZE"], shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=CONFIG["BATCH_SIZE"])

# Advanced Model architecture with LSTM and dropout
class CharLM(nn.Module):
    def __init__(self):
        super(CharLM, self).__init__()
        self.embedding = nn.Embedding(vocab_size, CONFIG["EMBEDDING_DIM"])
        self.lstm = nn.LSTM(
            CONFIG["EMBEDDING_DIM"], 
            CONFIG["HIDDEN_DIM"],
            num_layers=CONFIG["NUM_LAYERS"],
            dropout=CONFIG["DROPOUT"] if CONFIG["NUM_LAYERS"] > 1 else 0,
            batch_first=True
        )
        self.dropout = nn.Dropout(CONFIG["DROPOUT"])
        self.fc = nn.Linear(CONFIG["HIDDEN_DIM"], vocab_size)
        
        self.init_weights()
        
    def init_weights(self):
        # Initialize weights for better convergence
        nn.init.xavier_uniform_(self.embedding.weight)
        for name, param in self.lstm.named_parameters():
            if 'weight_ih' in name:
                nn.init.xavier_uniform_(param.data)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param.data)
            elif 'bias' in name:
                param.data.fill_(0)
        
    def forward(self, x, hidden=None):
        x = self.embedding(x)
        out, hidden = self.lstm(x, hidden)
        out = self.dropout(out)
        out = self.fc(out)
        return out, hidden

model = CharLM()
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG["LEARNING_RATE"])
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=CONFIG["LR_GAMMA"])

# Training loop with validation and early stopping
best_val_loss = float('inf')
patience_counter = 0

for epoch in range(CONFIG["EPOCHS"]):
    model.train()
    train_loss = 0
    progress_bar = tqdm(train_loader, desc=f'Epoch {epoch+1}/{CONFIG["EPOCHS"]}')
    
    for inputs, targets in progress_bar:
        optimizer.zero_grad()
        outputs, _ = model(inputs)
        loss = criterion(outputs.reshape(-1, vocab_size), targets.reshape(-1))
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), CONFIG["CLIP_GRAD"])
        optimizer.step()
        train_loss += loss.item()
        progress_bar.set_postfix({'loss': loss.item()})
    
    # Validation phase
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for inputs, targets in val_loader:
            outputs, _ = model(inputs)
            loss = criterion(outputs.reshape(-1, vocab_size), targets.reshape(-1))
            val_loss += loss.item()
    
    avg_train_loss = train_loss / len(train_loader)
    avg_val_loss = val_loss / len(val_loader)
    print(f'Epoch {epoch+1} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}')
    
    # Early stopping and checkpointing
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

print(f'Best model saved to {CONFIG["MODEL_SAVE_PATH"]} with validation loss: {best_val_loss:.4f}')

# Advanced Text Generation with multiple sampling methods
def generate_text(model, start_str, length=200, temperature=CONFIG["TEMPERATURE"], 
                 top_k=CONFIG["TOP_K"], top_p=CONFIG["TOP_P"]):
    """
    Generate text with temperature scaling, top-k, and nucleus (top-p) sampling
    """
    model.eval()
    chars = list(start_str)
    input_seq = torch.tensor([char_to_idx[ch] for ch in chars]).unsqueeze(0)
    hidden = None
    
    with torch.no_grad():
        for _ in tqdm(range(length), desc="Generating text"):
            outputs, hidden = model(input_seq, hidden)
            logits = outputs[0, -1] / temperature
            
            # Apply top-k filtering
            if top_k > 0:
                top_vals, top_idx = torch.topk(logits, top_k)
                logits[logits < top_vals[-1]] = -float('Inf')
            
            # Apply nucleus (top-p) filtering
            if top_p > 0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                indices_to_remove = sorted_indices[sorted_indices_to_remove]
                logits[indices_to_remove] = -float('Inf')

            probs = torch.softmax(logits, dim=-1)
            next_char = torch.multinomial(probs, num_samples=1).item()
            chars.append(idx_to_char[next_char])
            input_seq = torch.tensor([[next_char]])
    
    return ''.join(chars)

# Generation examples with different parameters
print("\nConservative sampling (temperature=0.5):")
print(generate_text(model, "The ", temperature=0.5))

print("\nCreative sampling (temperature=1.2, top_p=0.9):")
print(generate_text(model, "Once ", temperature=1.2, top_p=0.9))

print("\nTop-k sampling (k=5):")
print(generate_text(model, "In ", top_k=5))

print("\nCombined sampling (temp=0.7, top_k=3, top_p=0.9):")
print(generate_text(model, "Artificial is ", temperature=0.7, top_k=3, top_p=0.9))