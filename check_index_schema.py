import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

def check_schema():
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    key = os.getenv("AZURE_AI_SEARCH_KEY")

    print(f"Checking index: {index_name} at {endpoint}")

    try:
        if key:
            client = SearchIndexClient(endpoint, AzureKeyCredential(key))
        else:
            client = SearchIndexClient(endpoint, DefaultAzureCredential())

        index = client.get_index(index_name)
        print("\nFields in index:")
        for field in index.fields:
            print(f" - {field.name} (Type: {field.type})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
