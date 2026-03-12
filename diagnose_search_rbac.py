import os
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv

load_dotenv()

def diagnose():
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    
    print(f"--- Azure AI Search RBAC Diagnostics ---")
    print(f"Endpoint: {endpoint}")
    print(f"Index: {index_name}")
    
    credential = DefaultAzureCredential()
    
    # 1. Test Management Plane (List Indices)
    print("\n1. Testing Management Plane (SearchIndexClient.list_index_names)...")
    try:
        index_client = SearchIndexClient(endpoint, credential)
        indices = list(index_client.list_index_names())
        print(f"SUCCESS: Found indices: {indices}")
    except HttpResponseError as e:
        print(f"FAILURE: Management Plane access denied. Error: {e.message}")
        if "Forbidden" in e.message:
            print("TIP: Ensure RBAC is enabled on the Search Service AND your identity has 'Search Service Contributor' or 'Owner' role.")
    except Exception as e:
        print(f"ERROR: {str(e)}")

    # 2. Test Data Plane (Search Documents)
    print("\n2. Testing Data Plane (SearchClient.search)...")
    try:
        search_client = SearchClient(endpoint, index_name, credential)
        # Try a simple wildcard search
        results = search_client.search(search_text="*", top=1)
        print("SUCCESS: Data Plane access granted.")
        for result in results:
            print("Found at least one document.")
            break
    except HttpResponseError as e:
        print(f"FAILURE: Data Plane access denied. Error: {e.message}")
        if "Forbidden" in e.message:
            print("TIP: Ensure your identity has 'Search Index Data Contributor' or 'Search Index Data Reader' role.")
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    diagnose()
