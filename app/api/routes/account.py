from fastapi import APIRouter, Depends
import hashlib
import shutil

from app.api.deps import RequestIdentity, get_request_identity
from app.repositories.account_repository import AccountRepository
from app.repositories.purchase_repository import PurchaseRepository
from app.api.routes.style_studio import RESULT_ROOT

router = APIRouter(prefix="/account", tags=["account"])


@router.delete("")
async def delete_account(identity: RequestIdentity = Depends(get_request_identity)) -> dict[str, str]:
    AccountRepository().delete_account_data(identity)
    owner = PurchaseRepository.app_user_id_for_identity(identity)
    directory = RESULT_ROOT / hashlib.sha256(owner.encode()).hexdigest()
    if directory.exists():
        shutil.rmtree(directory)
    return {"status": "deleted"}
