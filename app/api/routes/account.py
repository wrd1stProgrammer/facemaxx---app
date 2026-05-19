from fastapi import APIRouter, Depends

from app.api.deps import RequestIdentity, get_request_identity
from app.repositories.account_repository import AccountRepository

router = APIRouter(prefix="/account", tags=["account"])


@router.delete("")
async def delete_account(identity: RequestIdentity = Depends(get_request_identity)) -> dict[str, str]:
    AccountRepository().delete_account_data(identity)
    return {"status": "deleted"}
