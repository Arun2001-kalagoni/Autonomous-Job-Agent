from groq import Groq
from src.database import get_chroma_collection

# 1. Setup Groq Cloud Model Configuration
# We will use Llama 3.1 8B hosted entirely on Groq's supercomputers (0% Mac CPU usage!)
import os
client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
CLOUD_MODEL = "llama-3.1-8b-instant"

def get_answer_from_resume(question):
    # --- STEP 1: RETRIEVAL ---
    collection = get_chroma_collection()
    results = collection.query(
        query_texts=[question],
        n_results=3
    )
    
    context = "\n".join(results['documents'][0])

    # --- STEP 2: AUGMENTATION ---
    prompt = f"""
    You are an AI assistant helping Arun Kalagoni with a job application.
    Based ONLY on the resume fragments below, answer the question.
    
    RESUME FRAGMENTS:
    {context}
    
    QUESTION: 
    {question}
    
    INSTRUCTION: 
    Respond in the first person as Arun. If the answer isn't in the fragments, 
    say "Information not found in resume."
    """

    # --- STEP 3: GENERATION ---
    # Call Groq's cloud server instead of our local machine
    response = client.chat.completions.create(
        model=CLOUD_MODEL,
        messages=[{'role': 'user', 'content': prompt}]
    )
    
    return response.choices[0].message.content

import json

def evaluate_job_match(job_title, job_description):
    """
    Evaluates how well the job description matches Arun's resume using RAG.
    Returns a dict with 'score' (0-100) and 'reasoning'.
    """
    collection = get_chroma_collection()
    
    # Query Chroma for chunks relevant to the job description to find matching skills.
    results = collection.query(
        query_texts=[job_description],
        n_results=5 # get more context since job descriptions are long
    )
    
    context = "\n".join(results['documents'][0])
    
    prompt = f"""
    You are an AI career advisor for Arun Kalagoni.
    Based ONLY on Arun's resume fragments below, evaluate if he is a good fit for this job.
    
    RESUME FRAGMENTS:
    {context}
    
    JOB TITLE: {job_title}
    JOB DESCRIPTION: 
    {job_description}
    
    CRITERIA:
    - Compare the job requirements to Arun's skills.
    - Provide a score from 0 to 100 on how well he matches.
    - Output MUST be valid JSON in this exact format:
      {{"score": 85, "reasoning": "explanation..."}}
    """
    
    response = client.chat.completions.create(
        model=CLOUD_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        response_format={"type": "json_object"} # Groq natively forces perfect JSON!
    )
    
    # Extract the string content
    raw_response = response.choices[0].message.content.strip()
    try:
        return json.loads(raw_response)
    except Exception as e:
        print(f"Failed to parse JSON response: {e}\nRaw output: {raw_response}")
        return {"score": 0, "reasoning": "Failed to evaluate."}

def answer_screener_question(question_text, input_type, options=None):
    """
    Given a screening question from an employer, uses the RAG memory to definitively answer it.
    Output is strictly formatted so it can be mechanically injected into the text boxes.
    """
    collection = get_chroma_collection()
    results = collection.query(
        query_texts=[question_text], 
        n_results=3 
    )
    context_text = "\n\n".join(results['documents'][0]) if results and results['documents'] else "No relevant resume context found."
    profile_data = "{}"
    try:
        import os, json
        if os.path.exists("data/profile.json"):
            with open("data/profile.json", "r") as f:
                profile_data = json.dumps(json.load(f), indent=2)
    except Exception:
        pass
    
    options_str = f"Available Options: {options}" if options else ""
    
    prompt = f"""
You are Arun Kalagoni, an applicant determining the answer to a job screening question.
Look ONLY at these Resume Fragments:
{context_text}

Look ONLY at this User Profile (Demographic/Legal Preferences):
{profile_data}

Employer Question: '{question_text}'
Input Type: {input_type}
{options_str}

CRITICAL RULES:
1. If the input is a Dropdown or Radio, you MUST return exactly one of the Options verbatim. DO NOT EXPLAIN.
2. If the question asks for "Years of Experience" or any numeric value, you MUST return ONLY a mathematical integer (e.g. "3", "5"). If you lack experience, return "0". NEVER include text like "years".
3. If the input is a Yes/No question, return exactly "Yes" or "No".
4. ABSOLUTELY NO CONVERSATION OR EXPLANATIONS. DO NOT output complete sentences. You are acting as an API that generates raw data variables.
5. DO NOT OUTPUT JSON. Output ONLY the raw data string that should be typed directly into the UI text box.
6. DEMOGRAPHICS, LOGISTICS & COMPLIANCE: Use the provided 'User Profile (Demographic/Legal Preferences)' JSON to definitively answer ALL questions regarding demographics, race, legal status, visa sponsorship, conflicts of interest, corporate consent, logistics, and contact preferences. If the question asks about hybrid/onsite work, LinkedIn URLs, career events, how you heard about the job, or personal details (country, state, city, phone), use the JSON data to answer strictly. Match the Profile Data concepts to the specific federal labels/options provided to you. If the question is an open-ended essay question ("Why do you want to work here?"), generate a highly professional, generic 1-sentence answer based on the resume.
"""
    try:
        response = client.chat.completions.create(
            model=CLOUD_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error querying Groq for Form Question: {e}")
        return "Yes" # Safe fallback for binary forms

if __name__ == "__main__":
    query = "What did I do at Wells Fargo regarding SQL and Redshift?"
    try:
        answer = get_answer_from_resume(query)
        print(f"\n✅ AI ANSWER:\n{answer}")
    except Exception as e:
        print(f"❌ Still having trouble: {e}")