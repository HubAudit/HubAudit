import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import nltk
from nltk.util import ngrams
from collections import Counter
import numpy as np

# Download NLTK resources if you haven't already
nltk.download('punkt')

nltk.download('stopwords')


class TextDataset(Dataset):
    def __init__(self, filepath, n=3, min_freq=1):  # n-gram size, minimum frequency
        self.n = n
        self.data = self.load_and_preprocess(filepath, min_freq)

    def load_and_preprocess(self, filepath, min_freq):
        with open(filepath, 'r', encoding='utf-8') as f:  # Handle encoding
            text = f.read()

        # Tokenization and lowercasing
        tokens = nltk.word_tokenize(text.lower())

        # N-gram creation and frequency counting
        n_grams = ngrams(tokens, self.n)
        ngram_counts = Counter(n_grams)

        # Filtering based on minimum frequency
        filtered_ngrams = [ngram for ngram, count in ngram_counts.items() if count >= min_freq]

        # Vocabulary creation
        self.vocabulary = sorted(set(token for ngram in filtered_ngrams for token in ngram))
        self.word_to_index = {word: index for index, word in enumerate(self.vocabulary)}
        self.index_to_word = {index: word for word, index in self.word_to_index.items()}

        # Data preparation for PyTorch
        data = []
        for ngram in filtered_ngrams:
            context = [self.word_to_index[token] for token in ngram[:-1]]
            target = self.word_to_index[ngram[-1]]
            data.append((context, target))
        return data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        context, target = self.data[idx]
        return torch.tensor(context), torch.tensor(target)


class LanguageModel(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim):
        super(LanguageModel, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)
        self.lstm = nn.LSTM(embedding_dim, hidden_dim, batch_first=True)  # Use LSTM
        self.linear = nn.Linear(hidden_dim, vocab_size)

    def forward(self, context):
        embedded = self.embedding(context)
        output, _ = self.lstm(embedded)  # LSTM output
        output = self.linear(output[:, -1, :])  # Get the last timestep's output
        return output


# Training parameters
filepath = 'dataset.txt'  # Replace with your dataset file
n_gram_size = 3
min_frequency = 2  # Adjust as needed
embedding_dimension = 32
hidden_dimension = 64
learning_rate = 0.01
batch_size = 32
epochs = 10

# Data loading and preprocessing
dataset = TextDataset(filepath, n_gram_size, min_frequency)
dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

# Model initialization
vocab_size = len(dataset.vocabulary)
model = LanguageModel(vocab_size, embedding_dimension, hidden_dimension)

# Loss function and optimizer
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=learning_rate)

# Training loop
for epoch in range(epochs):
    for contexts, targets in dataloader:
        optimizer.zero_grad()
        outputs = model(contexts)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

    print(f"Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}")

# Save the trained model
torch.save(model.state_dict(), 'language_model.pth')

print("Training complete. Model saved as language_model.pth")



# Example of text generation (after training and loading)
def generate_text(model, dataset, start_sequence="the", max_length=50):
    model.eval()  # Set to evaluation mode
    tokens = start_sequence.split() # start sequence as list of tokens
    context = [dataset.word_to_index[token] for token in tokens]
    context_tensor = torch.tensor([context]) # wrap the context list to a tensor and add one dimension

    generated_text = tokens[:] # start with the start sequence

    for _ in range(max_length):
        with torch.no_grad():
            output = model(context_tensor)
            predicted_index = torch.argmax(output).item()
            predicted_word = dataset.index_to_word[predicted_index]
            generated_text.append(predicted_word)
            context.append(predicted_index) # update context with the new predicted word
            context = context[-n_gram_size+1:] # keep the context of n-gram size
            context_tensor = torch.tensor([context]) # update the context tensor
            
            if predicted_word == ".": # stop if the predicted word is end of sentence
                break

    return " ".join(generated_text)

# Example usage (after training and saving)
# Load the model
model = LanguageModel(vocab_size, embedding_dimension, hidden_dimension)
model.load_state_dict(torch.load('language_model.pth'))
model.eval()

generated_text = generate_text(model, dataset, start_sequence="the quick brown")
print(generated_text)