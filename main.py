from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from api import ai_devs
from api import agents
from api import rag
from api import chat
from services.db import create_db_and_tables

create_db_and_tables()

app = FastAPI(title='NexusRealm API', description='Optional API for extended NexusRealm features')

app.include_router(ai_devs.router)
app.include_router(agents.router)

@app.get('/')
def main():
    return 'Testing 3...2...1'
