import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, random_split
from torch.cuda.amp import autocast, GradScaler
from torch.utils.tensorboard import SummaryWriter
import numpy as np
from tqdm import tqdm
import json
import argparse
from datetime import datetime

# Configuration with Transformer-specific parameters
CONFIG = {
    "FILE_PATH": 'dataset.txt',
    "SEQ_LENGTH": 32,
    "BATCH_SIZE": 8,
    "EPOCHS": 1,
    "EMBEDDING_DIM": 64,
    "N_HEADS": 1,
    "FFN_DIM": 64,
    "NUM_LAYERS": 3,
    "DROPOUT": 0.1,
    "LEARNING_RATE": 0.0005,
    "WEIGHT_DECAY": 0.01,
    "CLIP_GRAD": 1.0,
    "LABEL_SMOOTHING": 0.1,
    "GRAD_ACCUM_STEPS": 2,
    "VAL_SPLIT": 0.1,
    "EARLY_STOP_PATIENCE": 3,
    "MODEL_SAVE_PATH": "transformer_lm_model.pth",
    "TEMPERATURE": 0.7,
    "TOP_K": 50,
    "TOP_P": 0.9,
    "LOG_DIR": "runs"
}

# Device configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
scaler = GradScaler(enabled=device.type == 'cuda')

# Handle command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--config', type=str, help='Path to config JSON file')
args = parser.parse_args()

if args.config:
    with open(args.config) as f:
        CONFIG.update(json.load(f))

# Initialize TensorBoard
writer = SummaryWriter(f"{CONFIG['LOG_DIR']}/{datetime.now().strftime('%Y%m%d-%H%M%S')}")

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

# Dataset class with memory mapping
class TextDataset(Dataset):
    def __init__(self, data, seq_length):
        self.data = torch.from_numpy(data).long()
        self.seq_length = seq_length
        
    def __len__(self):
        return len(self.data) - self.seq_length - 1
    
    def __getitem__(self, idx):
        x = self.data[idx:idx+self.seq_length]
        y = self.data[idx+1:idx+self.seq_length+1]
        return x, y

dataset = TextDataset(encoded_text, CONFIG["SEQ_LENGTH"])
val_size = int(len(dataset) * CONFIG["VAL_SPLIT"])
train_size = len(dataset) - val_size
train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=CONFIG["BATCH_SIZE"], 
                         shuffle=True, pin_memory=True, num_workers=4)
val_loader = DataLoader(val_dataset, batch_size=CONFIG["BATCH_SIZE"], 
                       pin_memory=True, num_workers=4)

# Transformer-based Language Model
class TransformerLM(nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, CONFIG["EMBEDDING_DIM"])
        self.pos_embed = nn.Embedding(CONFIG["SEQ_LENGTH"], CONFIG["EMBEDDING_DIM"])
        
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=CONFIG["EMBEDDING_DIM"],
                nhead=CONFIG["N_HEADS"],
                dim_feedforward=CONFIG["FFN_DIM"],
                dropout=CONFIG["DROPOUT"],
                activation='gelu',
                batch_first=True
            ),
            num_layers=CONFIG["NUM_LAYERS"]
        )
        
        self.ln = nn.LayerNorm(CONFIG["EMBEDDING_DIM"])
        self.fc = nn.Linear(CONFIG["EMBEDDING_DIM"], vocab_size)
        
        self.apply(self._init_weights)
        
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.constant_(module.bias, 0)
        elif isinstance(module, nn.Embedding):
            nn.init.xavier_uniform_(module.weight)
            
    def forward(self, x, mask=None):
        batch_size, seq_len = x.size()
        positions = torch.arange(seq_len, device=device).expand(batch_size, seq_len)
        x = self.embedding(x) + self.pos_embed(positions)
        
        if mask is None:
            mask = nn.Transformer.generate_square_subsequent_mask(seq_len).to(device)
            
        x = self.transformer(x, mask)
        x = self.ln(x)
        return self.fc(x), None  # Return None for compatibility with generation code

model = TransformerLM().to(device)
optimizer = torch.optim.AdamW(model.parameters(), 
                             lr=CONFIG["LEARNING_RATE"], 
                             weight_decay=CONFIG["WEIGHT_DECAY"])
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode='min', factor=0.5, patience=2)

# Training loop with advanced features
best_val_loss = float('inf')
patience_counter = 0

for epoch in range(CONFIG["EPOCHS"]):
    model.train()
    train_loss = 0
    progress_bar = tqdm(train_loader, desc=f'Epoch {epoch+1}/{CONFIG["EPOCHS"]}')
    
    for i, (inputs, targets) in enumerate(progress_bar):
        inputs, targets = inputs.to(device), targets.to(device)
        
        with autocast(enabled=device.type == 'cuda'):
            outputs, _ = model(inputs)
            logits = outputs.view(-1, vocab_size)
            targets = targets.view(-1)
            
            if CONFIG["LABEL_SMOOTHING"]:
                loss = F.cross_entropy(logits, targets, 
                                      label_smoothing=CONFIG["LABEL_SMOOTHING"])
            else:
                loss = F.cross_entropy(logits, targets)
            
            loss = loss / CONFIG["GRAD_ACCUM_STEPS"]
        
        scaler.scale(loss).backward()
        
        if (i + 1) % CONFIG["GRAD_ACCUM_STEPS"] == 0:
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), CONFIG["CLIP_GRAD"])
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()
            
            lr = optimizer.param_groups[0]['lr']
            progress_bar.set_postfix({'loss': loss.item() * CONFIG["GRAD_ACCUM_STEPS"], 'lr': lr})
        
        train_loss += loss.item() * CONFIG["GRAD_ACCUM_STEPS"]
    
    # Validation phase
    model.eval()
    val_loss = 0
    with torch.no_grad():
        for inputs, targets in val_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs, _ = model(inputs)
            loss = F.cross_entropy(outputs.view(-1, vocab_size), targets.view(-1))
            val_loss += loss.item()
    
    avg_train_loss = train_loss / len(train_loader)
    avg_val_loss = val_loss / len(val_loader)
    scheduler.step(avg_val_loss)
    
    # Log metrics
    writer.add_scalar('Loss/train', avg_train_loss, epoch)
    writer.add_scalar('Loss/val', avg_val_loss, epoch)
    writer.add_scalar('Learning Rate', optimizer.param_groups[0]['lr'], epoch)
    writer.add_scalar('Perplexity/train', np.exp(avg_train_loss), epoch)
    writer.add_scalar('Perplexity/val', np.exp(avg_val_loss), epoch)
    
    print(f'Epoch {epoch+1} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}')
    
    # Early stopping and checkpointing
    if avg_val_loss < best_val_loss:
        best_val_loss = avg_val_loss
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_state_dict': scheduler.state_dict(),
            'config': CONFIG
        }, CONFIG["MODEL_SAVE_PATH"])
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= CONFIG["EARLY_STOP_PATIENCE"]:
            print("Early stopping triggered")
            break

writer.close()
print(f'Best model saved to {CONFIG["MODEL_SAVE_PATH"]} with validation loss: {best_val_loss:.4f}')

# Advanced generation with multiple sampling strategies
def generate_text(model, start_str, length=200, temperature=CONFIG["TEMPERATURE"],
                 top_k=CONFIG["TOP_K"], top_p=CONFIG["TOP_P"]):
    model.eval()
    chars = list(start_str)
    input_seq = torch.tensor([char_to_idx[ch] for ch in chars], device=device).unsqueeze(0)
    
    with torch.no_grad():
        for _ in tqdm(range(length), desc="Generating text"):
            mask = nn.Transformer.generate_square_subsequent_mask(input_seq.size(1)).to(device)
            outputs, _ = model(input_seq[:, -CONFIG["SEQ_LENGTH"]:], mask)
            logits = outputs[:, -1] / temperature
            
            # Apply nucleus sampling first
            if top_p > 0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
                logits = logits.masked_fill(indices_to_remove, float('-inf'))
            
            # Then apply top-k filtering
            if top_k > 0:
                top_k = min(top_k, logits.size(-1))
                indices_to_remove = logits < torch.topk(logits, top_k)[0][..., -1, None]
                logits = logits.masked_fill(indices_to_remove, float('-inf'))
            
            probs = F.softmax(logits, dim=-1)
            next_char = torch.multinomial(probs, num_samples=1)
            chars.append(idx_to_char[next_char.item()])
            input_seq = torch.cat([input_seq, next_char], dim=1)
    
    return ''.join(chars)

# Generate examples with different parameters
print("\nConservative sampling:")
print(generate_text(model, "The ", temperature=0.5, top_p=0))

print("\nCreative sampling:")
print(generate_text(model, "Once ", temperature=1.2, top_p=0.9))

print("\nTop-k sampling:")
print(generate_text(model, "In ", top_k=50))

print("\nCombined sampling:")
print(generate_text(model, "Artificial intelligence ", temperature=0.8, top_k=50, top_p=0.9))