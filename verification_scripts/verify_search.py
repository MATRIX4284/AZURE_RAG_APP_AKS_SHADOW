import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.core.exceptions import HttpResponseError

load_dotenv()

def verify_ai_search():
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    key = os.getenv("AZURE_AI_SEARCH_KEY")

    print(f"Endpoint: {endpoint}")
    print(f"Index: {index_name}")
    print(f"Key configured: {'Yes' if key else 'No (Using Managed Identity/DefaultAzureCredential?)'}")

    if not endpoint:
        print("Error: AZURE_AI_SEARCH_ENDPOINT not set.")
        return

    try:
        if key:
            print("Trying with API Key...")
            from azure.core.credentials import AzureKeyCredential
            client = SearchIndexClient(endpoint, AzureKeyCredential(key))
        else:
            print("Trying with DefaultAzureCredential...")
            credential = DefaultAzureCredential()
            client = SearchIndexClient(endpoint, credential)

        print("Attempting to list indices...")
        indices = client.list_indices()
        for index in indices:
            print(f" - Found index: {index.name}")
        print("\nSuccess! Can list indices.")

    except HttpResponseError as e:
        print(f"\nCaught HttpResponseError: {e}")
        if "Forbidden" in str(e):
            print("\nSUGGESTION: This is a 'Forbidden' error. Possible causes:")
            print("1. Your Service Principal/Identity does NOT have 'Search Service Contributor' or 'Search Index Data Contributor' role.")
            print("2. RBAC is enabled on the Search Service, but you're not using it or vice versa.")
            print("3. Networking/Firewall is blocking access.")
    except Exception as e:
        print(f"\nCaught Exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    from azure.core.credentials import AzureKeyCredential
    verify_ai_search()
