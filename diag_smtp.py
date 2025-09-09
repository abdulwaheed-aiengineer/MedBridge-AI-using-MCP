# diag_smtp.py
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

def main():
    """Tests SMTP credentials and configuration from .env"""
    # Explicitly load .env from the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path)

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER") # Corrected from SMTP_USERNAME
    password = os.getenv("SMTP_PASS") # Corrected from SMTP_PASSWORD
    from_addr = os.getenv("SMTP_FROM")
    
    # Use a dummy recipient or your own email for testing
    to_addr = os.getenv("SMTP_TEST_RECIPIENT", "test@example.com")

    print("🧪 Running SMTP Diagnostics...")
    print(f"Host: {host}, Port: {port}, User: {user}, From: {from_addr}")

    if not all([host, from_addr, to_addr]):
        print("❌ Missing required .env variables: SMTP_HOST, SMTP_FROM, SMTP_TEST_RECIPIENT")
        return

    msg = EmailMessage()
    msg["Subject"] = "SMTP Test from Hospital MCP"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content("This is a test email to verify SMTP configuration.")

    try:
        with smtplib.SMTP(host, port) as s:
            s.set_debuglevel(1) # Verbose output
            s.starttls()
            if user and password:
                s.login(user, password)
            s.send_message(msg)
        print("\n✅ SMTP test email sent successfully!")
    except Exception as e:
        print(f"\n❌ SMTP Error: {e}")
        print("Hint: Check your .env file for correct SMTP credentials, host, and port. Ensure your email provider allows SMTP access and check for firewall issues.")

if __name__ == "__main__":
    main() 