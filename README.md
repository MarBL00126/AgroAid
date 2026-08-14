# AgroAid / AgroSafety

AgroAid is an AI Safety prototype for agricultural decision support in Latin America. It evaluates high-risk rural queries, retrieves local evidence, asks follow-up questions when critical context is missing, and abstains when a safe recommendation cannot be justified.

The system is designed as a safety layer for agricultural AI assistants, not as a replacement for agronomists, veterinarians, emergency services, or regulatory authorities.

## Main Features

- FastAPI backend.
- Web frontend served from `frontend/index.html`.
- RAG pipeline over agricultural documents.
- Chroma vector database in `db_agro_docs`.
- Risk scoring and abstention policy.
- Evidence verification.
- PDF download for the final diagnostic report.
- Optional PostgreSQL persistence with in-memory fallback for demo use.

## Safety Domains

AgroAid evaluates risk across:

- Agrochemicals and regulated substances.
- Extreme weather and field operations.
- Rural worker safety.
- Water and contamination.
- Zoonoses and animal health.
- Plant biosecurity.
- Food safety.
- Rural fires.
- Irrigation and soil risks.

## Requirements

Use Python 3.10+.

Install dependencies:

```bash
pip install fastapi "uvicorn[standard]" python-dotenv psycopg2-binary reportlab
pip install langchain langchain-community langchain-openai langchain-chroma langchain-text-splitters chromadb pypdf openai
```

`reportlab` is required to download the final diagnostic report as a PDF.

## Environment Variables

All credentials must be loaded from environment variables. Do not commit real secrets.

Create a local `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here

DB_HOST=localhost
DB_PORT=5432
DB_NAME=agrosafety
DB_USER=postgres
DB_PASSWORD=your_postgres_password_here

PDF_FOLDER=data
CHROMA_DIR=db_agro_docs
```

The `.env` file is local-only and must not be uploaded to GitHub or included in a hackathon submission.

For PowerShell, you can also set variables temporarily for the current terminal session:

```powershell
$env:OPENAI_API_KEY="your_openai_api_key_here"
$env:DB_PASSWORD="your_postgres_password_here"
```

Never put real API keys or database passwords in the README.

## Run The App

From the project folder:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/api/health
```

## PDF Diagnostic Report

After completing a consultation, the frontend shows a **Download PDF** button.

The backend endpoint is:

```text
GET /api/consulta/{consulta_id}/pdf
```

Example:

```text
http://localhost:8000/api/consulta/1/pdf
```

The downloaded report includes:

- Consultation ID and date.
- Risk level and confidence.
- Detected safety domains.
- Abstention status.
- Missing information.
- Detected risks.
- Final evaluation.
- Evidence verification and sources.

## PostgreSQL Notes

PostgreSQL is optional for local demos. If the database is unavailable, the app can run in in-memory fallback mode.

Use PostgreSQL when you want to persist consultations, responses, audits, final evaluations, and metrics.

## Security Notes

Do not commit:

- `.env` files.
- OpenAI API keys.
- PostgreSQL passwords.
- Notebook outputs containing secrets.
- Screenshots showing credentials.

Recommended `.gitignore` entries:

```gitignore
.env
*.env
__pycache__/
.ipynb_checkpoints/
*.pyc
```

If a real OpenAI key or database password was ever committed, shared, or included in a notebook, rotate it immediately.

## Disclaimer

AgroAid is a prototype for AI Safety research. It does not replace professional advice from agronomists, veterinarians, emergency services, environmental authorities, or sanitary/fitosanitary regulators.
