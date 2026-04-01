"""
llm_engine.py  –  Multi-backend LLM support
Priority:  1. Ollama (offline/free)  2. Groq (free cloud)  3. Together AI  4. HuggingFace
"""
import time
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are CareerBot, an expert AI career assistant built into InternConnect — an internship & career platform for students in India.

Your role is to help students with:
1. **Career Guidance** – career paths, choosing the right field, growth roadmaps
2. **Internship Help** – how to apply, what to write in cover letters, tips to get selected
3. **Application Status** – explain what Pending/Approved/Rejected means and next steps
4. **Resume & CV** – writing tips, what to include, ATS-friendly formatting
5. **Interview Preparation** – common questions, how to prepare, confidence tips
6. **Skill Development** – which skills to learn for which sector, free resources
7. **Platform Help** – how to use InternConnect features (apply, view mentors, check status)
8. **Doubts & Questions** – answer any student query patiently and thoroughly

Platform Context:
- Students can apply to internships across sectors: Technology, Finance, Marketing, Engineering, Healthcare, Education, Legal, Design, Logistics, Agriculture
- Internships can be Remote, Onsite, or Hybrid
- Duration: 1, 2, 3, 6, or 12 months
- Students can chat with mentors for personalized guidance
- Applications go through: Pending → Approved/Rejected

Tone: Friendly, encouraging, professional. Use simple English (students may be from Hindi medium backgrounds). Keep answers concise but complete. Use bullet points when listing multiple items. Always end with an encouraging note or offer to help further.

If asked something outside career/internship/education scope, politely redirect to career topics.
"""

# ─── BACKEND CLASSES ──────────────────────────────────────────────────────────

class OllamaBackend:
    """Ollama – runs 100% offline on the server. Install: https://ollama.ai"""
    NAME = "ollama"
    BASE_URL = "http://localhost:11434"
    # Fast models (pick one based on your RAM):
    # qwen2.5:0.5b  →  ~400MB, fastest
    # qwen2.5:1.5b  →  ~1GB, better quality
    # llama3.2:1b   →  ~700MB, good general
    # mistral:7b    →  ~4GB, best quality
    DEFAULT_MODEL = getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:1.5b')

    def is_available(self):
        try:
            r = requests.get(f"{self.BASE_URL}/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def chat(self, messages: list, model: str = None) -> dict:
        model = model or self.DEFAULT_MODEL
        t0 = time.time()
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 600,
            }
        }
        try:
            r = requests.post(
                f"{self.BASE_URL}/api/chat",
                json=payload,
                timeout=60
            )
            r.raise_for_status()
            data = r.json()
            elapsed = int((time.time() - t0) * 1000)
            return {
                "content": data["message"]["content"],
                "model": model,
                "backend": self.NAME,
                "tokens": data.get("eval_count", 0),
                "ms": elapsed,
                "ok": True,
            }
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return {"ok": False, "error": str(e)}

    def stream_chat(self, messages: list, model: str = None):
        """Generator that yields text chunks for streaming response."""
        model = model or self.DEFAULT_MODEL
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "stream": True,
            "options": {"temperature": 0.7, "num_predict": 600}
        }
        try:
            with requests.post(
                f"{self.BASE_URL}/api/chat",
                json=payload,
                stream=True,
                timeout=60
            ) as r:
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
                        if data.get("done"):
                            break
        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            yield f"\n\n⚠️ Connection error: {e}"


class GroqBackend:
    """Groq – free cloud, extremely fast (LPU hardware). Get key: https://console.groq.com"""
    NAME = "groq"
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant')
    # Other free Groq models: gemma2-9b-it, mixtral-8x7b-32768, llama3-70b-8192

    def is_available(self):
        return bool(getattr(settings, 'GROQ_API_KEY', ''))

    def chat(self, messages: list, model: str = None) -> dict:
        api_key = getattr(settings, 'GROQ_API_KEY', '')
        if not api_key:
            return {"ok": False, "error": "No GROQ_API_KEY in settings"}
        model = model or self.DEFAULT_MODEL
        t0 = time.time()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "temperature": 0.7,
            "max_tokens": 600,
            "stream": False,
        }
        try:
            r = requests.post(self.BASE_URL, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            elapsed = int((time.time() - t0) * 1000)
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": model,
                "backend": self.NAME,
                "tokens": data.get("usage", {}).get("completion_tokens", 0),
                "ms": elapsed,
                "ok": True,
            }
        except Exception as e:
            logger.error(f"Groq error: {e}")
            return {"ok": False, "error": str(e)}

    def stream_chat(self, messages: list, model: str = None):
        api_key = getattr(settings, 'GROQ_API_KEY', '')
        model = model or self.DEFAULT_MODEL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "temperature": 0.7,
            "max_tokens": 600,
            "stream": True,
        }
        try:
            with requests.post(self.BASE_URL, json=payload, headers=headers, stream=True, timeout=30) as r:
                for line in r.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: ") and line != "data: [DONE]":
                            data = json.loads(line[6:])
                            chunk = data["choices"][0].get("delta", {}).get("content", "")
                            if chunk:
                                yield chunk
        except Exception as e:
            logger.error(f"Groq stream error: {e}")
            yield f"\n\n⚠️ Error: {e}"


class TogetherAIBackend:
    """Together AI – free $1 credit on signup, cheap after. Fast inference."""
    NAME = "together"
    BASE_URL = "https://api.together.xyz/v1/chat/completions"
    DEFAULT_MODEL = getattr(settings, 'TOGETHER_MODEL', 'Qwen/Qwen2.5-7B-Instruct-Turbo')

    def is_available(self):
        return bool(getattr(settings, 'TOGETHER_API_KEY', ''))

    def chat(self, messages: list, model: str = None) -> dict:
        api_key = getattr(settings, 'TOGETHER_API_KEY', '')
        model = model or self.DEFAULT_MODEL
        t0 = time.time()
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "temperature": 0.7, "max_tokens": 600,
        }
        try:
            r = requests.post(self.BASE_URL, json=payload, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "model": model, "backend": self.NAME,
                "tokens": data.get("usage", {}).get("completion_tokens", 0),
                "ms": int((time.time() - t0) * 1000), "ok": True,
            }
        except Exception as e:
            logger.error(f"Together error: {e}")
            return {"ok": False, "error": str(e)}

    def stream_chat(self, messages: list, model: str = None):
        # Same pattern as Groq (OpenAI-compatible)
        api_key = getattr(settings, 'TOGETHER_API_KEY', '')
        model = model or self.DEFAULT_MODEL
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "temperature": 0.7, "max_tokens": 600, "stream": True,
        }
        try:
            with requests.post(self.BASE_URL, json=payload, headers=headers, stream=True, timeout=30) as r:
                for line in r.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: ") and line != "data: [DONE]":
                            data = json.loads(line[6:])
                            chunk = data["choices"][0].get("delta", {}).get("content", "")
                            if chunk:
                                yield chunk
        except Exception as e:
            yield f"\n\n⚠️ Error: {e}"


# ─── FALLBACK RULE-BASED BOT ──────────────────────────────────────────────────

FALLBACK_RESPONSES = {
    "apply": "To apply for an internship:\n1. Go to **Internships** page\n2. Click on any internship card\n3. Press **Apply Now** button\n4. Your application is submitted! Track it under **My Applications**.\n\nTip: Make sure your profile is complete before applying.",
    "status": "Your application status can be:\n• **Pending** – Mentor has not reviewed yet, wait patiently\n• **Approved** ✅ – Congratulations! Check mentor feedback for next steps\n• **Rejected** ❌ – Don't be discouraged. Read mentor feedback and apply to others\n\nCheck **My Applications** page to see your status.",
    "resume": "Resume tips for students:\n1. Keep it **1 page** max\n2. Start with a strong **objective** (2 lines)\n3. List **skills** relevant to the internship\n4. Include **projects** even if college projects\n5. Add **certifications** from Coursera, NPTEL etc.\n6. Use simple formatting — no colors or tables\n7. Save as **PDF** before uploading",
    "interview": "Interview preparation tips:\n• Research the **company and role** beforehand\n• Prepare answers for: Tell me about yourself, Why this internship?, Your strengths/weaknesses\n• Practice on **mock interview** tools\n• Dress professionally even for online interviews\n• Arrive/join **5 minutes early**\n• Prepare **2-3 questions** to ask the interviewer\n\nYou've got this! 💪",
    "skill": "Top skills by sector:\n• **Technology** – Python, JavaScript, SQL, Git\n• **Marketing** – Excel, Canva, Social Media, SEO\n• **Finance** – Excel, Tally, Financial Modeling\n• **Design** – Figma, Photoshop, Illustrator\n• **Data** – Python, Excel, Power BI, SQL\n\nFree learning: Coursera, NPTEL, YouTube, freeCodeCamp",
    "mentor": "To connect with your mentor:\n1. Go to **Chat → Mentors** page\n2. Click on any mentor's card\n3. Send your message!\n\nMentors are here to guide you. Don't hesitate to ask your doubts about internships, career, or skill building.",
    "career": "Career path planning:\n1. **Identify your interest** – What subject excites you?\n2. **Explore sectors** – Technology, Finance, Healthcare, Design etc.\n3. **Build foundational skills** – Take free courses\n4. **Do internships** – Practical experience matters most\n5. **Build a portfolio** – Show your work to employers\n6. **Network** – Connect with mentors and professionals\n\nStart with internships here on InternConnect!",
    "default": "Hi! I'm **CareerBot** 🤖 — your AI career assistant.\n\nI can help you with:\n• How to **apply** for internships\n• **Resume** writing tips\n• **Interview** preparation\n• **Career guidance** and skill building\n• **Application status** explained\n• **Mentor chat** and platform help\n\nJust ask me anything! 😊",
}

def fallback_response(user_msg: str) -> str:
    msg_lower = user_msg.lower()
    if any(w in msg_lower for w in ['apply', 'application', 'how to apply', 'submit']):
        return FALLBACK_RESPONSES['apply']
    if any(w in msg_lower for w in ['status', 'pending', 'approved', 'rejected', 'review']):
        return FALLBACK_RESPONSES['status']
    if any(w in msg_lower for w in ['resume', 'cv', 'curriculum']):
        return FALLBACK_RESPONSES['resume']
    if any(w in msg_lower for w in ['interview', 'prepare', 'question']):
        return FALLBACK_RESPONSES['interview']
    if any(w in msg_lower for w in ['skill', 'learn', 'course', 'technology']):
        return FALLBACK_RESPONSES['skill']
    if any(w in msg_lower for w in ['mentor', 'chat', 'message', 'doubt']):
        return FALLBACK_RESPONSES['mentor']
    if any(w in msg_lower for w in ['career', 'future', 'job', 'path', 'guide']):
        return FALLBACK_RESPONSES['career']
    return FALLBACK_RESPONSES['default']


# ─── UNIFIED ENGINE ───────────────────────────────────────────────────────────

_backends = [OllamaBackend(), GroqBackend(), TogetherAIBackend()]

def get_active_backend():
    """Return first available backend."""
    for b in _backends:
        if b.is_available():
            return b
    return None

def chat_with_llm(messages: list) -> dict:
    """Try backends in order, fall back to rule-based if all fail."""
    backend = get_active_backend()
    if backend:
        result = backend.chat(messages)
        if result.get("ok"):
            return result
    # All backends failed → use rule-based fallback
    last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    return {
        "content": fallback_response(last_user_msg),
        "model": "rule-based",
        "backend": "fallback",
        "tokens": 0, "ms": 0, "ok": True,
    }

def stream_with_llm(messages: list):
    """Generator for streaming. Falls back gracefully."""
    backend = get_active_backend()
    if backend and hasattr(backend, 'stream_chat'):
        yield from backend.stream_chat(messages)
    else:
        last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        yield fallback_response(last_user_msg)

def get_backend_status() -> dict:
    """Return status of all backends for admin/debug."""
    return {b.NAME: b.is_available() for b in _backends}
