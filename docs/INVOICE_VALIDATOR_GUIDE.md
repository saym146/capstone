# Invoice Validator Function - Developer Documentation

## Overview

The Invoice Validator is an Azure Function (with FastAPI local wrapper) that validates invoice data by comparing user-provided invoice details against extracted data from a PDF. It uses Azure OpenAI to perform intelligent comparison and identify discrepancies.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT REQUEST                                    │
│              POST /api/validate_invoice (PDF + JSON data)                    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       INVOICE VALIDATOR API                                  │
│            (app_local.py / validate_invoice/__init__.py)                     │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 1: User Input Validation                                          │ │
│  │         - Validate PDF file (extension check)                          │ │
│  │         - Validate JSON data format                                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ STEP 2: Parse User Invoice Data                                        │ │
│  │         - Extract "Invoice" object from JSON                           │ │
│  │         - Prepare user data for comparison                             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Call Invoice Extractor API (REST API Call)                          │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  POST http://localhost:8000/extract                                    │ │
│  │  - Send PDF file                                                       │ │
│  │  - Receive extracted invoice data (JSON)                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                      INVOICE EXTRACTOR API                                   │
│                      (invoice-extractor)                                     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Compare Input vs Extracted Data (AOAI Call)                         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  AOAIHelper.get_completion()                                           │ │
│  │  - SYSTEM_PROMPT: Validation rules                                     │ │
│  │  - USER_PROMPT: User data + Extracted data                             │ │
│  │  - Returns: Validation result with field analysis                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                      AZURE OPENAI (AI Foundry)                               │
│                          gpt-4.1-mini                                        │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RESPONSE TO CLIENT                                 │
│              { "Extraction": {...}, "Validation": {...} }                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Validation Process Flow

| Step | Action | Description |
|------|--------|-------------|
| 1 | **User Input Validation** | Validate PDF file extension and JSON data format |
| 2 | **Parse User Invoice Data** | Extract Invoice object from request JSON |
| 3 | **Extractor REST API Call** | Send PDF to Invoice Extractor API, receive extracted data |
| 4 | **AOAI Comparison Call** | Compare user input vs extracted data using GPT-4.1-mini |

---

## Project Structure

```
invoice-validator-func/
├── validate_invoice/           # Azure Function
│   ├── __init__.py             # Function handler
│   └── function.json           # Function binding config
├── app_local.py                # FastAPI wrapper (local dev)
├── host.json                   # Azure Functions host config
├── local.settings.json         # Local environment settings
├── requirements.txt            # Dependencies
└── .env                        # Environment variables (local)

helpers/                        # Shared (workspace level)
├── __init__.py
└── aoai_helper.py              # Azure OpenAI helper
```

---

## Components

### 1. FastAPI Local Wrapper (`app_local.py`)

Used for local development on Windows ARM64 (Azure Functions Python worker not supported).

| Function | Description |
|----------|-------------|
| `root()` | GET `/` - Health check endpoint |
| `validate_invoice_endpoint()` | POST `/api/validate_invoice` - Main validation endpoint |
| `call_invoice_extractor()` | Calls the extractor API to get PDF data |
| `validate_invoice()` | Uses AOAI to compare user vs extracted data |

---

### 2. Azure Function (`validate_invoice/__init__.py`)

Production-ready Azure Function for deployment.

| Function | Description |
|----------|-------------|
| `main()` | HTTP triggered function entry point |
| `call_invoice_extractor()` | Calls the extractor API |
| `validate_invoice()` | AOAI comparison logic |

---

### 3. AOAI Helper (`helpers/aoai_helper.py`)

Shared helper for Azure OpenAI API calls.

| Class/Method | Description |
|--------------|-------------|
| `AOAIHelper` | Wrapper for Azure OpenAI async client |
| `get_completion()` | Makes chat completion request |
| `AOAIError` | Custom exception for AOAI errors |

---

## Validation Logic

The validator uses GPT-4.1-mini to intelligently compare invoice data:

**Comparison Rules:**
- Numbers compared numerically (`"42.35"` equals `42.35`)
- Dates compared semantically (`"March 29, 2025"` equals `"29/03/2025"`)
- Empty/null values in user data are ignored
- Line items matched by product name

---

## Input/Output Schema

### Request Input

**Multipart Form Data:**
- `file`: PDF invoice file
- `data`: JSON string with invoice data

**JSON Data Structure:**
```json
{
  "query": "Please validate this invoice",
  "Invoice": {
    "OrderNumber": "ORD-12345",
    "InvoiceNumber": "405993",
    "InvoiceDate": "March 29, 2025",
    "InvoiceBaseAmount": "42.35",
    "InvoiceWithTaxAmount": "50.82",
    "InvoiceLineItems": [
      {
        "LineItemNo": "1",
        "Product": "Level II Cloud VPS",
        "Quantity": "1",
        "UnitPrice": "42.35",
        "Amount": "42.35"
      }
    ]
  }
}
```

### Response Output

```json
{
  "Extraction": {
    "OrderNumber": "ORD-12345",
    "InvoiceNumber": "405993",
    "InvoiceDate": "March 29, 2025",
    "InvoiceBaseAmount": 42.35,
    "InvoiceWithTaxAmount": 50.82,
    "InvoiceLineItems": [...]
  },
  "Validation": {
    "is_valid": true,
    "field_analysis": {
      "InvoiceNumber": {
        "status": "MATCH",
        "expected": "405993",
        "actual": "405993"
      },
      "InvoiceDate": {
        "status": "MATCH",
        "expected": "March 29, 2025",
        "actual": "March 29, 2025"
      }
    },
    "line_items_analysis": [
      {
        "line_number": 1,
        "status": "MATCH",
        "field_analysis": {
          "Product": {
            "status": "MATCH",
            "expected": "Level II Cloud VPS",
            "actual": "Level II Cloud VPS"
          },
          "Amount": {
            "status": "MATCH",
            "expected": "42.35",
            "actual": 42.35
          }
        }
      }
    ],
    "summary": "All invoice fields match successfully."
  }
}
```

---

## Configuration

### Environment Variables (`.env` / `local.settings.json`)

| Variable | Description | Default |
|----------|-------------|---------|
| `INVOICE_EXTRACTOR_URL` | URL of the extractor API | `http://localhost:8000/extract` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | Required |
| `AZURE_OPENAI_API_KEY` | API key for authentication | Required |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-4.1-mini` |
| `AZURE_OPENAI_API_VERSION` | API version | `2025-01-01-preview` |

### `.env` File (Local Development)

```env
INVOICE_EXTRACTOR_URL=http://localhost:8000/extract
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

### `local.settings.json` (Azure Functions)

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "INVOICE_EXTRACTOR_URL": "http://localhost:8000/extract",
    "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "your-api-key",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1-mini",
    "AZURE_OPENAI_API_VERSION": "2025-01-01-preview"
  }
}
```

---

## API Reference

### POST `/api/validate_invoice`

**Request:**
- Content-Type: `multipart/form-data`
- Body:
  - `file`: PDF file
  - `data`: JSON string with invoice data

**Response (200):**
```json
{
  "Extraction": { ... },
  "Validation": { ... }
}
```

**Error Responses:**

| Code | Description |
|------|-------------|
| 400 | Invalid file type / Invalid JSON / Missing Invoice object |
| 500 | Extraction failed / AOAI error / Validation failed |

---

## Dependencies

```
azure-functions
aiohttp
python-dotenv
openai
```

**Additional for local development:**
```
fastapi
uvicorn[standard]
python-multipart
```

---

## Running Locally

### Prerequisites
1. Invoice Extractor API running on port 8000
2. `.env` file configured with Azure OpenAI credentials

### Start the Validator

```powershell
# Navigate to project
cd invoice-validator-func

# Activate virtual environment
..\venv\Scripts\Activate

# Install dependencies
pip install -r requirements.txt

# Run FastAPI wrapper (Windows ARM64)
python -m uvicorn app_local:app --host 127.0.0.1 --port 7071
```

**Swagger UI:** http://localhost:7071/docs

### Test with cURL

```powershell
curl -X POST "http://localhost:7071/api/validate_invoice" `
  -F "file=@invoice.pdf" `
  -F 'data={"query":"Validate","Invoice":{"InvoiceNumber":"405993","InvoiceDate":"March 29, 2025","InvoiceBaseAmount":"42.35","InvoiceWithTaxAmount":"50.82","InvoiceLineItems":[{"LineItemNo":"1","Product":"Level II Cloud VPS","Quantity":"1","UnitPrice":"42.35","Amount":"42.35"}]}}'
```

---

## Debugging (VS Code)

Select **"FastAPI Debug (invoice-validator)"** and press `F5`.

Configuration in `.vscode/launch.json`:
```json
{
  "name": "FastAPI Debug (invoice-validator)",
  "type": "debugpy",
  "request": "launch",
  "module": "uvicorn",
  "args": ["app_local:app", "--host", "127.0.0.1", "--port", "7071"],
  "cwd": "${workspaceFolder}/invoice-validator-func"
}
```

---

## Azure Deployment

> **Note:** Azure Functions Python worker does not support Windows ARM64 locally. Use the FastAPI wrapper for local development and deploy to Azure for production.

```bash
# Deploy to Azure
func azure functionapp publish <your-function-app-name>
```
