from fastapi import APIRouter
from services.vectorService import EmbeddingService, VectorService

router = APIRouter(prefix='/rag', tags=['memory', 'rag'])

@router.get('/retrieve')
def retrieve(query_string: str):
    return ''

@router.post('/remember')
async def remember(information: str):
    embedding_service = EmbeddingService('http://polaris5:19530', 'nomic-embed-text')
    vs = VectorService(embedding_service, 'test')
    await vs.insert_into_collection('test', 'search_document', ['Help me'])
    return ''

