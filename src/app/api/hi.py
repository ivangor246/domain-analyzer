from fastapi import APIRouter

hi_router = APIRouter(prefix='/hi', tags=['hi'])


@hi_router.get('')
def hi() -> str:
    return 'HI!!!'
