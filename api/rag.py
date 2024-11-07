from fastapi import APIRouter

router = APIRouter(prefix='/rag', tags=['memory', 'rag'])

@router.get('/retrieve')
def retrieve(query_string: str):
    return ''

@router.post('/remember')
def remember(information: str):
    return ''

