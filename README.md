# 🎯 AI Career Readiness & Skill Intelligence Dashboard

An AI-powered adaptive assessment platform built with Streamlit, Gemini, Plotly, and Firebase.

This project evaluates candidate readiness for technical roles using:
- Dynamic AI-generated quizzes
- Resume-aware personalized assessments
- Multi-model Gemini fallback orchestration
- Radar-chart analytics
- Community benchmarking
- AI-generated learning roadmaps
- Skill-gap narrative analysis

---

# 🚀 Features

## ✅ Adaptive AI Quiz Generation
Generates unique technical interview questions across 6 skill pillars:
- Core Theory
- System Design
- Tools & Frameworks
- Data Pipelines
- Problem Solving
- Soft Skills

Questions dynamically adapt based on:
- target role
- self-assessment scores
- uploaded resume content

---

## ✅ Resume-Aware Personalization
Upload a PDF resume and the system:
- analyzes experience using Gemini
- estimates baseline capability scores
- generates personalized interview questions

---

## ✅ Multi-Model Gemini Fallback System
The application automatically retries across multiple Gemini models if:
- a model is overloaded
- rate-limited
- temporarily unavailable
- returns malformed output

Supported models include:
- gemini-2.5-flash
- gemini-2.5-pro
- gemini-2.0-flash
- gemini-2.0-flash-lite
- gemini-2.0-pro-exp
- gemini-1.5-flash
- gemini-1.5-flash-8b
- gemini-1.5-pro

---

## ✅ Structured Output Validation
Uses Pydantic schemas for:
- quiz validation
- roadmap generation
- commentary generation
- resume analysis

---

## ✅ Community Benchmarking
Optional Firebase integration stores anonymous score distributions and displays:
- community medians
- comparative radar analytics

---

## ✅ AI-Generated Learning Roadmaps
Creates personalized 5-week learning sprint plans targeting:
- weakest verified skills
- calibration gaps
- missing technical depth

---

# 🔄 Workflow

1. User selects a target technical role.
2. User self-rates across 6 engineering skill dimensions.
3. Optional resume upload enables personalized assessment generation.
4. Gemini generates adaptive technical interview questions.
5. Quiz performance is evaluated against perceived and resume-based scores.
6. Analytics visualizations and AI-generated learning roadmaps are produced.

---

# 🧠 Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application |
| Streamlit | Frontend/UI |
| Google Gemini API | AI generation |
| Plotly | Radar analytics visualization |
| Firebase Firestore | Community benchmarking |
| Pydantic | Structured schema validation |

---

# 📂 Project Structure

```bash
project/
│
├── app.py
├── requirements.txt
├── README.md
│
└── .streamlit/
    └── secrets.toml
```

---

# 🌐 Live Demo

Try the deployed application here:

https://career-skill-ai-dashboard-acwqfaptgjlewt3whvzprh.streamlit.app

---

# ⚙️ Installation & Setup

## 1. Clone the Repository

```bash
git clone https://github.com/Sai-Siddhardha-06/Career-Skill-AI-Dashboard.git
cd Career-Skill-AI-Dashboard
```

---

## 2. Create a Virtual Environment (Recommended)

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# 🔑 Configure API Keys

Create the following file:

```bash
.streamlit/secrets.toml
```

Add your Gemini API key:

```toml
GEMINI_API_KEY = "your-api-key"
```

Get your API key from:

https://aistudio.google.com/apikey

---

# ☁️ Optional Firebase Setup

To enable community benchmarking, also add:

```toml
FIREBASE_PROJECT_ID = "your-project-id"
FIREBASE_API_KEY = "your-firebase-api-key"
```

inside `.streamlit/secrets.toml`

---

# ▶️ Run the Application

Start the Streamlit app:

```bash
streamlit run app.py
```

The application will open in your browser at:

```text
http://localhost:8501
```

---

# 📦 Requirements

Install all dependencies using:

```bash
pip install -r requirements.txt
```
