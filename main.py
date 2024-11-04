from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from api import ai_devs

app = FastAPI(title='NexusRealm API', description='Optional API for extended NexusRealm features')

app.include_router(ai_devs.router)

@app.get('/')
def main():
    return 'Testing 3...2...1'
