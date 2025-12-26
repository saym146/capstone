import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for module resolution
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load config (this also loads .env)
import app.config  # noqa: F401

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from app.services.invoice_extractor import extract_invoice_details, ExtractionError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Invoice Extractor API")

# Ensure upload directory exists
UPLOAD_DIR = Path("resource/uploaded-invoices")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def read_pdf_content(file_path: Path) -> str:
    """
    Read text content from a PDF file using pypdf.
    """
    try:
        reader = PdfReader(file_path)
        text_content = ""
        for page in reader.pages:
            text_content += page.extract_text() or ""
        return text_content
    except Exception as e:
        logger.error(f"Failed to read PDF: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read PDF file: {str(e)}")


@app.get("/")
async def root():
    return {"message": "Invoice Extractor API"}


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """
    Extract invoice details from an uploaded PDF file.
    Returns structured JSON with invoice information.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        file_content = await file.read()
        
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Save file with timestamp naming: inv_dd_mm_yyyy_HH_MM_SS.pdf
        timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
        saved_filename = f"inv_{timestamp}.pdf"
        saved_path = UPLOAD_DIR / saved_filename
        
        with open(saved_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"File saved: {saved_path}")
        
        # Read PDF content and pass text to extractor
        pdf_text = read_pdf_content(saved_path)
        
        if not pdf_text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF. The PDF may be image-based or empty.")
        
        result = await extract_invoice_details(pdf_text)
        return JSONResponse(
            content={"Extraction": result},
            headers={
                "Cache-Control": "no-store, no-cache, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    
    except HTTPException:
        raise
    except ExtractionError as e:
        logger.error(f"Extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except IOError as e:
        logger.error(f"File I/O error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
