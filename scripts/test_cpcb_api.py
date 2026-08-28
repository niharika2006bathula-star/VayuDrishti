import os
import sys
import requests
from dotenv import load_dotenv

def main():
    # Load environment variables from the .env file
    load_dotenv()

    # Get the CPCB_API_KEY
    cpcb_api_key = os.getenv("CPCB_API_KEY")

    # Verify if it exists
    if not cpcb_api_key:
        print("Error: CPCB_API_KEY is missing from the .env file.")
        sys.exit(1)
    
    # CPCB Real-Time Air Quality Index resource ID on data.gov.in
    resource_id = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
    url = f"https://api.data.gov.in/resource/{resource_id}"
    
    params = {
        "api-key": cpcb_api_key,
        "format": "json",
        "limit": 3
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"HTTP Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("API request succeeded.")
            
            # Print top-level JSON keys
            print(f"Top-level JSON keys: {list(data.keys())}")
            
            # Print number of records returned
            records = data.get("records", [])
            print(f"Number of records returned: {len(records)}")
            
            if records:
                # Print field names from the first record
                print(f"Field names (first record): {list(records[0].keys())}")
                
                # Print up to 3 sample records
                print("\nSample records:")
                for i, record in enumerate(records[:3]):
                    print(f"Record {i + 1}: {record}")
            else:
                print("No records found in the response.")
        else:
            print("\nError: The API request failed.")
            print("This could be due to an invalid API key, an expired resource ID, or the server being down.")
            # Safely print response text without exposing the full URL (which contains the API key)
            print(f"API Response Message: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print("\nError: A network error occurred while trying to reach the API.")
        # Ensure we don't accidentally print the URL containing the API key in the exception string
        error_msg = str(e).replace(cpcb_api_key, "***HIDDEN_API_KEY***")
        print(f"Details: {error_msg}")

if __name__ == "__main__":
    main()
