import json
import logging
import os
import sys
from pathlib import Path

import azure.functions as func
import aiohttp

# Add workspace root to path for helpers import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from helpers.aoai_helper import AOAIHelper, AOAIError

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
    """
    Call the invoice-extractor API to extract data from PDF.
    """
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
    """
    Use AOAI to compare user invoice data with extracted data.
    """
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


async def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP triggered function to validate invoice.
    Expects multipart form data with:
    - file: PDF file
    - data: JSON string with invoice data
    """
    logging.info('Invoice validation function triggered.')
    
    try:
        # Get the PDF file from the request
        pdf_file = req.files.get('file')
        if not pdf_file:
            return func.HttpResponse(
                json.dumps({"error": "No PDF file provided. Use 'file' field in multipart form."}),
                status_code=400,
                mimetype="application/json"
            )
        
        if not pdf_file.filename.endswith('.pdf'):
            return func.HttpResponse(
                json.dumps({"error": "Only PDF files are supported"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Get the JSON data from the request
        data_str = req.form.get('data')
        if not data_str:
            return func.HttpResponse(
                json.dumps({"error": "No invoice data provided. Use 'data' field with JSON string."}),
                status_code=400,
                mimetype="application/json"
            )
        
        try:
            request_data = json.loads(data_str)
        except json.JSONDecodeError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON in 'data' field"}),
                status_code=400,
                mimetype="application/json"
            )
        
        user_invoice = request_data.get("Invoice")
        if not user_invoice:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'Invoice' object in request data"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Read PDF content
        file_content = pdf_file.read()
        
        # Call invoice extractor API
        logging.info(f"Calling invoice extractor for file: {pdf_file.filename}")
        extracted_data = await call_invoice_extractor(file_content, pdf_file.filename)
        
        if "error" in extracted_data:
            return func.HttpResponse(
                json.dumps({"error": f"Extraction failed: {extracted_data['error']}"}),
                status_code=500,
                mimetype="application/json"
            )
        
        # Validate invoice using AOAI
        logging.info("Validating invoice with AOAI")
        validation_result = await validate_invoice(user_invoice, extracted_data)
        
        response = {
            "Extraction": extracted_data,
            "Validation": validation_result
        }
        
        return func.HttpResponse(
            json.dumps(response, indent=2),
            status_code=200,
            mimetype="application/json"
        )
    
    except AOAIError as e:
        logging.error(f"AOAI error: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"AI validation failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"Validation failed: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
