import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

def delete_index():
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    key = os.getenv("AZURE_AI_SEARCH_KEY")

    print(f"Deleting index: {index_name} at {endpoint}")

    try:
        if key:
            client = SearchIndexClient(endpoint, AzureKeyCredential(key))
        else:
            client = SearchIndexClient(endpoint, DefaultAzureCredential())

        client.delete_index(index_name)
        print(f"Success! Deleted index '{index_name}'.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    delete_index()
