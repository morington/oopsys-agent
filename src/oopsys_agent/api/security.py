from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_agent.services import TokenService

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing agent token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def require_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED

    container = request.state.dishka_container
    session = await container.get(AsyncSession)
    service = TokenService(session)
    if not await service.verify_token(credentials.credentials):
        raise _UNAUTHORIZED
