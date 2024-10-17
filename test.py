# Import library yang diperlukan
import torch
from transformers import BertTokenizer, BertForSequenceClassification
from transformers import Trainer, TrainingArguments
from datasets import load_dataset

# Pastikan menggunakan GPU jika tersedia
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Muat dataset
dataset = load_dataset("imdb")

# Lihat contoh data
print(dataset['train'][0])

# Tokenisasi
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

def tokenize_function(examples):
    return tokenizer(examples['text'], padding='max_length', truncation=True)

# Terapkan tokenisasi
tokenized_datasets = dataset.map(tokenize_function, batched=True)

# Siapkan model
model = BertForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=2)
model.to(device)  # Pindahkan model ke device

# Atur parameter pelatihan
training_args = TrainingArguments(
    output_dir='./results',          
    evaluation_strategy="epoch",     
    learning_rate=2e-5,              
    per_device_train_batch_size=16,  
    per_device_eval_batch_size=16,   
    num_train_epochs=3,               
    weight_decay=0.01,                
)

# Buat Trainer
trainer = Trainer(
    model=model,                        
    args=training_args,                  
    train_dataset=tokenized_datasets['train'],   
    eval_dataset=tokenized_datasets['test']      
)

# Mulai pelatihan
trainer.train()

# Evaluasi model
results = trainer.evaluate()
print(results)

# Simpan model
model.save_pretrained('./my_model')
tokenizer.save_pretrained('./my_model')
