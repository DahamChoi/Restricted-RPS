import openai
from custom_logger import logger
from dotenv import load_dotenv
import os

# --- Configuration ---
load_dotenv() # Load environment variables from .env file if it exists
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Placeholder for API Key setup ---
try:
    # Use the new client interface
    client = openai.OpenAI()
    # Example: Check connection by listing models (optional)
    # client.models.list()
    logger.info("OpenAI client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    exit()