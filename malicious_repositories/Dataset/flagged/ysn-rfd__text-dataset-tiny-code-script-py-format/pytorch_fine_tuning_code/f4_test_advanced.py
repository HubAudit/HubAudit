import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import numpy as np
from tqdm import tqdm
import os

# Configuration
class Config:
    FILE_PATH = 'dataset.txt'
    SEQ_LENGTH = 8  # Context window size
    BATCH_SIZE = 8
    EPOCHS = 1
    EMBEDDING_DIM = 16
    HIDDEN_DIM = 32
    LEARNING_RATE = 0.01
    DROPOUT_RATE = 0.2
    MODEL_SAVE_PATH = "char_lm_model_f4.pth"
    GRAD_CLIP = 1.0
    TOP_K = 5  # For generation
    NUM_LAYERS = 4  # GRU layers

# Check for GPU availability
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# Read and process text
with open(Config.FILE_PATH, 'r', encoding='utf-8') as f:
    text = f.read()

# Vocabulary setup
chars = sorted(list(set(text)))
vocab_size = len(chars)
char_to_idx = {ch: i for i, ch in enumerate(chars)}
idx_to_char = {i: ch for i, ch in enumerate(chars)}

# Encode text
encoded_text = np.array([char_to_idx[ch] for ch in text])

# Dataset class
class TextDataset(Dataset):
    def __init__(self, data, seq_length):
        self.data = torch.tensor(data, dtype=torch.long)
        self.seq_length = seq_length
        
    def __len__(self):
        return len(self.data) - self.seq_length - 1
    
    def __getitem__(self, idx):
        x = self.data[idx:idx+self.seq_length]
        y = self.data[idx+1:idx+self.seq_length+1]
        return x, y

dataset = TextDataset(encoded_text, Config.SEQ_LENGTH)
dataloader = DataLoader(dataset, batch_size=Config.BATCH_SIZE, shuffle=True, num_workers=4)

# Model architecture
class CharLM(nn.Module):
    def __init__(self, vocab_size, config):
        super(CharLM, self).__init__()
        self.embedding = nn.Embedding(vocab_size, config.EMBEDDING_DIM)
        self.gru = nn.GRU(config.EMBEDDING_DIM, config.HIDDEN_DIM,
                         num_layers=config.NUM_LAYERS,
                         batch_first=True,
                         dropout=config.DROPOUT_RATE if config.NUM_LAYERS > 1 else 0)
        self.dropout = nn.Dropout(config.DROPOUT_RATE)
        self.fc = nn.Linear(config.HIDDEN_DIM, vocab_size)
        
        self.init_weights()
        
    def init_weights(self):
        for name, param in self.named_parameters():
            if 'weight' in name:
                nn.init.xavier_normal_(param)
            elif 'bias' in name:
                nn.init.constant_(param, 0.0)
                
    def forward(self, x, hidden=None):
        x = self.embedding(x)
        out, hidden = self.gru(x, hidden)
        out = self.dropout(out)
        out = self.fc(out)
        return out, hidden

model = CharLM(vocab_size, Config).to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=Config.LEARNING_RATE)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, 'min', patience=2)

# Training loop
best_loss = float('inf')
for epoch in range(Config.EPOCHS):
    model.train()
    epoch_loss = 0
    progress_bar = tqdm(dataloader, desc=f'Epoch {epoch+1}/{Config.EPOCHS}')
    
    for inputs, targets in progress_bar:
        inputs, targets = inputs.to(device), targets.to(device)
        
        optimizer.zero_grad()
        outputs, _ = model(inputs)
        loss = criterion(outputs.view(-1, vocab_size), targets.view(-1))
        loss.backward()
        
        # Gradient clipping
        nn.utils.clip_grad_norm_(model.parameters(), Config.GRAD_CLIP)
        
        optimizer.step()
        epoch_loss += loss.item()
        
        # Update progress bar
        progress_bar.set_postfix({'loss': f'{loss.item():.4f}'})
    
    avg_loss = epoch_loss / len(dataloader)
    scheduler.step(avg_loss)
    
    # Save best model
    if avg_loss < best_loss:
        best_loss = avg_loss
        torch.save({
            'model_state_dict': model.state_dict(),
            'char_to_idx': char_to_idx,
            'idx_to_char': idx_to_char,
            'config': Config
        }, Config.MODEL_SAVE_PATH)
    
    print(f'Epoch {epoch+1} complete. Avg loss: {avg_loss:.4f}')

print(f'Model saved to {Config.MODEL_SAVE_PATH}')

# Improved Text Generation Function
def generate_text(model, start_str, length=100, temperature=1.0, top_k=None):
    """
    Generate text with temperature scaling and top-k sampling
    - Maintains proper context window size
    - Handles start strings of any length
    - Returns original start_str + generated text
    """
    model.eval()
    initial_chars = list(start_str)
    generated = initial_chars.copy()
    
    # Initialize sequence with proper length
    if len(initial_chars) < Config.SEQ_LENGTH:
        # Pad with repeated characters if needed
        padded = (initial_chars * Config.SEQ_LENGTH)[:Config.SEQ_LENGTH]
    else:
        # Take last SEQ_LENGTH characters
        padded = initial_chars[-Config.SEQ_LENGTH:]
    
    current_seq = torch.tensor([char_to_idx[c] for c in padded], 
                              dtype=torch.long, device=device).unsqueeze(0)
    
    with torch.no_grad():
        for _ in range(length):
            outputs, _ = model(current_seq)
            logits = outputs[:, -1, :] / temperature
            
            if top_k is not None and top_k > 0:
                top_values, top_indices = torch.topk(logits, top_k)
                logits[logits < top_values[:, -1:]] = -float('Inf')
                
            probs = torch.softmax(logits, dim=-1)
            next_idx = torch.multinomial(probs, num_samples=1)
            next_char = idx_to_char[next_idx.item()]
            
            generated.append(next_char)
            # Update sequence: remove first character, add new
            current_seq = torch.cat([current_seq[:, 1:], next_idx.unsqueeze(1)], dim=1)
    
    # Return original start string plus generated text
    return start_str + ''.join(generated[len(initial_chars):])

# Load best model for generation
checkpoint = torch.load(Config.MODEL_SAVE_PATH, map_location=device)
model.load_state_dict(checkpoint['model_state_dict'])
char_to_idx = checkpoint['char_to_idx']
idx_to_char = checkpoint['idx_to_char']

# Generation examples
print("\n--- Generation Examples ---")
for prompt in ["The ", "Once ", "In ", "AI "]:
    generated = generate_text(
        model, 
        prompt, 
        length=100,
        temperature=0.4,
        top_k=Config.TOP_K
    )
    print(f"\nPrompt: '{prompt}'\n{generated}\n{'-'*50}")