# rag_engine.py
from langchain_community.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.docstore.document import Document
from pathlib import Path
import json
import os
import requests
from bs4 import BeautifulSoup

# Declare global variables
global params
params = None
_vector_store = None

# Load parameters globally
with open("parameters.json", "r") as f:
    global_params = json.load(f)
    params_file = global_params["rag_parameters"]
    with open(params_file, "r") as f:
        params = json.load(f)

EMBED_MODEL = params["embed_model"]

# need to retrieve from the hellointerview wesbite andstore the text in the documents folder
def retrieve_text_single_topic(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the main content - adjust selectors based on the website structure
        main_content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
        
        if main_content:
            # Get all text content, removing extra whitespace
            text = ' '.join(main_content.stripped_strings)
            return text
        else:
            raise ValueError("Could not find main content on the page")
            
    except requests.RequestException as e:
        raise Exception(f"Failed to retrieve content: {str(e)}")
    
# only retrive it once
def retrieve_text_all_topics():
    if not os.path.exists("documents"):
        os.makedirs("documents")
    for topic in params["topics"]:
        url = params["base_url"] + topic
        text = retrieve_text_single_topic(url)
        store_text(text, f"documents/{topic}.txt")

def store_text(text: str, text_path: str = "documents/hello_interview.txt"):
    with open(text_path, "w") as f:
        f.write(text)

def _build_store():
    """Build vector store from all documents in the documents directory."""
    all_texts = []
    for file in os.listdir("documents"):
        if file.endswith(".txt"):
            text = Path(f"documents/{file}").read_text(encoding="utf-8")
            all_texts.append(text)
    
    splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = splitter.create_documents(all_texts)
    embedder = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    return Chroma.from_documents(docs, embedder)

def initialize_rag():
    """Initialize the RAG system by retrieving texts and building the vector store."""
    global _vector_store
    retrieve_text_all_topics()
    _vector_store = _build_store()

def get_snippets(query: str, k: int = 4) -> str:
    """Return top-k snippets concatenated for prompt injection."""
    if _vector_store is None:
        initialize_rag()
    matches = _vector_store.similarity_search(query, k=k)
    return "\n\n".join(d.page_content for d in matches)

# Initialize RAG system when module is imported
initialize_rag()
