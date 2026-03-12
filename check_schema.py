import os
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv

load_dotenv()

def check_schema():
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    
    print(f"Checking schema for index: {index_name}")
    credential = DefaultAzureCredential()
    
    try:
        client = SearchIndexClient(endpoint, credential)
        index = client.get_index(index_name)
        print(f"Index '{index_name}' found.")
        print("Fields:")
        for field in index.fields:
            print(f"- {field.name} (type: {field.type}, filterable: {field.filterable})")
        
        # Explicit check for 'source'
        has_source = any(f.name == "source" for f in index.fields)
        print(f"\nHas 'source' field: {has_source}")
        
    except HttpResponseError as e:
        print(f"Error retrieving index: {e.message}")
        if "Forbidden" in e.message:
            print("Note: Management Plane access (Search Service Contributor) is required to check schema.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    check_schema()
