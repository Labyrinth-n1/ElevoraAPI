import pymupdf
import time
import json
import re
import os
import google.generativeai as genai
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

genai.configure(api_key=GEMINI_API_KEY)

MIN_API_CALL_DELAY_SECONDS = 5
last_api_call_time = 0

# Charger le prompt UNE seule fois
with open("prompt.txt", "r", encoding="utf-8") as f:
    LLM_PROMPT_TEMPLATE = f.read()

# =========================
# PDF EXTRACTION
# =========================
def extract_text_from_pdf(cv_path):
    try:
        full_text = []
        with pymupdf.open(cv_path) as doc:
            for page in doc:
                full_text.append(page.get_text())
        return "\n".join(full_text)
    except Exception as e:
        return "Error extracting the text"

# =========================
# SANITIZATION
# =========================
def sanitize_job_text(text):
    sanitized_text = text
    is_compromised = False

    patterns = [
        r'(ignore|disregard|forget|oublie)\s+(?:all\s+)?(?:previous|prior)?\s*(?:instructions|commands|rules)',
        r'(act\s+as|you\s+are)\s+a\s+\w+',
        r'(show\s+me|display|print|read|cat)',
        r'/etc/passwd|/etc/shadow|/proc/self/environ',
        r'do\s+not\s+(?:analyze|process)',
        r'never\s+say\s+\w+'
    ]

    for pattern in patterns:
        if re.search(pattern, sanitized_text, flags=re.IGNORECASE):
            is_compromised = True
            sanitized_text = re.sub(pattern, ' ', sanitized_text, flags=re.IGNORECASE)

    sanitized_text = re.sub(r'[\\\[\]{}()<>`"\$%^&*+=\|~]', ' ', sanitized_text)
    sanitized_text = re.sub(r'\s+', ' ', sanitized_text).strip()

    return "INVALID_JOB_DESCRIPTION_DUE_TO_INJECTION" if is_compromised else sanitized_text

# =========================
# LLM CALL
# =========================
def get_llm_json_response_with_rate_limit(prompt_text, model_name="gemini-2.5-flash-lite"):
    global last_api_call_time

    try:
        # Rate limiting
        now = time.time()
        if now - last_api_call_time < MIN_API_CALL_DELAY_SECONDS:
            time.sleep(MIN_API_CALL_DELAY_SECONDS - (now - last_api_call_time))

        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt_text)

        text = response.text.strip()

        # Nettoyage markdown
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()

        last_api_call_time = time.time()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "error": "invalid_json_from_llm",
                "raw": text
            }

    except Exception as e:
        return {
            "error": "llm_call_failed",
            "details": str(e)
        }

# =========================
# MAIN LOGIC
# =========================
def analyse_cv(job_text, cv_path):
    pdf_text = extract_text_from_pdf(cv_path)

    if not pdf_text:
        return json.dumps({"error": "empty_pdf"}, ensure_ascii=False)

    sanitized_job_text = sanitize_job_text(job_text)

    if sanitized_job_text == "INVALID_JOB_DESCRIPTION_DUE_TO_INJECTION":
        return json.dumps({
            "nom": "N/A",
            "premier_prenom": "N/A",
            "emails": [],
            "telephones": [],
            "score_compatibilite": "N/A",
            "resume_profil": "N/A",
            "skills": [],
            "resume_experiences_professionnelles": "N/A",
            "points_forts": [],
            "points_faibles": [],
            "recommandations_competences": [],
            "metiers_adaptes": []
        }, ensure_ascii=False)

    prompt = LLM_PROMPT_TEMPLATE.format(
        cv_text=pdf_text,
        job_text=sanitized_job_text
    )

    response = get_llm_json_response_with_rate_limit(prompt)

    return json.dumps(response, ensure_ascii=False)