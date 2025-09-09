# diag_env.py
import os
from dotenv import load_dotenv

def main():
    """Reads a single variable from the .env file to test loading."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(project_root, '.env')
    
    print(f"Attempting to load .env file from: {dotenv_path}")
    
    if not os.path.exists(dotenv_path):
        print("❌ CRITICAL: .env file does not exist at the expected path.")
        return

    load_dotenv(dotenv_path=dotenv_path, override=True, verbose=True)
    
    smtp_from = os.getenv("SMTP_FROM")
    
    print("\n--- Environment Variable Check ---")
    print(f"SMTP_FROM = {smtp_from}")
    
    if smtp_from:
        print("\n✅ Successfully read SMTP_FROM.")
    else:
        print("\n❌ Failed to read SMTP_FROM. Please check the .env file for typos or formatting errors.")

if __name__ == "__main__":
    main() 