"""
prediction_engine.py
Resume prediction and job matching engine for Django.
"""
import os
import re
import warnings
import logging
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# Set up logger
logger = logging.getLogger(__name__)

# Path to saved models (adjust if needed)
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'saved_models')

# Global variables for loaded models and data
_model      = None
_tfidf      = None
_le         = None
_df_jobs    = None
_job_matrix = None
_models_loaded = False
_load_error    = None


def _load_models():
    """
    Load all ML artefacts once and keep them in memory.
    Build the pre‑vectorised job matrix immediately.
    Returns True if successful, False otherwise.
    """
    global _model, _tfidf, _le, _df_jobs, _job_matrix, _models_loaded, _load_error
    if _models_loaded:
        return True

    try:
        import joblib
        from scipy.sparse import csr_matrix
        from sklearn.metrics.pairwise import cosine_similarity  # not used here but ensures sklearn is available

        logger.info("Loading ML models from %s", MODEL_DIR)

        _model   = joblib.load(os.path.join(MODEL_DIR, 'best_model.pkl'))
        _tfidf   = joblib.load(os.path.join(MODEL_DIR, 'tfidf_vectorizer.pkl'))
        _le      = joblib.load(os.path.join(MODEL_DIR, 'label_encoder.pkl'))
        _df_jobs = pd.read_pickle(os.path.join(MODEL_DIR, 'df_jobs.pkl'))

        logger.info("Models loaded: %s", type(_model).__name__)
        logger.info("Number of categories: %d", len(_le.classes_))
        logger.info("Number of jobs in dataset: %d", len(_df_jobs))
        logger.info("DataFrame columns: %s", _df_jobs.columns.tolist())

        # Verify that the required column exists
        if 'clean_combined' not in _df_jobs.columns:
            raise KeyError("The DataFrame 'df_jobs.pkl' does not contain a 'clean_combined' column. "
                           "Please recreate it with that column (e.g., job_title + description).")

        # Show a sample of clean_combined
        sample_text = _df_jobs['clean_combined'].iloc[0]
        logger.info("Sample clean_combined (first 200 chars): %s", str(sample_text)[:200])

        # Build the job matrix once and keep it
        logger.info("Building job matrix (TF‑IDF transform of all jobs)...")
        _job_matrix = _tfidf.transform(
            _df_jobs['clean_combined'].fillna('').replace('', ' ').tolist()
        )
        logger.info("Job matrix built. Shape: %s", _job_matrix.shape)

        _models_loaded = True
        return True

    except Exception as e:
        _load_error = str(e)
        logger.error("Failed to load ML models: %s", _load_error, exc_info=True)
        return False


def models_available():
    """Check if ML models are loaded and ready."""
    return _load_models()


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF file (pdfplumber → fallback PyMuPDF)."""
    text = ''
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + ' '
        if text.strip():
            return text.strip()
    except Exception:
        pass

    try:
        import fitz
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text() + ' '
        doc.close()
        return text.strip()
    except Exception as e:
        raise RuntimeError(f'Could not read PDF: {e}')


def _get_nltk_tools():
    """Get stopwords and lemmatizer; fallback to basic stopwords if NLTK fails."""
    try:
        import nltk
        from nltk.corpus import stopwords
        from nltk.stem import WordNetLemmatizer
        nltk.download('stopwords', quiet=True)
        nltk.download('wordnet', quiet=True)
        nltk.download('omw-1.4', quiet=True)
        return set(stopwords.words('english')), WordNetLemmatizer()
    except Exception:
        # Basic stopwords list (English)
        basic_stops = {
            'the','a','an','and','or','but','in','on','at','to',
            'for','of','with','by','from','is','was','are','were',
            'be','been','being','have','has','had','do','does','did',
            'will','would','could','should','may','might','shall',
            'not','no','nor','so','yet','both','either','neither',
            'this','that','these','those','i','me','my','we','our',
            'you','your','he','his','she','her','it','its','they','their'
        }
        return basic_stops, None


def preprocess_text(text: str) -> str:
    """Clean and lemmatise raw text."""
    if not isinstance(text, str) or not text.strip():
        return ''
    stop_words, lemmatizer = _get_nltk_tools()
    text = text.lower()
    text = re.sub(r'http\S+|www\.\S+', ' ', text)
    text = re.sub(r'\S+@\S+', ' ', text)
    text = re.sub(r'[^a-z\s]', ' ', text)
    tokens = [t for t in text.split() if t not in stop_words and len(t) > 2]
    if lemmatizer:
        try:
            tokens = [lemmatizer.lemmatize(t) for t in tokens]
        except Exception:
            pass
    return ' '.join(tokens)


def run_prediction(pdf_path: str) -> dict:
    """
    Run full prediction pipeline on a resume PDF.
    Returns a dictionary matching the notebook's output structure.
    """
    # 1. Extract and clean
    raw_text   = extract_text_from_pdf(pdf_path)
    clean_text = preprocess_text(raw_text)

    if not clean_text.strip():
        raise ValueError(
            'No readable text found in this PDF. '
            'Please use a text‑based (non‑scanned) PDF.'
        )

    words_raw   = len(raw_text.split())
    words_clean = len(clean_text.split())
    preview     = clean_text[:200]

    # Base result
    result = {
        'words_raw':          words_raw,
        'words_clean':        words_clean,
        'clean_preview':      preview,
        'predicted_category': 'UNKNOWN',
        'confidence_score':   None,
        'top3_categories':    [],
        'top5_jobs':          [],
        'matched_internships': [],
        'raw_text_preview':   preview,
        'words_extracted':    words_raw,
        'ml_used':            False,
    }

    # If models not available, fallback to keyword‑based category
    if not _load_models():
        logger.warning("ML models not available – using keyword fallback.")
        cat = _keyword_fallback(clean_text)
        result['predicted_category'] = cat
        result['top3_categories'] = [
            {'category': cat, 'score': 100.0, 'bar_filled': 20, 'bar_empty': 0}
        ]
        return result

    try:
        from scipy.sparse import csr_matrix
        from sklearn.metrics.pairwise import cosine_similarity

        # 2. Vectorise resume
        resume_vec     = _tfidf.transform([clean_text])
        resume_vec_abs = csr_matrix(resume_vec.copy())
        resume_vec_abs.data = np.abs(resume_vec_abs.data)  # some models need non‑negative

        # 3. Predict category
        label_idx          = _model.predict(resume_vec_abs)[0]
        predicted_category = _le.inverse_transform([label_idx])[0]
        result['predicted_category'] = predicted_category

        # 4. Confidence and top 3 categories
        top3_categories = []
        confidence      = None

        if hasattr(_model, 'predict_proba'):
            proba      = _model.predict_proba(resume_vec_abs)[0]
            confidence = float(proba.max()) * 100
            top3_idx   = np.argsort(proba)[::-1][:3]
            for idx in top3_idx:
                pct        = round(float(proba[idx]) * 100, 2)
                filled     = int(pct / 5)          # out of 20 blocks
                empty      = 20 - filled
                top3_categories.append({
                    'category':   _le.inverse_transform([idx])[0],
                    'score':      pct,
                    'bar_filled': filled,
                    'bar_empty':  empty,
                })

        elif hasattr(_model, 'decision_function'):
            scores         = _model.decision_function(resume_vec)[0]
            scores_shifted = scores - scores.min()
            norm_scores    = scores_shifted / (scores_shifted.sum() + 1e-9)
            confidence     = float(norm_scores.max()) * 100
            top3_idx       = np.argsort(norm_scores)[::-1][:3]
            for idx in top3_idx:
                pct    = round(float(norm_scores[idx]) * 100, 2)
                filled = int(pct / 5)
                empty  = 20 - filled
                top3_categories.append({
                    'category':   _le.inverse_transform([idx])[0],
                    'score':      pct,
                    'bar_filled': filled,
                    'bar_empty':  empty,
                })

        result['confidence_score'] = round(confidence, 2) if confidence else None
        result['top3_categories']  = top3_categories

        # 5. Top 5 matching jobs (using pre‑built job matrix)
        if _job_matrix is None:
            # Should never happen if _load_models succeeded, but safety check
            raise RuntimeError("Job matrix not built – models loaded incorrectly.")

        sim_scores = cosine_similarity(resume_vec, _job_matrix).flatten()
        logger.info("Similarity scores computed. Top 5: %s", sim_scores[np.argsort(sim_scores)[::-1][:5]])

        top5_idx = np.argsort(sim_scores)[::-1][:5]

        top5_jobs = []
        for rank, idx in enumerate(top5_idx, 1):
            row = _df_jobs.iloc[idx]
            top5_jobs.append({
                'rank':             rank,
                'job_id':           str(row.get('job_id', 'N/A')),
                'job_title':        str(row.get('job_title', 'N/A')),
                'category':         str(row.get('category', 'N/A')),
                'location':         str(row.get('location', 'N/A')),
                'similarity_score': round(float(sim_scores[idx]), 4),
            })

        result['top5_jobs'] = top5_jobs
        result['ml_used']   = True

    except Exception as e:
        logger.error("Prediction pipeline failed: %s", e, exc_info=True)
        # Fallback to keyword category
        cat = _keyword_fallback(clean_text)
        result['predicted_category'] = cat
        result['top3_categories'] = [
            {'category': cat, 'score': 100.0, 'bar_filled': 20, 'bar_empty': 0}
        ]
        result['top5_jobs'] = []   # explicitly empty

    return result


def match_mentor_internships(predicted_category: str, clean_text: str = '') -> list:
    """
    Match the predicted category with active internships from the portal.
    Returns up to 5 internships with match scores.
    """
    from mentor_portal.models import Internship

    SECTOR_MAP = {
        'technology':  ['technology','software','data','it','computer','web','programming','developer','python','java'],
        'finance':     ['finance','banking','accounting','fintech','investment','audit','tax'],
        'marketing':   ['marketing','sales','digital','seo','advertising','brand','customer'],
        'engineering': ['engineering','mechanical','electrical','civil','manufacturing','production'],
        'healthcare':  ['healthcare','medical','pharma','health','clinical','nursing'],
        'education':   ['education','teaching','training','learning','academic','coaching'],
        'legal':       ['legal','law','compliance','regulatory','litigation'],
        'design':      ['design','graphic','ui','ux','creative','figma','illustrator'],
        'logistics':   ['logistics','supply chain','operations','warehouse'],
        'agriculture': ['agriculture','farming','rural','agri'],
    }

    CATEGORY_TO_SECTOR = {
        'SALES':                  'marketing',
        'INFORMATION-TECHNOLOGY': 'technology',
        'DATA-SCIENCE':           'technology',
        'HR':                     'technology',
        'FINANCE':                'finance',
        'MARKETING':              'marketing',
        'ENGINEERING':            'engineering',
        'HEALTHCARE':             'healthcare',
        'EDUCATION':              'education',
        'LEGAL':                  'legal',
        'DESIGN':                 'design',
        'ACCOUNTANT':             'finance',
        'BUSINESS-DEVELOPMENT':   'marketing',
        'DIGITAL-MEDIA':          'marketing',
        'FITNESS':                'healthcare',
        'APPAREL':                'design',
        'AUTOMOBILE':             'engineering',
        'AVIATION':               'engineering',
        'BANKING':                'finance',
        'CHEF':                   'other',
        'CONSTRUCTION':           'engineering',
        'CONSULTANT':             'technology',
        'ARTS':                   'design',
        'ADVOCATE':               'legal',
        'BPO':                    'technology',
        'PUBLIC-RELATIONS':       'marketing',
        'TEACHER':                'education',
        'AGRICULTURE':            'agriculture',
        'ELECTRICAL-ENGINEERING': 'engineering',
        'MECHANICAL-ENGINEER':    'engineering',
        'NETWORK-SECURITY-ENGINEER': 'technology',
        'OPERATIONS-MANAGER':     'technology',
        'PMO':                    'technology',
    }

    matched = []
    try:
        internships   = Internship.objects.filter(is_active=True).select_related('mentor')
        cat_upper     = predicted_category.upper()
        text_lower    = clean_text.lower()
        mapped_sector = CATEGORY_TO_SECTOR.get(cat_upper, '')

        for internship in internships:
            score   = 0
            reasons = []

            sector_kws = SECTOR_MAP.get(internship.sector, [internship.sector.lower()])
            if internship.sector == mapped_sector:
                score += 40
                reasons.append(f'Category → Sector: {internship.get_sector_display()}')
            else:
                for kw in sector_kws:
                    if kw in text_lower:
                        score += 20
                        reasons.append(f'Keyword match: {kw}')
                        break

            if internship.skills_required:
                skills = [s.strip().lower() for s in internship.skills_required.split(',')]
                matched_skills = [s for s in skills if len(s) > 2 and s in text_lower]
                if matched_skills:
                    score += min(len(matched_skills) * 10, 40)
                    reasons.append(f'Skills: {", ".join(matched_skills[:3])}')

            title_words = [w for w in internship.title.lower().split() if len(w) > 3]
            for word in title_words:
                if word in text_lower:
                    score += 10
                    reasons.append(f'Title match: {word}')
                    break

            if score > 0:
                matched.append({
                    'id':              internship.id,
                    'title':           internship.title,
                    'company_name':    internship.company_name,
                    'sector':          internship.get_sector_display(),
                    'location':        internship.location,
                    'mode':            internship.get_mode_display(),
                    'stipend_amount':  internship.stipend_amount,
                    'duration':        internship.get_duration_display(),
                    'skills_required': internship.skills_required,
                    'mentor_name':     internship.mentor.full_name,
                    'match_score':     score,
                    'match_reasons':   list(dict.fromkeys(reasons)),
                })

        matched.sort(key=lambda x: x['match_score'], reverse=True)
        return matched[:5]

    except Exception as e:
        logger.error('Internship match error: %s', e, exc_info=True)
        return []


def _keyword_fallback(text: str) -> str:
    """Simple keyword‑based category prediction when ML models are unavailable."""
    categories = {
        'INFORMATION-TECHNOLOGY': ['python','java','javascript','software','developer','web','database','sql','html','css','react','django'],
        'DATA-SCIENCE':           ['machine learning','data','analytics','tensorflow','pandas','numpy','sklearn','tableau','deep learning'],
        'FINANCE':                ['finance','accounting','financial','budget','investment','bank','tax','audit','revenue'],
        'SALES':                  ['sales','customer','retail','target','crm','negotiation','revenue','client','pipeline'],
        'MARKETING':              ['marketing','seo','social media','campaign','brand','digital','advertising','content'],
        'ENGINEERING':            ['engineering','mechanical','electrical','civil','cad','manufacturing','production','quality'],
        'HEALTHCARE':             ['medical','clinical','patient','hospital','healthcare','pharma','nursing','health'],
        'EDUCATION':              ['teaching','education','curriculum','student','academic','training','coaching'],
        'HR':                     ['recruitment','hiring','onboarding','payroll','hr','human resources','talent','employee'],
        'LEGAL':                  ['legal','law','contract','compliance','regulatory','litigation','attorney'],
        'DESIGN':                 ['design','creative','graphic','ui','ux','illustrator','photoshop','figma'],
    }
    text_lower = text.lower()
    scores = {cat: sum(1 for kw in kws if kw in text_lower) for cat, kws in categories.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else 'GENERAL'