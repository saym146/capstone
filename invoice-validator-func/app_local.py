"""
FastAPI wrapper for local development on Windows ARM64.
Run this instead of Azure Functions for local testing.
"""
import json
import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import aiohttp

# Add workspace root to path for helpers import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from helpers.aoai_helper import AOAIHelper, AOAIError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Invoice Validator API")

# Configuration
INVOICE_EXTRACTOR_URL = os.getenv("INVOICE_EXTRACTOR_URL", "http://localhost:8000/extract")

SYSTEM_PROMPT = """You are an invoice validation assistant. Compare the user-provided invoice data with the extracted invoice data and identify any discrepancies.

For each field, check if the values match. Consider the following:
- Numbers should be compared numerically (e.g., "42.35" equals 42.35, 100 equals 100.0)
- Dates should be compared semantically (e.g., "March 29, 2025" equals "29/03/2025")
- Empty or null values in user data should be ignored
- Line items should be compared by matching products
- Amounts should be compared numerically in float (e.g., 500.0 equals 500)

Return a JSON response with this structure:
{
    "is_valid": true or false if all the invoice fields match, 
    "field_analysis": { 
      "input-json-field-name": { #input-json-field-name will be InvoiceNumber, OrderNumber, InvoiceDate, InvoiceBaseAmount, InvoiceWithTaxAmount
        "status": "MATCH", #if expected and actual values are the same, "MISMATCH", #if expected and actual values are different
        "expected": "value from user input for that field", 
        "actual": "value from extracted data for that field" 
      }
    }, 
    "line_items_analysis": [ 
      { 
        "line_number": 1, #rowindex starting from 1
        "status": "MATCH", #if mentioned field_analysis (Product, Quantity, UnitPrice, Amount) line item for a particular line_number match, "MISMATCH", #if any field in that line item mismatches
        "field_analysis": { 
          "line-item-input-json-field-name": { #line-item-input-json-field-name will be Product, Quantity, UnitPrice, Amount. Also, for each line item check if the user input product exists in extracted data. if exists, compare other fields.
            "status": "MATCH", #if expected and actual values are the same, "MISMATCH", #if expected and actual values are different
            "expected": "value from user input for that field", 
            "actual": "value from extracted data for that field" 
          }, 
        } 
      } 
    ],
    "summary": "Brief summary of validation result under 20 words"
}

Return ONLY the JSON object, no additional text.
"""

VALIDATION_PROMPT = """Please validate the following invoice data:

USER PROVIDED DATA:
{user_data}

EXTRACTED DATA:
{extracted_data}

Compare these two datasets and identify any discrepancies.
"""


async def call_invoice_extractor(file_content: bytes, filename: str) -> dict:
    """Call the invoice-extractor API to extract data from PDF."""
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field('file', file_content, filename=filename, content_type='application/pdf')
        
        async with session.post(INVOICE_EXTRACTOR_URL, data=data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Invoice extractor returned {response.status}: {error_text}")
            
            result = await response.json()
            return result.get("Extraction", result)


async def validate_invoice(user_invoice: dict, extracted_invoice: dict) -> dict:
    """Use AOAI to compare user invoice data with extracted data."""
    aoai_helper = AOAIHelper()
    
    user_data_str = json.dumps(user_invoice, indent=2)
    extracted_data_str = json.dumps(extracted_invoice, indent=2)
    
    prompt = VALIDATION_PROMPT.format(
        user_data=user_data_str,
        extracted_data=extracted_data_str
    )
    
    result_text = await aoai_helper.get_completion(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt
    )
    
    # Parse JSON from response
    try:
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
    except json.JSONDecodeError:
        return {"raw_response": result_text, "error": "Failed to parse validation response"}


@app.get("/")
async def root():
    return {"message": "Invoice Validator API"}


@app.post("/api/validate_invoice")
async def validate_invoice_endpoint(
    file: UploadFile = File(...),
    data: str = Form(...)
):
    """
    Validate invoice by comparing user data with extracted PDF data.
    
    - file: PDF file
    - data: JSON string with invoice data
    """
    logger.info('Invoice validation triggered.')
    
    try:
        # Validate file
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Parse JSON data
        try:
            request_data = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in 'data' field")
        
        user_invoice = request_data.get("Invoice")
        if not user_invoice:
            raise HTTPException(status_code=400, detail="Missing 'Invoice' object in request data")
        
        # Read PDF content
        file_content = await file.read()
        
        # Call invoice extractor API
        logger.info(f"Calling invoice extractor for file: {file.filename}")
        extracted_data = await call_invoice_extractor(file_content, file.filename)
        
        if "error" in extracted_data:
            raise HTTPException(status_code=500, detail=f"Extraction failed: {extracted_data['error']}")
        
        # Validate invoice using AOAI
        logger.info("Validating invoice with AOAI")
        validation_result = await validate_invoice(user_invoice, extracted_data)
        
        response = {
            "Extraction": extracted_data,
            "Validation": validation_result
        }
        
        return JSONResponse(content=response)
    
    except HTTPException:
        raise
    except AOAIError as e:
        logger.error(f"AOAI error: {e}")
        raise HTTPException(status_code=500, detail=f"AI validation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7071)
