import os
from dotenv import load_dotenv
from processor import process_pdf_to_faiss

load_dotenv()

def test():
    test_url = "https://kaustavst.blob.core.windows.net/uploads/LC-GAN.pdf"
    print(f"Testing ingestion for: {test_url}")
    process_pdf_to_faiss(test_url, tender_name="LC-GAN.pdf")

if __name__ == "__main__":
    test()
