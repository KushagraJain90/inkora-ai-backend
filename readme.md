
# Inkora AI — Backend

FastAPI backend for Inkora AI, an application for handwritten document conversion and academic answer evaluation.

## Features

- Handwritten OCR using Google Gemini
- Handwritten document conversion into DOCX and PDF
- Academic answer evaluation with marks and feedback
- PDF report generation
- Batch image processing
- REST API with OpenAPI documentation

## Technology Stack

- Python
- FastAPI
- Google Gemini API
- Pydantic
- Pillow
- python-docx
- ReportLab
- LibreOffice

## Project Structure

```text
inkora_backend/
├── app/
│   ├── core/
│   ├── models/
│   ├── prompts/
│   ├── routers/
│   ├── services/
│   └── utils/
├── main.py
├── requirements.txt
├── test_conversion_api.py
├── test_evaluation_api.py
└── test_ocr_api.py
```

## Local Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd inkora_backend
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Never commit your `.env` file.

### 5. Install LibreOffice

Install LibreOffice locally for DOCX-to-PDF conversion.

### 6. Run the backend

```bash
uvicorn main:app --reload
```

API documentation:

<http://127.0.0.1:8000/docs>

Health check:

<http://127.0.0.1:8000/health>

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Health check |
| POST | `/api/ocr` | Handwritten OCR |
| POST | `/api/convert` | Document conversion |
| POST | `/api/evaluate` | Academic answer evaluation |

## Running Tests

```bash
python -m unittest discover -v
```

## Deployment

The backend is intended for Docker-based deployment, with LibreOffice installed inside the container.

Production secrets should be configured through the hosting provider's environment variables.

```

Replace `YOUR_GITHUB_REPOSITORY_URL` after creating your GitHub repository.

### 3. Verify the cleaned repository

Run:

```powershell
git status --short
```

You should now see:

- `.gitignore`
- `README.md`
- `app/`
- `main.py`
- `requirements.txt`
- Test files

