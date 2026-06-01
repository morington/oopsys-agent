import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from oopsys_agent.services import TokenExistsError, TokenMismatchError, TokenService


async def test_get_agent_id_is_stable(session: AsyncSession) -> None:
    service = TokenService(session)
    first = await service.get_agent_id()
    second = await service.get_agent_id()
    assert first == second
    assert len(first) == 36


async def test_create_then_verify(session: AsyncSession) -> None:
    service = TokenService(session)
    created = await service.create_token(label="srv")
    assert await service.verify_token(created.token) is True


async def test_verify_rejects_wrong_token(session: AsyncSession) -> None:
    service = TokenService(session)
    await service.create_token()
    assert await service.verify_token("wrong") is False


async def test_create_refuses_when_active_exists(session: AsyncSession) -> None:
    service = TokenService(session)
    await service.create_token()
    with pytest.raises(TokenExistsError):
        await service.create_token()


async def test_force_recreate_invalidates_old(session: AsyncSession) -> None:
    service = TokenService(session)
    old = await service.create_token()
    new = await service.create_token(force=True)
    assert new.token != old.token
    assert await service.verify_token(old.token) is False
    assert await service.verify_token(new.token) is True


async def test_revoke_clears_token(session: AsyncSession) -> None:
    service = TokenService(session)
    created = await service.create_token()
    assert await service.revoke_token() is True
    assert await service.verify_token(created.token) is False


async def test_reconcile_env_token_saves_when_absent(session: AsyncSession) -> None:
    service = TokenService(session)
    await service.reconcile_env_token("env-token")
    assert await service.verify_token("env-token") is True


async def test_reconcile_env_token_raises_on_mismatch(session: AsyncSession) -> None:
    service = TokenService(session)
    await service.create_token()
    with pytest.raises(TokenMismatchError):
        await service.reconcile_env_token("does-not-match")
