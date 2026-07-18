from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent #since we are in agents file 'parent' is used to go to the parent directory(multi agent planner folder)
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(
    model="gpt-4o-mini", 
    api_key=OPENAI_API_KEY, 
    temperature=0
)