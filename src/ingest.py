import os
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from src.database import get_chroma_collection  # Importing the function we just wrote!

def ingest_resume(file_path):
    # 1. Initialize our Memory
    collection = get_chroma_collection()

    # 2. Extract Text from PDF
    reader = PdfReader(file_path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text()
    
    # 3. Chunk the Text
    # We don't want the AI to get confused, so we split by 500 characters
    # with a small overlap so no context is lost in the "cuts".
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(full_text)

    # 4. Add to ChromaDB
    # We create unique IDs for each chunk (e.g., chunk_0, chunk_1...)
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    
    collection.add(
        documents=chunks,
        ids=ids
    )
    
    print(f"✅ Successfully ingested {len(chunks)} career memory fragments.")

if __name__ == "__main__":
    # Ensure your resume is in the data folder!
    RESUME_PATH = "data/resume.pdf" 
    if os.path.exists(RESUME_PATH):
        ingest_resume(RESUME_PATH)
    else:
        print(f"❌ Error: Place your resume.pdf in the {RESUME_PATH} folder first!")