import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)
from azure.core.credentials import AzureKeyCredential

load_dotenv()

def recreate_index():
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME", "vector-index")
    key = os.getenv("AZURE_AI_SEARCH_KEY")

    if not endpoint or not index_name:
        print("Error: AZURE_AI_SEARCH_ENDPOINT or AZURE_AI_SEARCH_INDEX_NAME not set.")
        return

    print(f"Recreating index: {index_name} at {endpoint}")

    if key:
        client = SearchIndexClient(endpoint, AzureKeyCredential(key))
    else:
        print("AZURE_AI_SEARCH_KEY not found. Using DefaultAzureCredential (RBAC)...")
        client = SearchIndexClient(endpoint, DefaultAzureCredential())

    # Delete index if it exists
    try:
        client.delete_index(index_name)
        print(f"Deleted existing index: {index_name}")
    except Exception as e:
        print(f"Index not found or could not be deleted: {e}")

    # Define fields
    # Note: LangChain AzureSearch expects these specific names by default:
    # id, content, content_vector, metadata
    # We add 'source' and 'tender_name' as additional filterable fields.
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072, # Match text-embedding-3-large
            vector_search_profile_name="myHnswProfile",
        ),
        SearchableField(name="metadata", type=SearchFieldDataType.String),
        # Custom fields for filtering
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="tender_name", type=SearchFieldDataType.String, filterable=True),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="myHnswAlgorithmsConfig")],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnswAlgorithmsConfig",
            )
        ],
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)

    print(f"Creating index {index_name}...")
    client.create_index(index)
    print("Success!")

if __name__ == "__main__":
    recreate_index()
