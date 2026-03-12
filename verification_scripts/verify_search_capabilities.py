import os
import argparse
from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

load_dotenv()

def get_embeddings_client():
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )
    
    return AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_ad_token_provider=token_provider,
    )

def main():
    parser = argparse.ArgumentParser(description="Test Azure AI Search capabilities.")
    parser.add_argument("--query", type=str, help="Semantic search question.", default="What is GAN?")
    parser.add_argument("--source", type=str, help="Metadata filter (source URL).", default=None)
    parser.add_argument("--tender_name", type=str, help="Metadata filter (tender name).", default=None)
    args = parser.parse_args()

    # Configuration
    AZURE_AI_SEARCH_ENDPOINT = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    AZURE_AI_SEARCH_INDEX_NAME = os.getenv("AZURE_AI_SEARCH_INDEX_NAME", "vector-index")
    AZURE_AI_SEARCH_KEY = os.getenv("AZURE_AI_SEARCH_KEY")

    if not AZURE_AI_SEARCH_ENDPOINT:
        print("Error: AZURE_AI_SEARCH_ENDPOINT is not set.")
        return

    print(f"--- Search Test Configuration ---")
    print(f"Endpoint: {AZURE_AI_SEARCH_ENDPOINT}")
    print(f"Index: {AZURE_AI_SEARCH_INDEX_NAME}")
    print(f"----------------------------------\n")

    embeddings = get_embeddings_client()
    
    vector_store = AzureSearch(
        azure_search_endpoint=AZURE_AI_SEARCH_ENDPOINT,
        azure_search_key=AZURE_AI_SEARCH_KEY if AZURE_AI_SEARCH_KEY else None,
        azure_credential=DefaultAzureCredential() if not AZURE_AI_SEARCH_KEY else None,
        index_name=AZURE_AI_SEARCH_INDEX_NAME,
        embedding_function=embeddings.embed_query,
    )

    # 1. Keyword/Metadata Search
    if args.source or args.tender_name:
        filters = []
        if args.source:
            filters.append(f"source eq '{args.source}'")
        if args.tender_name:
            filters.append(f"tender_name eq '{args.tender_name}'")
        
        filter_query = " and ".join(filters)
        print(f"Performing Keyword Search (filtering by metadata: {filter_query})...")
        
        results = vector_store.similarity_search(
            query="*", # Wildcard for pure metadata filtering
            k=5,
            filters=filter_query
        )
        print(f"Found {len(results)} results matching the filter.")
        for i, res in enumerate(results):
            print(f"\nResult {i+1}:")
            print(f"Metadata: {res.metadata}")
            print(f"Content: {res.page_content[:200]}...")
    else:
        print("Skipping Keyword Search (no --source or --tender_name provided).")

    # 2. Semantic/Vector Search
    print(f"\nPerforming Semantic Search for: '{args.query}'...")
    results = vector_store.similarity_search(
        query=args.query,
        k=3
    )
    
    print(f"Found {len(results)} relevant results.")
    for i, res in enumerate(results):
        print(f"\nSemantic Result {i+1}:")
        print(f"Metadata: {res.metadata}")
        print(f"Content: {res.page_content[:200]}...")

if __name__ == "__main__":
    main()
