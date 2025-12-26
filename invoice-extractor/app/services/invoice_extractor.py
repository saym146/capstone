import json
import logging
import sys
from pathlib import Path

# Add workspace root to path for helpers import
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from helpers.aoai_helper import AOAIHelper, AOAIError

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Custom exception for extraction errors."""
    pass


SYSTEM_PROMPT = """You are an expert invoice data extraction assistant. Extract mentioned fields from the provided invoice pdf text.
{ 
    "OrderNumber": "string or null", #known as ORDER NUMBER, Order No., Order #, PO, Purchase Order, PO Number
    "InvoiceNumber": "string or null", #known as INVOICE NUMBER, INVOICE#, INV NO, Invoice No., Invoice #
    "InvoiceDate": "string or null", #known as INVOICE DATE, Invoice Date, Invoice Dt., Invoice Dt
    "InvoiceBaseAmount": "number or 0", #known as Sub total, Subtotal, Sub Total, Total before tax
    "InvoiceWithTaxAmount": "number or 0", #known as TOTAL AMOUNT, Total Amount, Invoice Total, Total Due, Amount Due
    "InvoiceLineItems": [
      { 
        "LineItemNo": "number", 
        "Product": "string or null", 
        "Quantity": "number or 0", 
        "UnitPrice": "number or 0", 
        "Amount": "number or 0" 
      } 
    ]
  }
Follow below rules 
- If a field is not found, use null.
- For Date fields, do not convert, use the format as in the pdf.
- If the LineItems array is empty, return an empty array.
- Return ONLY the JSON object, no additional text.
"""
EXTRACTION_PROMPT = """Extract the following details from the invoice pdf text and return in JSON format:
"""


async def extract_invoice_details(pdf_text: str) -> dict:
    """
    Extract invoice details from PDF text using Azure OpenAI.
    
    Raises:
        ExtractionError: If extraction fails due to API or parsing errors.
    """
    if not pdf_text.strip():
        raise ExtractionError("Could not extract text from PDF")
    
    try:
        aoai_helper = AOAIHelper()
        result_text = await aoai_helper.get_completion(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=EXTRACTION_PROMPT + pdf_text
        )
    except AOAIError as e:
        raise ExtractionError(str(e))
    
    # Parse JSON from response
    try:
        # Clean up response if it contains markdown code blocks
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        
        return json.loads(result_text.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.debug(f"Raw response: {result_text}")
        return {"raw_response": result_text, "error": "Failed to parse JSON from AI response"}
