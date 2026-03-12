import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from processor import process_pdf_to_faiss

@pytest.mark.asyncio
async def test_process_pdf_to_faiss_basic(mock_env_vars, mock_blob_service_client, mock_document_converter, mock_embeddings, mock_azure_search):
    
    # Setup mocks
    mock_blob_client = MagicMock()
    mock_blob_service_client.from_connection_string.return_value.get_blob_client.return_value = mock_blob_client
    mock_blob_client.download_blob.return_value.readall.return_value = b"%PDF-1.4\n%..."
    
    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = "# Test Header\nTest content"
    
    mock_result = MagicMock()
    mock_result.document = mock_doc
    mock_document_converter.return_value.convert = MagicMock(return_value=mock_result)
    
    mock_azure_search.return_value.asimilarity_search = AsyncMock(return_value=[])
    mock_azure_search.return_value.aadd_documents = AsyncMock()
    
    # Mock MarkdownHeaderTextSplitter
    with patch("processor.MarkdownHeaderTextSplitter") as mock_splitter_cls:
        mock_splitter = mock_splitter_cls.return_value
        mock_chunk = MagicMock()
        mock_chunk.page_content = "Test content"
        mock_chunk.metadata = {}
        mock_splitter.split_text.return_value = [mock_chunk]
        
        # Run
        await process_pdf_to_faiss("https://test.blob.core.windows.net/container/test.pdf")
    
    # Assert
    mock_blob_service_client.from_connection_string.assert_called_once()
    assert mock_document_converter.called
    assert mock_azure_search.return_value.aadd_documents.called
