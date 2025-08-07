from fastapi import APIRouter

router = APIRouter(tags=['openai'],prefix='/api/v1')

@router.post('/chat')
def chat_complete():
    """
    chat complete
    :return:
    """
    pass

@router.post('/embedding')
def embedding():
    """
    embedding
    :return:
    """
    pass