import os
import io
import logging
import tempfile
from urllib.parse import unquote, urlparse
from pathlib import Path
from dotenv import load_dotenv

# Docling imports
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode

# LangChain imports
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import AzureSearch

# Azure Storage imports
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
)

import asyncio

load_dotenv()

# Configuration
AZURE_AI_SEARCH_ENDPOINT = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
AZURE_AI_SEARCH_INDEX_NAME = os.getenv("AZURE_AI_SEARCH_INDEX_NAME", "vector-index")

# Configure logging to a file
logging.basicConfig(
    filename='processing_failures.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_embeddings_client():
    """
    Initializes the Azure OpenAI Embeddings client with the correct token scope for AI Foundry.
    """
    from azure.identity import get_bearer_token_provider
    
    # For AI Foundry Projects, we need the Machine Learning scope
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://ai.azure.com/.default"
    )
    
    from langchain_openai import AzureOpenAIEmbeddings
    
    return AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_ad_token_provider=token_provider,
    )

def log_failure(blob_url, error_message):
    """Logs the failed blob URL and error to the log file."""
    logging.error(f"Failed to process: {blob_url} | Error: {error_message}")
    print(f"FAILURE LOGGED: {blob_url}")


def download_blob_to_bytes(blob_url: str):
    """
    Downloads the file from Blob Storage and returns the bytes.
    """
    try:
        print(f"Starting download for: {blob_url}")
        
        # 1. Download the file from Blob Storage
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is missing")
            
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Robust URL parsing to handle folders and special characters
        parsed_url = urlparse(blob_url)
        path_parts = parsed_url.path.lstrip('/').split('/')
        
        if len(path_parts) < 2:
            raise ValueError(f"Could not parse container and blob from URL: {blob_url}")
            
        container_name = unquote(path_parts[0])
        blob_name = unquote('/'.join(path_parts[1:]))
        
        print(f"Downloading from Container: '{container_name}', Blob: '{blob_name}'")
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        blob_data = blob_client.download_blob().readall()
        
        # Check if we downloaded an Azure Error XML instead of a PDF
        if b"<?xml" in blob_data and b"<Error>" in blob_data:
            error_text = blob_data.decode('utf-8', errors='ignore')
            raise ValueError(f"Azure Storage Error (check permissions/URL): {error_text}")

        # Diagnostic checks
        file_size = len(blob_data)
        print(f"Downloaded data size: {file_size} bytes")
        
        if file_size == 0:
            raise ValueError("Downloaded data is empty")

        header = blob_data[:4]
        print(f"File header bytes: {header}")
        if header != b"%PDF":
            print("WARNING: Data does not start with %PDF. It might not be a valid PDF.")

        return blob_data
            
    except Exception as e:
        print(f"Error downloading blob: {e}")
        return None

def pdf_markdown_parser(pdf_bytes: bytes, filename: str = "document.pdf"):
    """
    Parses a PDF byte stream and returns markdown content using Docling.
    """
    try:
        from docling.datamodel.base_models import DocumentStream
        from docling.document_converter import DocumentConverter
        # Convert bytes to DocumentStream using keyword arguments
        doc_stream = DocumentStream(name=filename, stream=io.BytesIO(pdf_bytes))
        
        # Convert to Markdown
        converter = DocumentConverter()
        result = converter.convert(doc_stream)
        markdown_content = result.document.export_to_markdown()
        
        return markdown_content
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None

async def process_pdf_to_faiss(blob_url: str, tender_name: str = "test"):
    """
    End-to-end pipeline: Download -> Parse -> Chunk -> Index.
    """
    try:
        # Define the schema explicitly so LangChain knows how to map metadata
        # Consolidate this definition to ensure consistency across the function
        from azure.search.documents.indexes.models import (
            SearchField,
            SearchFieldDataType,
            SimpleField,
            SearchableField,
        )
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=3072,
                vector_search_profile_name="myHnswProfile",
            ),
            SearchableField(name="metadata", type=SearchFieldDataType.String),
            # Custom fields for filtering must be explicitly defined here
            SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="tender_name", type=SearchFieldDataType.String, filterable=True),
        ]

        print(f"Checking if document is already indexed: {blob_url}")
        # 0. Check for existence in the index
        embeddings = get_embeddings_client()
        search_key = os.getenv("AZURE_AI_SEARCH_KEY")
        
        # We need a temporary vector store instance to check for existence
        from langchain_community.vectorstores import AzureSearch
        temp_vector_store = AzureSearch(
            azure_search_endpoint=AZURE_AI_SEARCH_ENDPOINT,
            azure_search_key=search_key if search_key else None,
            azure_credential=DefaultAzureCredential() if not search_key else None,
            index_name=AZURE_AI_SEARCH_INDEX_NAME,
            embedding_function=embeddings.embed_query,
            fields=fields, # Pass fields here so it knows 'source' is filterable
        )
        
        # Use asimilarity_search with a filter to check if the source already exists
        # We use k=1 because we only care if ANY document exists for this source
        existing_docs = await temp_vector_store.asimilarity_search(
            query="*",
            k=1,
            filters=f"source eq '{blob_url}'"
        )
        
        if existing_docs:
            print(f"SKIP: Document already indexed. Source: {blob_url}")
            return

        print(f"Starting processing for: {blob_url}")
        
        # 1. Download the file from Blob Storage
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING is missing")
            
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Robust URL parsing to handle folders and special characters
        # URL format: https://<account>.blob.core.windows.net/<container>/<path/to/blob>
        from urllib.parse import urlparse
        parsed_url = urlparse(blob_url)
        path_parts = parsed_url.path.lstrip('/').split('/')
        
        if len(path_parts) < 2:
            raise ValueError(f"Could not parse container and blob from URL: {blob_url}")
            
        container_name = unquote(path_parts[0])
        blob_name = unquote('/'.join(path_parts[1:]))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / Path(blob_name).name
            
            print(f"Downloading from Container: '{container_name}', Blob: '{blob_name}'")
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            blob_data = blob_client.download_blob().readall()
            
            # Check if we downloaded an Azure Error XML instead of a PDF
            if b"<?xml" in blob_data and b"<Error>" in blob_data:
                error_text = blob_data.decode('utf-8', errors='ignore')
                raise ValueError(f"Azure Storage Error (check permissions/URL): {error_text}")

            with open(local_path, "wb") as f:
                f.write(blob_data)
                
            # Diagnostic checks
            file_size = os.path.getsize(local_path)
            print(f"Downloaded file size: {file_size} bytes")
        
            if file_size == 0:
                raise ValueError("Downloaded file is empty")

            with open(local_path, "rb") as f:
                header = f.read(4)
                print(f"File header bytes: {header}")
                if header != b"%PDF":
                    print("WARNING: File does not start with %PDF. It might not be a valid PDF.")

        # 2. Parse with Docling (using to_thread since it's CPU-bound)
        print("Parsing PDF with Docling (converting to Markdown)...")
        
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode

        # Configure advanced PDF pipeline options
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True
        pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE 
        
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        result = await asyncio.to_thread(converter.convert, str(local_path))
        markdown_content = result.document.export_to_markdown()

        print("Markdown Content")
        print(type(markdown_content))

        # 3. Chunk with LangChain (Markdown Header Splitting)
        print("Chunking document with MarkdownHeaderTextSplitter...")
        from langchain_text_splitters import MarkdownHeaderTextSplitter
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        chunks = markdown_splitter.split_text(markdown_content)
    
        # Add metadata (source URL and tender_name) to each chunk
        for chunk in chunks:
            chunk.metadata["source"] = blob_url
            chunk.metadata["tender_name"] = tender_name
    
        print(f"Created {len(chunks)} chunks.")

        # 4. Initialize Embeddings and Vector Store
        embeddings = get_embeddings_client()
        
        print(f"Updating Azure AI Search index: {AZURE_AI_SEARCH_INDEX_NAME}...")
    
        # AzureSearch handles index creation and connection internally
        # It supports DefaultAzureCredential if the key is None
        search_key = os.getenv("AZURE_AI_SEARCH_KEY")
        from langchain_community.vectorstores import AzureSearch
        vector_store: AzureSearch = AzureSearch(
            azure_search_endpoint=AZURE_AI_SEARCH_ENDPOINT,
            azure_search_key=search_key if search_key else None,
            azure_credential=DefaultAzureCredential() if not search_key else None,
            index_name=AZURE_AI_SEARCH_INDEX_NAME,
            embedding_function=embeddings.embed_query,
            fields=fields,
            # Explicitly map fields to match recreate_index.py
            additional_search_client_options={"retry_total": 3},
            index_management_client_options={"retry_total": 3},
        )

        # --- Optimized Parallel Ingestion ---
        batch_size = 10      # Smaller batches = lighter network calls
        concurrency = 5      # Process 5 batches at once
        
        # The 'Bouncer' that prevents Azure rate limiting (429 errors)
        semaphore = asyncio.Semaphore(concurrency)

        async def upload_batch(batch_index, batch_data):
            async with semaphore:
                # While one batch waits for Azure Search, 
                # another batch can start calculating embeddings!
                print(f"  [Batch {batch_index}] Uploading {len(batch_data)} chunks...")
                await vector_store.aadd_documents(documents=batch_data)
                print(f"  [Batch {batch_index}] Upload complete.")

        # 1. Slice the document into batches
        batches = [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]
        
        print(f"Updating Azure AI Search in {len(batches)} parallel batches...")
        
        # 2. Fire all batches simultaneously! 
        # (The semaphore handles the 5-at-a-time limit automatically)
        await asyncio.gather(*[upload_batch(i + 1, b) for i, b in enumerate(batches)])
        # ------------------------------------
        print(f"Success! Azure AI Search index '{AZURE_AI_SEARCH_INDEX_NAME}' updated.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"\nCRITICAL ERROR: {error_msg}")
        log_failure(blob_url, error_msg)

if __name__ == "__main__":
    # Test script for local debugging if needed
    # test_url = "https://youraccount.blob.core.windows.net/uploads/test.pdf"
    # process_pdf_to_faiss(test_url)
    pass
