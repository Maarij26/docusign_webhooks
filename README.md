# docusign_webhooks
Automated HR Contract Signing with DocuSign & FastAPI
Features
- Send contracts to multiple recipients via DocuSign
- Real-time signing notifications via webhooks
Setup Guide
1. DocuSign Developer Account Setup
1.1 Create an account:  
   Go to [DocuSign Developer Center] (https://developers.docusign.com) and sign up.
1.2 Create an App:
   - Navigate to Admin > Integrations > Apps and Keys
   - Click "Add App/Integration Key"
   - Name it (e.g., "mywebhook_app")
Note: In developer account, for each app, you can make 20 Successful API Calls. 
   - Save these credentials:
     - Integration Key (Client ID)
     - RSA Key Pair (Download both private and public keys)
     - Save Private Key in a separate (.pem) file.
1.3 Enable Webhooks:
   - Go to Admin > Connect
   - Click "Add Configuration" → "Custom"
   - Configuration Name: `my_config_hooks`	
Go to Configuration > Actions > Edit
Listener Settings:
URL to Publish
-	Leave it blank, follow further steps then Paste URL from Step 4.2. 


2. Environment Setup
2.1 Clone this repo:
   git clone https://github.com/yourusername/hr-docusign-automation.git
2.2 Set up environment variables:
o	Create .env file:
o	Edit .env with following credentials.
INTEGRATION_KEY="your_client_id"
USER_ID="your_user_id"
ACCOUNT_ID="your_account_id"
PRIVATE_KEY_PATH="private_key.pem"
API_BASE_URL=https://demo.docusign.net/restapi (For Production: https://www.docusign.net/restapi)
AUTH_BASE_URI=https://account-d.docusign.com (For Production https://account.docusign.com)
3. Run the Application
3.1	Start FastAPI:
uvicorn main:app --reload
o	API docs will be at: http://localhost:8000/docs
4. Webhook Setup with ngrok
4.1	Install ngrok  
Download from download.ngrok.com 
1.	Open Command Prompt (CMD) in the folder where ngrok.exe is extracted
2.	Authenticate (one-time setup):
In command prompt: 
ngrok authtoken YOUR_AUTH_TOKEN
(Get YOUR_AUTH_TOKEN by signing up at ngrok.com)
4.2	Start ngrok tunnel (ngrok URL):
In Command Prompt window: ngrok http 8000
Expected Output:
Forwarding https://abc123.ngrok-free.app -> http://localhost:8000
Copy the HTTPS URL (e.g., https://abc123.ngrok-free.app)
5.	Configure DocuSign Webhooks:
Go back to DocuSign Connect settings > URL to Publish
Paste your ngrok URL + /docusign-webhook/:
https://abc123.ngrok-free.app/docusign-webhook/
a.	Select events to monitor:
i.	Envelope: Sent, Delivered, Completed
ii.	Recipient: Sent, Completed
6.	Test sending a contract:
curl -X POST "http://localhost:8000/send-contract/" \
7.	Test webhooks:
a.	Sign a test contract in DocuSign
b.	View incoming webhooks at: http://localhost:4040


