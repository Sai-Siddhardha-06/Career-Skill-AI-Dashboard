import streamlit as st
import plotly.graph_objects as go
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
import json
import requests
import statistics
import hashlib
from datetime import datetime, timezone

# ==========================================
# 1. SCHEMAS
# ==========================================

class QuizQuestionSchema(BaseModel):
    category: str
    question: str
    options: List[str]
    correct: str

class FullQuizSchema(BaseModel):
    quiz_questions: List[QuizQuestionSchema]

class ResumeAnalysisSchema(BaseModel):
    suggested_role: str
    theory_score: int
    design_score: int
    tools_score: int
    data_pipeline_score: int
    problem_solving_score: int
    soft_skills_score: int

class WeekPlan(BaseModel):
    week_number: int
    focus_area: str
    tasks: List[str]

class RoadmapSchema(BaseModel):
    summary: str
    weeks: List[WeekPlan]

class CommentarySchema(BaseModel):
    imposter_syndrome_analysis: str
    resume_vs_reality_analysis: str

# ==========================================
# 2. CONSTANTS
# ==========================================

CORE_6_PILLARS = {
    "Core Theory": 1,
    "System Design": 1,
    "Tools": 1,
    "Data Pipelines": 1,
    "Problem Solving": 1,
    "Soft Skills": 1,
}

EXPANDED_ROLES = [
    "ML Engineer",
    "Data Scientist",
    "Backend Developer",
    "Frontend Developer",
    "Fullstack Engineer",
    "DevOps / SRE Engineer",
    "Data Engineer",
    "Cloud Architect",
    "Cybersecurity Analyst",
    "Product Manager (Technical)",
]

# Full ordered model list — tried in sequence, fastest/cheapest first.
# Add or remove model IDs here as Google releases new ones.
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-pro-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
]

# ==========================================
# 3. PAGE CONFIG & API CLIENT
# ==========================================

st.set_page_config(page_title="AI Skill Intelligence", page_icon="🎯", layout="wide")

try:
    _api_key = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=_api_key)
except Exception:
    st.error(
        "⚠️ **Gemini API key not found.**\n\n"
        "Create `.streamlit/secrets.toml` in your project folder and add:\n"
        "```\nGEMINI_API_KEY = 'your-key-here'\n```\n"
        "Get a free key at https://aistudio.google.com/apikey"
    )
    st.stop()

# ==========================================
# 4. SESSION STATE
# ==========================================

def _init_state():
    defaults = {
        "quiz_generated": False,
        "quiz_questions": [],
        "user_answers": {},
        "quiz_submitted": False,
        "actual_scores": CORE_6_PILLARS.copy(),
        "roadmap_data": None,
        "commentary_data": None,
        "resume_uploaded": False,
        "resume_pdf_bytes": None,  # Preserves uploaded documents consistently across all views
        "resume_scores": CORE_6_PILLARS.copy(),
        "last_selected_role": "",
        "community_scores": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_state()


def reset_all_assessment_state():
    """Full reset — preserves role selection and resume upload."""
    st.session_state.quiz_generated = False
    st.session_state.quiz_submitted = False
    st.session_state.quiz_questions = []
    st.session_state.user_answers = {}
    st.session_state.actual_scores = CORE_6_PILLARS.copy()
    st.session_state.roadmap_data = None
    st.session_state.commentary_data = None
    st.session_state.resume_uploaded = False
    st.session_state.resume_pdf_bytes = None
    st.session_state.resume_scores = CORE_6_PILLARS.copy()
    st.session_state.community_scores = None

# ==========================================
# 5. FIREBASE (FREE SPARK TIER)
# ==========================================
# Set FIREBASE_PROJECT_ID and FIREBASE_API_KEY in secrets.toml.
# Firestore Spark plan: free, no credit card needed.

def _firebase_enabled():
    try:
        return bool(
            st.secrets.get("FIREBASE_PROJECT_ID")
            and st.secrets.get("FIREBASE_API_KEY")
        )
    except Exception:
        return False


def push_profile_to_cloud(role, perceived, resume, actual):
    if not _firebase_enabled():
        return
    project_id = st.secrets["FIREBASE_PROJECT_ID"]
    api_key    = st.secrets["FIREBASE_API_KEY"]
    url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents/assessments?key={api_key}"
    )

    def iv(v): return {"integerValue": str(int(v))}
    def sv(v): return {"stringValue": str(v)}

    payload = {
        "fields": {
            "target_role":       sv(role),
            "timestamp":         sv(datetime.now(timezone.utc).isoformat()),
            "perceived_theory":  iv(perceived["Core Theory"]),
            "perceived_design":  iv(perceived["System Design"]),
            "perceived_tools":   iv(perceived["Tools"]),
            "perceived_data":    iv(perceived["Data Pipelines"]),
            "perceived_problem": iv(perceived["Problem Solving"]),
            "perceived_soft":    iv(perceived["Soft Skills"]),
            "resume_theory":     iv(resume["Core Theory"]),
            "resume_design":     iv(resume["System Design"]),
            "resume_tools":      iv(resume["Tools"]),
            "resume_data":       iv(resume["Data Pipelines"]),
            "resume_problem":    iv(resume["Problem Solving"]),
            "resume_soft":       iv(resume["Soft Skills"]),
            "actual_theory":     iv(actual["Core Theory"]),
            "actual_design":     iv(actual["System Design"]),
            "actual_tools":      iv(actual["Tools"]),
            "actual_data":       iv(actual["Data Pipelines"]),
            "actual_problem":    iv(actual["Problem Solving"]),
            "actual_soft":       iv(actual["Soft Skills"]),
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code in (200, 201):
            st.toast("☁️ Profile saved to community database!", icon="✅")
    except Exception:
        pass


def fetch_community_scores(role):
    """Returns median actual scores across all Firestore records for this role."""
    if not _firebase_enabled():
        return None
    project_id = st.secrets["FIREBASE_PROJECT_ID"]
    api_key    = st.secrets["FIREBASE_API_KEY"]
    url = (
        f"https://firestore.googleapis.com/v1/projects/{project_id}"
        f"/databases/(default)/documents:runQuery?key={api_key}"
    )
    body = {
        "structuredQuery": {
            "from": [{"collectionId": "assessments"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "target_role"},
                    "op": "EQUAL",
                    "value": {"stringValue": role},
                }
            },
            "limit": 500,
        }
    }
    try:
        resp = requests.post(url, json=body, timeout=5)
        if resp.status_code != 200:
            return None
        records = []
        for item in resp.json():
            doc = item.get("document")
            if not doc:
                continue
            f = doc.get("fields", {})
            records.append({
                "Core Theory":     int(f.get("actual_theory",   {}).get("integerValue", 1)),
                "System Design":   int(f.get("actual_design",   {}).get("integerValue", 1)),
                "Tools":           int(f.get("actual_tools",    {}).get("integerValue", 1)),
                "Data Pipelines":  int(f.get("actual_data",     {}).get("integerValue", 1)),
                "Problem Solving": int(f.get("actual_problem",  {}).get("integerValue", 1)),
                "Soft Skills":     int(f.get("actual_soft",     {}).get("integerValue", 1)),
            })
        if not records:
            return None
        return {
            pillar: round(statistics.median(r[pillar] for r in records), 1)
            for pillar in CORE_6_PILLARS
        }
    except Exception:
        return None

# ==========================================
# 6. HELPERS
# ==========================================

def _normalize_category(raw: str) -> str:
    """Single source of truth: maps any raw category string to one of the 6 pillars."""
    rc = raw.lower()
    if "design" in rc or "architecture" in rc:
        return "System Design"
    if "tool" in rc or "framework" in rc:
        return "Tools"
    if "pipeline" in rc or "data engine" in rc or "etl" in rc:
        return "Data Pipelines"
    if "problem" in rc or "solving" in rc or "logic" in rc:
        return "Problem Solving"
    if "soft" in rc or "product" in rc or "mindset" in rc or "management" in rc:
        return "Soft Skills"
    return "Core Theory"


def _validate_question(q: dict) -> bool:
    """Ensures JSON schemas contain required structures and answers match array indices."""
    if not isinstance(q, dict):
        return False
    options = q.get("options", [])
    if not isinstance(options, list) or len(options) != 4:
        return False
    if q.get("correct") not in options:
        return False
    if not q.get("question", "").strip():
        return False
    return True


def _deduplicate_questions(questions: list) -> list:
    """
    Removes duplicate questions within each category.
    Deduplication is done on the lowercased, stripped question text.
    """
    seen_per_category: dict[str, set] = {k: set() for k in CORE_6_PILLARS}
    unique = []
    for q in questions:
        if not _validate_question(q):
            continue
        cat = _normalize_category(q.get("category", ""))
        key = q.get("question", "").strip().lower()
        if key and key not in seen_per_category[cat]:
            seen_per_category[cat].add(key)
            unique.append(q)
    return unique


def _call_gemini_structured(prompt: str, schema, temperature: float = 0.3):
    """
    Tries every model in GEMINI_MODELS in order.
    Returns (result_dict_or_list, None) on success.
    Returns (None, error_message) if every model fails.
    """
    last_error = "Unknown error."
    for model_name in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=temperature,
                ),
            )
            parsed = json.loads(response.text)
            return parsed, None
        except Exception as e:
            last_error = str(e)
            continue
    return None, (
        f"❌ All {len(GEMINI_MODELS)} Gemini models are currently unavailable or rate-limited.\n\n"
        f"Last error: `{last_error}`\n\n"
        "**What you can do:**\n"
        "- Wait 30–60 seconds and try again.\n"
        "- Check your API key quota at https://aistudio.google.com/\n"
        "- If this persists, Google's API may be experiencing an outage."
    )


def _call_gemini_text(prompt: str, temperature: float = 0.4):
    """
    Tries every model for a plain-text (non-structured) response.
    Returns (text, None) on success, (None, error_message) on total failure.
    """
    last_error = "Unknown error."
    for model_name in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature),
            )
            return response.text, None
        except Exception as e:
            last_error = str(e)
            continue
    return None, (
        f"❌ All {len(GEMINI_MODELS)} Gemini models failed.\n\n"
        f"Last error: `{last_error}`\n\n"
        "Please wait a moment and try again."
    )

# ==========================================
# 7. AI PIPELINES
# ==========================================

def fetch_ai_quiz(role: str, scores: dict, count_per_cat: int):
    """
    Generates a fully unique, adaptive 6-axis quiz.
    Returns (questions_list, error_message).
    On success: (list, None). On failure: (None, str).
    Uniqueness strategy:
      - The prompt explicitly instructs the model to avoid repeating questions.
      - Post-processing deduplication removes any that slip through.
      - If a category ends up short after deduplication, a second API call
        fills only the missing slots for that category.
    """
    base_prompt = f"""
You are an expert technical interviewer for a '{role}' role.
Generate a quiz with EXACTLY {count_per_cat} UNIQUE, NON-REPEATING multiple-choice questions
for EACH of these SIX categories ({count_per_cat * 6} questions total):

1. 'Core Theory'      — difficulty {scores['Core Theory']}/10
2. 'System Design'    — difficulty {scores['System Design']}/10
3. 'Tools'            — difficulty {scores['Tools']}/10
4. 'Data Pipelines'   — difficulty {scores['Data Pipelines']}/10
5. 'Problem Solving'  — difficulty {scores['Problem Solving']}/10
6. 'Soft Skills'      — difficulty {scores['Soft Skills']}/10

Critical rules:
- Every question must be UNIQUE — no two questions may test the same concept or use similar wording.
- Every question must be specifically relevant to the '{role}' role, not generic.
- The 'correct' field MUST exactly match one of the strings in the 'options' array (case-sensitive).
- Provide exactly 4 options per question.
- Do NOT number the questions in the text.
"""

    result, err = _call_gemini_structured(base_prompt, FullQuizSchema, temperature=0.5)
    if err:
        return None, err

    raw_questions = result.get("quiz_questions", [])
    if not raw_questions:
        return None, "❌ The model returned an empty question set. Please try again."

    # Deduplicate
    questions = _deduplicate_questions(raw_questions)

    # Check if any category is short after deduplication
    category_counts = {k: 0 for k in CORE_6_PILLARS}
    for q in questions:
        category_counts[_normalize_category(q["category"])] += 1

    short_categories = {
        cat: count_per_cat - have
        for cat, have in category_counts.items()
        if have < count_per_cat
    }

    # Top-up pass: request only the missing questions for short categories
    if short_categories:
        existing_questions_text = "\n".join(
            f"- [{_normalize_category(q['category'])}] {q['question']}"
            for q in questions
        )
        topup_lines = "\n".join(
            f"  - '{cat}': {need} more questions"
            for cat, need in short_categories.items()
        )
        topup_prompt = f"""
You are an expert technical interviewer for a '{role}' role.
The following questions have already been used — do NOT repeat or paraphrase any of them:
{existing_questions_text}

Generate ONLY the following additional UNIQUE questions (one JSON array, same schema):
{topup_lines}

Same rules apply:
- Questions must be unique from each other AND from the list above.
- Specific to the '{role}' role.
- 'correct' must exactly match one of the 'options' strings.
- 4 options per question.
"""
        topup_result, topup_err = _call_gemini_structured(topup_prompt, FullQuizSchema, temperature=0.6)
        if topup_result:
            topup_questions = topup_result.get("quiz_questions", [])
            all_questions = questions + topup_questions
            questions = _deduplicate_questions(all_questions)

    if not questions:
        return None, "❌ Quiz generation produced no usable questions after deduplication. Please try again."

    return questions, None


def fetch_ai_quiz_with_resume(role, scores, count_per_cat, pdf_bytes):
    """Resume-aware variant: passes the PDF directly to the vision model."""
    prompt = f"""
You are an expert technical interviewer for a '{role}' role.
Analyze the attached resume and generate a PERSONALIZED quiz with EXACTLY {count_per_cat} UNIQUE questions
for each of these SIX categories ({count_per_cat * 6} total):
1. 'Core Theory'      — difficulty {scores['Core Theory']}/10
2. 'System Design'    — difficulty {scores['System Design']}/10
3. 'Tools'            — difficulty {scores['Tools']}/10
4. 'Data Pipelines'   — difficulty {scores['Data Pipelines']}/10
5. 'Problem Solving'  — difficulty {scores['Problem Solving']}/10
6. 'Soft Skills'      — difficulty {scores['Soft Skills']}/10

Rules:
- Every question UNIQUE — no repeated concepts or similar wording.
- Questions must probe the candidate's actual resume experience where relevant.
- 'correct' must exactly match one of the 'options' strings.
- 4 options per question.
"""
    last_error = "Unknown error."
    for model_name in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=FullQuizSchema,
                    temperature=0.5,
                ),
            )
            raw = json.loads(response.text).get("quiz_questions", [])
            questions = _deduplicate_questions(raw)
            if questions:
                return questions, None
        except Exception as e:
            last_error = str(e)
            continue
    return None, (
        f"❌ All models failed during resume-aware quiz generation.\n\n"
        f"Last error: `{last_error}`\n\nFalling back to standard quiz."
    )


def generate_ai_roadmap(role, perceived, resume, actual):
    """Structured 5-week roadmap.
    Returns (dict, None) or (None, error_str)."""
    prompt = f"""
You are an elite engineering mentor.
A candidate targeting '{role}' completed a 6-axis skill assessment.

Profile:
- Perceived self-rating: {perceived}
- Resume signals:        {resume}
- Verified quiz scores:  {actual}

Build a personalized 5-week sprint roadmap targeting their LOWEST verified scores.
For each week provide a 'focus_area' title and 4–6 concrete, actionable checkbox tasks.
The 'summary' should be exactly 2 sentences: what the plan addresses and the expected outcome.
Do not repeat the same task across weeks.
"""
    result, err = _call_gemini_structured(prompt, RoadmapSchema, temperature=0.4)
    if err:
        return None, err
    return result, None


def generate_visual_commentary(role, perceived, resume, actual):
    """Structured executive commentary.
    Returns (dict, None) or (None, error_str)."""
    prompt = f"""
You are a talent analytics expert.
Analyze this 6-axis skill profile for a '{role}' candidate.

Perceived self-rating: {perceived}
Resume signals:        {resume}
Verified quiz scores:  {actual}

Write two analytical paragraphs:
1. 'imposter_syndrome_analysis': Identify specifically which pillars show Imposter Syndrome
   (underestimating) or Dunning-Kruger inflation (overestimating).
   Quantify the gaps.
2. 'resume_vs_reality_analysis': How well do resume signals match verified scores?
   Call out specific aligned pillars and specific gaps with numbers.

Be clinical, constructive, and specific.
No markdown formatting inside the text.
"""
    result, err = _call_gemini_structured(prompt, CommentarySchema, temperature=0.3)
    if err:
        return None, err
    return result, None


def parse_resume(role, pdf_bytes):
    """Parses a resume PDF and returns scored fields.
    Returns (dict, None) or (None, error_str)."""
    resume_prompt = (
        f"You are an expert technical recruiter. Analyze this candidate's resume PDF. "
        f"Evaluate their background for a '{role}' role. Score strictly 1–10 for each field."
    )
    last_error = "Unknown error."
    for model_name in GEMINI_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    resume_prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ResumeAnalysisSchema,
                    temperature=0.2,
                ),
            )
            return json.loads(response.text), None
        except Exception as e:
            last_error = str(e)
            continue
    return None, (
        f"❌ All {len(GEMINI_MODELS)} models failed to parse the resume.\n\n"
        f"Last error: `{last_error}`"
    )

# ==========================================
# 8. SIDEBAR
# ==========================================

st.sidebar.markdown("## 📊 Candidate Profile")
target_role = st.sidebar.selectbox("What role are you targeting?", EXPANDED_ROLES)

# Full reset when role changes
if st.session_state.last_selected_role != target_role:
    reset_all_assessment_state()
    st.session_state.last_selected_role = target_role

st.sidebar.subheader("⚙️ Assessment Settings")
q_per_section = st.sidebar.selectbox("Questions per section:", [3, 5, 10], index=0)
total_expected_questions = q_per_section * 6

st.sidebar.subheader("📊 Rate Your Perceived Skills (1–10)")
self_theory  = st.sidebar.slider("Core Theory / Concepts",        1, 10, 5)
self_design  = st.sidebar.slider("System Design / Architecture",  1, 10, 5)
self_tools   = st.sidebar.slider("Tools & Frameworks",            1, 10, 5)
self_data    = st.sidebar.slider("Data Engineering & Pipelines",  1, 10, 5)
self_problem = st.sidebar.slider("Applied Problem Solving",       1, 10, 5)
self_soft    = st.sidebar.slider("Soft Skills & Product Mindset", 1, 10, 5)

perceived_scores_dict = {
    "Core Theory":     self_theory,
    "System Design":   self_design,
    "Tools":           self_tools,
    "Data Pipelines":  self_data,
    "Problem Solving": self_problem,
    "Soft Skills":     self_soft,
}

# Resume upload
st.sidebar.markdown("---")
st.sidebar.subheader("📄 Resume (optional)")
uploaded_file = st.sidebar.file_uploader("Upload resume PDF for personalized quiz", type=["pdf"])

if uploaded_file:
    st.session_state.resume_pdf_bytes = uploaded_file.read()

if uploaded_file and not st.session_state.resume_uploaded:
    with st.sidebar.spinner("🧠 Parsing resume..."):
        parsed_resume, resume_err = parse_resume(target_role, st.session_state.resume_pdf_bytes)
        if resume_err:
            st.sidebar.error(resume_err)
        else:
            st.session_state.resume_scores["Core Theory"]     = parsed_resume.get("theory_score", 5)
            st.session_state.resume_scores["System Design"]   = parsed_resume.get("design_score", 5)
            st.session_state.resume_scores["Tools"]           = parsed_resume.get("tools_score", 5)
            st.session_state.resume_scores["Data Pipelines"]  = parsed_resume.get("data_pipeline_score", 5)
            st.session_state.resume_scores["Problem Solving"] = parsed_resume.get("problem_solving_score", 5)
            st.session_state.resume_scores["Soft Skills"]     = parsed_resume.get("soft_skills_score", 5)
            st.session_state.resume_uploaded = True
            st.sidebar.success("✅ Resume parsed!")
            st.rerun()

if st.session_state.resume_uploaded:
    rs = st.session_state.resume_scores
    st.sidebar.info(
        f"📋 **Resume Baseline Active**\n"
        f"Theory: {rs['Core Theory']}/10  ·  Design: {rs['System Design']}/10\n"
        f"Tools: {rs['Tools']}/10  ·  Data: {rs['Data Pipelines']}/10\n"
        f"Logic: {rs['Problem Solving']}/10  ·  Soft: {rs['Soft Skills']}/10"
    )

if _firebase_enabled():
    st.sidebar.markdown("---")
    st.sidebar.caption("☁️ Community benchmarking active")

# ==========================================
# 9. MAIN TABS
# ==========================================

st.title("🎯 AI Career Readiness & Skill Intelligence Dashboard")
st.write(f"Evaluating readiness for: **{target_role}**")
st.write("---")

tab1, tab2, tab3 = st.tabs(["📝 Dynamic Assessment", "📊 Skills Analytics", "🗺️ Personalized Roadmap"])

# ------------------------------------------
# TAB 1 — DYNAMIC ASSESSMENT
# ------------------------------------------
with tab1:
    st.header("Adaptive Technical Evaluation")

    if not st.session_state.quiz_generated:
        resume_note = (
            " Your resume has been loaded — questions will be tailored to your background."
            if st.session_state.resume_uploaded
            else ""
        )
        st.write(
            f"Click below to generate a custom **{total_expected_questions}-question** quiz "
            f"tailored to your role and self-assessment.{resume_note}"
        )

        if st.button("🚀 Generate My Dynamic Quiz", type="primary"):
            # Clean light-weight button throttle mechanism
            import time
            current_time = time.time()
            if current_time - st.session_state.get("last_request_time", 0.0) < 5.0:
                st.error("⏳ Rate limit trigger: Please wait a few seconds before trying to generate again.")
            else:
                st.session_state["last_request_time"] = current_time
                with st.spinner(
                    f"🧠 Trying up to {len(GEMINI_MODELS)} Gemini models to build your question set…"
                ):
                    if st.session_state.resume_uploaded and st.session_state.resume_pdf_bytes:
                        questions, err = fetch_ai_quiz_with_resume(
                            target_role, perceived_scores_dict, q_per_section, st.session_state.resume_pdf_bytes
                        )
                        if err:
                            # Resume quiz failed — fall back to standard quiz with a warning
                            st.warning(f"Resume-aware quiz failed: {err}\n\nFalling back to standard quiz.")
                            questions, err = fetch_ai_quiz(target_role, perceived_scores_dict, q_per_section)
                    else:
                        questions, err = fetch_ai_quiz(target_role, perceived_scores_dict, q_per_section)

                    if err:
                        st.error(err)
                    elif not questions:
                        st.error("❌ Quiz generation returned an empty set. Please try again.")
                    else:
                        st.session_state.quiz_questions = questions
                        st.session_state.quiz_generated = True
                        st.rerun()

    if st.session_state.quiz_generated and not st.session_state.quiz_submitted:
        # Count questions per category for display
        category_counts = {k: 0 for k in CORE_6_PILLARS}
        for q in st.session_state.quiz_questions:
            category_counts[_normalize_category(q["category"])] += 1

        total_q = sum(category_counts.values())
        st.info(
            f"💡 **{total_q} unique questions loaded** across 6 categories. "
            "Answer honestly — your results drive the radar chart and roadmap."
        )

        # Group questions by category BEFORE the form
        grouped_questions: dict[str, list] = {k: [] for k in CORE_6_PILLARS}
        for i, q in enumerate(st.session_state.quiz_questions):
            grouped_questions[_normalize_category(q["category"])].append((i, q))

        local_answers = {}

        with st.form("quiz_form"):
            for category_name, q_list in grouped_questions.items():
                if not q_list:
                    continue
                with st.expander(
                    f"📦 {category_name}  ({len(q_list)} questions)", expanded=True
                ):
                    for local_idx, (global_idx, q) in enumerate(q_list):
                        st.markdown(f"**Q{local_idx + 1}. {q['question']}**")
                        local_answers[global_idx] = st.radio(
                            "Select answer:",
                            q["options"],
                            key=f"q_{global_idx}",
                            index=None,
                            label_visibility="collapsed",
                        )
                        st.write("")

            submitted = st.form_submit_button("✅ Submit Assessment", type="primary")

        if submitted:
            st.session_state.user_answers = local_answers

            with st.spinner("Calculating your alignment scores…"):
                category_correct = {k: 0 for k in CORE_6_PILLARS}
                category_total   = {k: 0 for k in CORE_6_PILLARS}

                for i, q in enumerate(st.session_state.quiz_questions):
                    clean_key = _normalize_category(q["category"])
                    category_total[clean_key] += 1
                    user_sel = st.session_state.user_answers.get(i)
                    if user_sel and (
                        str(user_sel).strip().lower() == str(q["correct"]).strip().lower()
                    ):
                        category_correct[clean_key] += 1

                for cat in CORE_6_PILLARS:
                    if category_total[cat] > 0:
                        fraction = category_correct[cat] / category_total[cat]
                        st.session_state.actual_scores[cat] = round(1 + fraction * 9, 1)
                    else:
                        st.session_state.actual_scores[cat] = 1.0

            push_profile_to_cloud(
                target_role,
                perceived_scores_dict,
                st.session_state.resume_scores,
                st.session_state.actual_scores,
            )
            st.session_state.quiz_submitted = True
            st.success("✅ Assessment submitted! Check Tabs 2 and 3 for your results.")
            st.rerun()

    if st.session_state.quiz_submitted:
        st.success("🎉 Assessment complete!")
        st.subheader("Score Breakdown")
        cols = st.columns(3)
        for i, (cat, score) in enumerate(st.session_state.actual_scores.items()):
            with cols[i % 3]:
                delta_vs_perceived = round(
                    score - perceived_scores_dict[cat], 1
                )
                st.metric(
                    cat,
                    f"{score}/10",
                    delta=f"{delta_vs_perceived:+.1f} vs perceived",
                )
        st.write("")
        if st.button("🔄 Reset & Try Again"):
            reset_all_assessment_state()
            st.rerun()

# ------------------------------------------
# TAB 2 — SKILLS ANALYTICS
# ------------------------------------------
with tab2:
    st.header("📋 6-Way Unified Alignment Profile")

    if not st.session_state.quiz_submitted:
        st.warning("🔒 Complete the quiz in Tab 1 to unlock analytics.")
    else:
        cats_loop = [
            "Core Theory", "System Design", "Tools",
            "Data Pipelines", "Problem Solving", "Soft Skills", "Core Theory",
        ]
        perceived_loop = [
            self_theory, self_design, self_tools,
            self_data, self_problem, self_soft, self_theory,
        ]
        resume_loop  = [st.session_state.resume_scores[c] for c in cats_loop]
        actual_loop  = [st.session_state.actual_scores[c]  for c in cats_loop]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=perceived_loop, theta=cats_loop, fill="toself",
            name="Perceived (self-rated)", line=dict(color="#5b8dee"),
        ))
        fig.add_trace(go.Scatterpolar(
            r=resume_loop, theta=cats_loop, fill="toself",
            name="Resume Profile", line=dict(color="#ffc107", dash="dash"),
        ))
        fig.add_trace(go.Scatterpolar(
            r=actual_loop, theta=cats_loop, fill="toself",
            name="Verified (quiz)", line=dict(color="#e8605a", width=3),
        ))

        # Community benchmark (Firebase)
        if st.session_state.community_scores is None:
            with st.spinner("Fetching community benchmark…"):
                st.session_state.community_scores = fetch_community_scores(target_role)

        if st.session_state.community_scores:
            community_loop = [st.session_state.community_scores[c] for c in cats_loop]
            fig.add_trace(go.Scatterpolar(
                r=community_loop, theta=cats_loop, fill="toself",
                name="Community Median", line=dict(color="#7cfc00", dash="dot", width=1.5),
                opacity=0.6,
            ))

        fig.update_layout(
            polar=dict(
                bgcolor="#000000",
                radialaxis=dict(
                    visible=True, range=[0, 10],
                    gridcolor="#2a2d3d", linecolor="#3a3d4d",
                    tickfont=dict(color="#8890aa"),
                ),
                angularaxis=dict(
                    gridcolor="#2a2d3d", linecolor="#3a3d4d",
                    tickfont=dict(color="#c9cfe0"),
                ),
            ),
            paper_bgcolor="#000000",
            font=dict(color="#c9cfe0", family="monospace"),
            showlegend=True,
            title="Triangulated Alignment Matrix (6 Dimensions)",
            margin=dict(t=50, b=50, l=50, r=50),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("🧠 Executive Interpretation")

        if st.session_state.commentary_data is None:
            if st.button("Generate Statistical Narrative Analysis", type="primary"):
                with st.spinner(f"🧠 Analyzing gaps across {len(GEMINI_MODELS)} models…"):
                    result, err = generate_visual_commentary(
                        target_role,
                        perceived_scores_dict,
                        st.session_state.resume_scores,
                        st.session_state.actual_scores,
                    )
                    if err:
                        st.error(err)
                    else:
                        st.session_state.commentary_data = result
                        st.rerun()
        else:
            cd = st.session_state.commentary_data
            if isinstance(cd, dict):
                st.markdown("**Self-Assessment Calibration**")
                st.info(cd.get("imposter_syndrome_analysis", ""))
                st.markdown("**Resume vs. Reality**")
                st.info(cd.get("resume_vs_reality_analysis", ""))
            else:
                st.info(str(cd))
            if st.button("🔄 Recalculate Narrative"):
                st.session_state.commentary_data = None
                st.rerun()

# ------------------------------------------
# TAB 3 — PERSONALIZED ROADMAP
# ------------------------------------------
with tab3:
    st.header("🗺️ AI-Generated Learning Pathway")

    if not st.session_state.quiz_submitted:
        st.info("🔒 Complete the assessment in Tab 1 to unlock your custom roadmap.")
    else:
        if st.session_state.roadmap_data is None:
            st.write("Click below to generate your personalized 5-week sprint plan.")
            if st.button("🗺️ Generate My Custom Learning Roadmap", type="primary"):
                with st.spinner(f"🧠 Building milestone plan (trying up to {len(GEMINI_MODELS)} models)…"):
                    result, err = generate_ai_roadmap(
                        target_role,
                        perceived_scores_dict,
                        st.session_state.resume_scores,
                        st.session_state.actual_scores,
                    )
                    if err:
                        st.error(err)
                    else:
                        st.session_state.roadmap_data = result
                        st.rerun()
        else:
            rd = st.session_state.roadmap_data
            col1, col2 = st.columns([6, 1])
            with col1:
                st.success("🎯 Your custom roadmap is ready!")
            with col2:
                if st.button("🔄 Rebuild"):
                    st.session_state.roadmap_data = None
                    st.rerun()

            st.markdown("---")

            if isinstance(rd, dict):
                summary = rd.get("summary", "")
                if summary:
                    st.info(summary)

                weeks = rd.get("weeks", [])
                if not weeks:
                    st.warning("Roadmap returned empty. Please regenerate.")
                else:
                    # ASCII sprint flowchart
                    flow_parts = [
                        f"[Week {w['week_number']}: {w['focus_area']}]" for w in weeks
                    ]
                    flow_text = "\n          |\n          v\n".join(flow_parts)
                    st.code(flow_text, language=None)
                    st.markdown("---")

                    for week in weeks:
                        with st.expander(
                            f"📅 Week {week['week_number']}: {week['focus_area']}",
                            expanded=(week["week_number"] == 1),
                        ):
                            for task in week.get("tasks", []):
                                # Cryptographically stable checksum string protects checkbox states across application reruns
                                safe_key = f"task_w{week['week_number']}_{hashlib.md5(task.encode()).hexdigest()[:16]}"
                                st.checkbox(task, key=safe_key)
            else:
                st.markdown(str(rd))