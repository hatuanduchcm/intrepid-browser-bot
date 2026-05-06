"""
Common utility for extracting Shopee invoice data using Google Gemini API (google-generativeai).
Reads API key from environment variable (supports .env loading).

System Instruction (Master Prompt):
[Paste your full Master Prompt here]
"""
import os
import time
import json
import base64
import mimetypes
from typing import Dict, Any
from pathlib import Path
import google.generativeai as genai

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
# Model name can be overridden via env var, defaults to gemini-2.5-flash
GEMINI_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.5-flash")

# System instruction (Master Prompt)
MASTER_PROMPT = """
You are a professional Invoice OCR Specialist. Your task is to extract financial data from Shopee adjustment images across Southeast Asia (VN, SG, MY, ID, PH, TH).

### EXTRACTION RULES:
1. SCOPE: Extract only the lines starting from "Refund Amount" down to "Total Adjustment Amount". Ignore all headers, footers, or noise outside this range.
2. LANGUAGE & CURRENCY: Automatically detect the currency/country (VND, SGD, MYR, IDR, PHP, THB).
3. NUMBER PROCESSING (CRITICAL):
   - Do NOT use hardcoded rules for dots (.) or commas (,). Use CONTEXTUAL INFERENCE:
     - If there are 3 digits after a separator (e.g., .000 or ,000), treat it as a THOUSANDS separator.
     - If there are 2 digits after a separator at the end (e.g., .50, ,00), treat it as a DECIMAL point.
     - For VND: Always return as Integers (No decimals).
     - For SGD, MYR, PHP, THB, IDR: Keep 2 decimal places if present in the image.
   - Keep the negative sign (-) if present.
   - Remove all currency symbols (đ, Rp, $, RM, ฿, ₱).

### LOGIC VERIFICATION:
- Calculate the sum of all "extracted_items" (excluding the Total Adjustment Amount).
- Compare your calculated sum with the "Total Adjustment Amount" shown in the image.
- Set "is_match" to true if they are equal, otherwise false.

### OUTPUT FORMAT (JSON ONLY):
{
  "metadata": {
    "country_code": "VN/SG/MY/ID/PH/TH",
    "currency": "VND/SGD/..."
  },
  "extracted_items": [
    {"item_name": "Original Name in Image", "amount": number}
  ],
  "total_adjustment_amount_in_image": number,
  "calculated_total": number,
  "is_match": boolean
}
"""

def extract_shopee_invoice(image_path: str) -> Dict[str, Any]:
    """
    Extract Shopee invoice data from an image using Gemini API (gemini-1.5-flash).

    Args:
        image_path (str): Path to the invoice image file.

    Returns:
        dict: Extracted invoice data as a dictionary.
    """
    try:
        # Check file existence
        if not Path(image_path).is_file():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        if not GEMINI_API_KEY:
            raise ValueError("Google Gemini API key not found in environment variable 'GOOGLE_GEMINI_API_KEY'.")

        genai.configure(api_key=GEMINI_API_KEY)

        # First positional arg is model name (not keyword 'model')
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=MASTER_PROMPT
        )

        # Detect mime type from file extension (fallback to image/png)
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png"

        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()

        # Build inline image part using base64
        image_part = {
            "inline_data": {
                "mime_type": mime_type,
                "data": base64.b64encode(image_bytes).decode()
            }
        }

        # Send request to Gemini API (system_instruction already set in model)
        response = model.generate_content(
            [image_part],
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json"
            }
        )

        # Parse JSON response
        if hasattr(response, "text") and response.text:
            return json.loads(response.text)
        raise ValueError("No valid response from Gemini API.")

    except FileNotFoundError as e:
        print(f"[extract_shopee_invoice] File error: {e}")
        raise
    except ValueError as e:
        print(f"[extract_shopee_invoice] Config/API error: {e}")
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "rate limit" in err_str or "resource exhausted" in err_str or "429" in err_str:
            print("[extract_shopee_invoice] Rate limit exceeded. Waiting 65 seconds before retrying...")
            time.sleep(65)
        else:
            print(f"[extract_shopee_invoice] Unexpected error: {e}")
        raise
