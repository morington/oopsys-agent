import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_agent.database import AgentIdentity, utc_now

_IDENTITY_ID = 1
_TOKEN_BYTES = 32


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenExistsError(RuntimeError):
    pass


class TokenMismatchError(RuntimeError):
    pass


@dataclass(slots=True)
class CreatedToken:
    token: str
    label: str | None


class TokenService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get_identity(self) -> AgentIdentity | None:
        result = await self._session.execute(select(AgentIdentity).where(AgentIdentity.id == _IDENTITY_ID))
        return result.scalar_one_or_none()

    async def ensure_identity(self) -> AgentIdentity:
        identity = await self._get_identity()
        if identity is None:
            identity = AgentIdentity(id=_IDENTITY_ID, agent_id=str(uuid.uuid4()))
            self._session.add(identity)
            await self._session.commit()
            await self._session.refresh(identity)
        return identity

    async def get_agent_id(self) -> str:
        identity = await self.ensure_identity()
        return identity.agent_id

    async def has_active_token(self) -> bool:
        identity = await self._get_identity()
        return bool(identity and identity.token_hash)

    async def create_token(self, *, label: str | None = None, force: bool = False) -> CreatedToken:
        identity = await self.ensure_identity()
        if identity.token_hash and not force:
            raise TokenExistsError("An active token already exists. Use force to recreate it.")

        token = secrets.token_urlsafe(_TOKEN_BYTES)
        identity.token_hash = hash_token(token)
        identity.token_label = label
        identity.token_created_at = utc_now()
        await self._session.commit()
        return CreatedToken(token=token, label=label)

    async def revoke_token(self) -> bool:
        identity = await self._get_identity()
        if identity is None or not identity.token_hash:
            return False
        identity.token_hash = None
        identity.token_label = None
        identity.token_created_at = None
        await self._session.commit()
        return True

    async def verify_token(self, token: str) -> bool:
        identity = await self._get_identity()
        if identity is None or not identity.token_hash:
            return False
        return hmac.compare_digest(identity.token_hash, hash_token(token))

    async def reconcile_env_token(self, token: str) -> None:
        identity = await self.ensure_identity()
        if not identity.token_hash:
            identity.token_hash = hash_token(token)
            identity.token_created_at = utc_now()
            await self._session.commit()
            return
        if not hmac.compare_digest(identity.token_hash, hash_token(token)):
            raise TokenMismatchError("OOPSYS_AGENT__TOKEN does not match the stored token hash.")
