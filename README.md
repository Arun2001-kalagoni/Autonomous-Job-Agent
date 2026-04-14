# 🤖 Autonomous AI Job Application Agent

An intelligent, autonomous Python agent that automatically searches job boards (Glassdoor), mathematically evaluates job descriptions against your resume context, and mechanically parses and fills out application forms using LLMs.

## 🌟 Key Features

*   **Anti-Bot Bypassing:** Utilizes `playwright-stealth` and persistent browser session fingerprinting to navigate heavily obfuscated Single Page Applications.
*   **RAG-Powered AI Brain (`src/brain.py`):** Uses an internal ChromaDB vector store hooked up to a Llama-3.1 model (via Groq API) to extract unstructured requirements from job postings and intelligently score them against your localized resume.
*   **Dynamic Form Parsing (`src/form_filler.py`):** Mechanically iterates through highly unstandardized employer application modals, parsing text areas, extracting radio button groups, and utilizing the LLM to instantly type out custom answers to pre-screening questions.
*   **Local Database Memory (`src/database.py`):** Tracks application states and historical evaluations into a local SQLite tracking database, preventing duplicate applications.

## 🛠️ Architecture Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repo-link>
   cd project-ai-agent
   ```

2. **Install Dependencies:**
   ```bash
   pip install playwright playwright-stealth groq chromadb pypdf langchain-text-splitters
   playwright install chromium
   ```

3. **Configure the Brain:**
   * Create a `data/` directory.
   * Drop your `.pdf` resume inside the `data/` directory.
   * Set your `GROQ_API_KEY` either as a system environment variable or inside an `.env` file!

4. **Initialize the Agent Memory:**
   Run the ingestion script to chunk and vectorize your resume into ChromaDB:
   ```bash
   python src/ingest.py
   ```

## 🚀 Usage

You must log in to Glassdoor manually once to pass the initial bot-checks. Run:
```bash
python src/automation.py setup
```
*(Press Enter when successfully logged in to save the session state locally).*

**Start the Autonomous Applier:**
```bash
python app.py
```
The terminal will prompt you for your desired target position, location, and the maximum age of the listing. The bot will then take over the browser completely.

## ⚠️ Safety Protocols
Because the bot directly handles PII (Personally Identifiable Information), it implements a strict **Human-in-the-Loop** circuit breaker. Upon reaching the final stages of an application, the bot will intentionally freeze and issue a terminal alert, giving the user explicit veto-power over the final `Submit` click.
