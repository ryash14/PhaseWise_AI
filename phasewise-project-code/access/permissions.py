"""The guard every request except signing in and out passes through."""

from typing import Annotated

from fastapi import Header, HTTPException, Request

from config import config
from persistence.database import session_factory
from persistence.models import UserAccount
from persistence.repository import fetch_user_account


def authorize_request(
    request: Request,
    session_token: Annotated[str | None, Header(alias=config.SESSION_TOKEN_HEADER)] = None,
):
    """Who is asking, and whether their role reaches the area of this route."""
    if not session_token:
        raise HTTPException(status_code=401, detail=config.SIGN_IN_REQUIRED_MESSAGE)
    with session_factory() as session:
        account = fetch_user_account(session, UserAccount.session_token == session_token)
    if account is None:
        raise HTTPException(status_code=401, detail=config.SIGN_IN_REQUIRED_MESSAGE)
    route = request.scope.get("route")
    path_template = getattr(route, "path", request.url.path)
    area = config.AREA_BY_ROUTE.get((request.method, path_template))
    if area not in config.ROLE_AREA_ACCESS.get(account["role"], []):
        raise HTTPException(
            status_code=403,
            detail=config.AREA_REFUSED_MESSAGE.format(role=account["role"], area=area),
        )
    return account
