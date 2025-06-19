import logging
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
import os, base64, time, jwt, requests
from urllib.parse import urlencode
import jwt
import time 
import hmac
import hashlib
from fastapi import Request, BackgroundTasks
import xml.etree.ElementTree as ET

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Log to a file
        logging.StreamHandler()          # Also log to console
    ]
)

# Load environment variables
load_dotenv()
logging.info("Environment variables loaded.")

# Read sensitive values from .env
INTEGRATION_KEY = os.getenv("INTEGRATION_KEY")
USER_ID = os.getenv("USER_ID")
AUTH_BASE_URI = os.getenv("AUTH_BASE_URI")
API_BASE_URL = os.getenv("API_BASE_URL")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
PRIVATE_KEY_PATH = "private_key.pem"

# FastAPI app instance
app = FastAPI()

# Pydantic models
class Signer(BaseModel):
    email: str
    name: str
    recipientId: str

class EnvelopeRequest(BaseModel):
    signers: list[Signer]

# Load private key from file
def load_private_key():
    try:
        with open(PRIVATE_KEY_PATH, "r") as key_file:
            private_key = key_file.read()
            logging.debug(f"Private key loaded successfully.{private_key}")
            return private_key
    except Exception as e:
        logging.exception("Failed to load private key.")
        raise RuntimeError(f"Failed to load private key: {e}")

def get_access_token():
    private_key = load_private_key()
    current_time = int(time.time())
    logging.debug(f"Current time is: {current_time}")
    payload = {
        "iss": "4f224261-81ac-4f76-aff7-6d0bf7818a7c",
        "sub": "40f1626d-c4b1-4d47-a8ed-05cb04637e2e",
        "aud": "account-d.docusign.com",
        "iat": current_time,
        "exp": current_time + 6000,
        "scope": "signature impersonation"
    }

    assertion = jwt.encode(payload, private_key, algorithm="RS256")
    # Log the assertion for debugging
    logging.debug(f"JWT Assertion: {assertion}")

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion
    }
    response = requests.post(f"{AUTH_BASE_URI}/oauth/token", headers=headers, data=data)

    if response.status_code != 200:
        logging.error(f"Failed to get token: {response.status_code} - {response.text}")
        raise Exception(f"Token request failed: {response.text}")

    return response.json().get("access_token")

# Endpoint to send contract
@app.post("/send-contract/")
def send_contract(data: EnvelopeRequest):
    logging.info("Received request to send contract.")
    try:
        access_token = get_access_token()
        logging.debug(f"The access token is: {access_token}")
        # Read and encode PDF
        logging.debug("Reading and encoding PDF file.")
        with open("IBS_Contract.pdf", "rb") as file:
            file_base64 = base64.b64encode(file.read()).decode()

        # Create signer payload
        logging.debug("Preparing signer payload.")
        signers_payload = []
        for signer in data.signers:
            logging.debug(f"Processing signer: {signer.email}")
            signers_payload.append({
                "email": signer.email,
                "name": signer.name,
                "recipientId": signer.recipientId,
                "routingOrder": "1",
                "tabs": {
                    "signHereTabs": [{
                        "anchorString": "**signature**",
                        "anchorYOffset": "10",
                        "anchorUnits": "pixels"
                    }]
                }
            })

        # Envelope payload
        payload = {
            "documents": [{
                "documentBase64": file_base64,
                "documentId": "1",
                "fileExtension": "pdf",
                "name": "Contract Document"
            }],
            "emailSubject": "Please sign the contract",
            "recipients": {
                "signers": signers_payload
            },
            "status": "sent"
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = f"{API_BASE_URL}/v2.1/accounts/{ACCOUNT_ID}/envelopes"
        logging.debug(f"Sending envelope to URL: {url}")
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 201:
            logging.info("Envelope sent successfully.")
            return {
                "message": "Envelope sent successfully",
                "envelopeId": response.json().get("envelopeId")
            }
        else:
            logging.error(f"Failed to send envelope: {response.status_code} - {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except Exception as e:
        logging.exception("Error occurred while sending envelope.")
        raise HTTPException(status_code=500, detail=f"Envelope sending failed: {str(e)}")
    
@app.post("/docusign-webhook/") 
async def docusign_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint to receive DocuSign Connect webhook notifications
    """
    try:
        # Get the raw XML body
        body_bytes = await request.body()
        xml_data = body_bytes.decode('utf-8')
        
        # Log the raw XML for debugging
        logging.info(f"Received DocuSign webhook:\n{xml_data}")
        
        # Parse the XML
        root = ET.fromstring(xml_data)
        
        # Extract envelope information
        envelope_id = root.find('.//EnvelopeStatus/EnvelopeID').text
        status = root.find('.//EnvelopeStatus/Status').text
        
        # Extract recipients
        recipients = []
        for recipient in root.findall('.//EnvelopeStatus/RecipientStatus'):
            email = recipient.find('Email').text
            name = recipient.find('UserName').text
            recipient_status = recipient.find('Status').text
            recipients.append({
                'email': email,
                'name': name,
                'status': recipient_status
            })
        
        # Process in background to avoid timeout
        background_tasks.add_task(process_docusign_event, envelope_id, status, recipients)
        
        return {"status": "success", "message": "Notification received"}
    
    except Exception as e:
        logging.error(f"Webhook processing error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def process_docusign_event(envelope_id: str, status: str, recipients: list):
    """
    Background task to process the webhook event
    """
    try:
        logging.info(f"Processing event for envelope {envelope_id}")
        logging.info(f"Envelope status: {status}")
        logging.info(f"Recipients: {recipients}")
        
        # Check if envelope was completed
        if status.lower() == 'completed':
            logging.info(f"Envelope {envelope_id} was fully completed!")
            
            # Check which recipients signed
            signed_recipients = [r for r in recipients if r['status'].lower() == 'completed']
            for recipient in signed_recipients:
                logging.info(f"Recipient {recipient['email']} signed the document")
                # Add your custom logic here (e.g., update database, send email, etc.)
                
    except Exception as e:
        logging.error(f"Error in background processing: {str(e)}", exc_info=True)