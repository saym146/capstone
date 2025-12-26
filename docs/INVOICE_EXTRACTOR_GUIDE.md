# Invoice Extractor API - Developer Documentation

## Overview

The Invoice Extractor API is a FastAPI-based service that extracts structured invoice data from PDF files using Azure OpenAI (GPT-4.1-mini). It parses PDF content and returns JSON-formatted invoice details.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT REQUEST                                    │
│                         POST /extract (PDF file)                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI APP                                     │
│                            (app/main.py)                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Validate PDF file                                                │    │
│  │  2. Save to: resource/uploaded-invoices/inv_dd_mm_yyyy_HH_MM_SS.pdf │    │
│  │  3. Extract text using pypdf                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INVOICE EXTRACTOR SERVICE                            │
│                     (app/services/invoice_extractor.py)                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Prepare SYSTEM_PROMPT + EXTRACTION_PROMPT                        │    │
│  │  2. Call AOAIHelper.get_completion()                                 │    │
│  │  3. Parse JSON response                                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             AOAI HELPER                                      │
│                        (helpers/aoai_helper.py)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  - AsyncAzureOpenAI client                                           │    │
│  │  - Error handling (Auth, RateLimit, Connection)                      │    │
│  │  - Returns completion response                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AZURE OPENAI (AI Foundry)                               │
│                           gpt-4.1-mini                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
invoice-extractor/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration loader
│   └── services/
│       ├── __init__.py
│       └── invoice_extractor.py # Extraction logic
├── resource/
│   └── uploaded-invoices/      # Stored PDFs
├── .env                        # Environment variables
├── .env.example                # Template
└── requirements.txt            # Dependencies

helpers/                        # Shared (workspace level)
├── __init__.py
└── aoai_helper.py              # Azure OpenAI helper
```

---

## Components

### 1. FastAPI App (`app/main.py`)

| Function | Description |
|----------|-------------|
| `root()` | GET `/` - Health check endpoint |
| `extract()` | POST `/extract` - Main extraction endpoint |
| `read_pdf_content()` | Extracts text from PDF using pypdf |

**Request Flow:**
1. Accepts multipart form with PDF file
2. Validates file extension (`.pdf` only)
3. Saves file with timestamp: `inv_dd_mm_yyyy_HH_MM_SS.pdf`
4. Extracts text content
5. Returns JSON response

---

### 2. Invoice Extractor Service (`app/services/invoice_extractor.py`)

| Function | Description |
|----------|-------------|
| `extract_invoice_details()` | Async function that calls AOAI and parses response |

**Extraction Schema:**
```json
{
  "OrderNumber": "string | null",
  "InvoiceNumber": "string | null",
  "InvoiceDate": "string | null",
  "InvoiceBaseAmount": "number | 0",
  "InvoiceWithTaxAmount": "number | 0",
  "InvoiceLineItems": [
    {
      "LineItemNo": "number",
      "Product": "string | null",
      "Quantity": "number | 0",
      "UnitPrice": "number | 0",
      "Amount": "number | 0"
    }
  ]
}
```

---

### 3. AOAI Helper (`helpers/aoai_helper.py`)

| Class/Method | Description |
|--------------|-------------|
| `AOAIHelper` | Wrapper for Azure OpenAI async client |
| `get_completion()` | Makes chat completion request |
| `AOAIError` | Custom exception for AOAI errors |

**Error Handling:**
- `AuthenticationError` → Invalid API key
- `RateLimitError` → Rate limit exceeded
- `APIConnectionError` → Endpoint unreachable
- `APIError` → General API errors

---

### 4. Config (`app/config.py`)

Loads environment variables using `python-dotenv`.

---

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | Required |
| `AZURE_OPENAI_API_KEY` | API key for authentication | Required |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-4.1-mini` |
| `AZURE_OPENAI_API_VERSION` | API version | `2025-01-01-preview` |

### Example `.env`

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

---

## API Reference

### POST `/extract`

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (PDF file)

**Response (200):**
```json
{
  "Extraction": {
    "OrderNumber": "ORD-12345",
    "InvoiceNumber": "INV-001",
    "InvoiceDate": "March 29, 2025",
    "InvoiceBaseAmount": 42.35,
    "InvoiceWithTaxAmount": 50.82,
    "InvoiceLineItems": [...]
  }
}
```

**Error Responses:**
| Code | Description |
|------|-------------|
| 400 | Invalid file type / Empty file / PDF read error |
| 500 | Extraction error / AOAI error |

---

## Dependencies

```
fastapi
uvicorn[standard]
python-multipart
openai
python-dotenv
pypdf
```

---

## Running Locally

```bash
# Navigate to project
cd invoice-extractor

# Activate virtual environment
..\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials

# Run server
uvicorn app.main:app --reload --port 8000
```

**Swagger UI:** http://localhost:8000/docs

---

## Debugging (VS Code)

Select **"FastAPI Debug (invoice-extractor)"** and press `F5`.

Configuration in `.vscode/launch.json`:
```json
{
  "name": "FastAPI Debug (invoice-extractor)",
  "type": "debugpy",
  "request": "launch",
  "module": "uvicorn",
  "args": ["app.main:app", "--host", "127.0.0.1", "--port", "8000"],
  "cwd": "${workspaceFolder}/invoice-extractor"
}
```
