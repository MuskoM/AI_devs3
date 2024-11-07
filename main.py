from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from api import ai_devs
from api import rag

app = FastAPI(title='NexusRealm API', description='Optional API for extended NexusRealm features')

app.include_router(ai_devs.router)
app.include_router(rag.router)

@app.get('/')
def main():
    return 'Testing 3...2...1'
