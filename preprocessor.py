import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from spacy.lang.en import English
from transformers import pipeline
import re
from spacy.cli import download
import spacy

# # Try to load the model, and if it doesn't exist, download it
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)

# Initialize NLTK stopwords
stop_words = set(stopwords.words("english"))

def clean_text(text):
    """Remove non-alphanumeric characters and unnecessary spaces."""
    text = re.sub(r"[^A-Za-z0-9\s]", "", text)  # Remove special characters
    text = re.sub(r"\s+", " ", text)  # Remove multiple spaces
    text = text.strip()  # Remove leading/trailing whitespaces
    return text

def remove_stopwords(text):
    """Remove common stopwords from the text."""
    word_tokens = word_tokenize(text)
    filtered_text = [word for word in word_tokens if word.lower() not in stop_words]
    return " ".join(filtered_text)

def lemmatize_text(text):
    """Lemmatize the text to get base word forms."""
    doc = nlp(text)
    lemmatized_text = [token.lemma_ for token in doc]
    return " ".join(lemmatized_text)

def preprocess_text(text):
    """Preprocess the text before sending it to the LLM."""
    text = clean_text(text)
    text = remove_stopwords(text)
    text = lemmatize_text(text)
    
    return text
