import os
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.databases import Base
from models import User, Message, MessageRecipient
from services.user_service import UserService


IS_DM = os.getenv("TEST_DB_URL", "").startswith("dm://")


@pytest.mark.skipif(not IS_DM, reason="DM 环境未配置 TEST_DB_URL")
def test_user_list_perf_dm():
    db_url = os.getenv("TEST_DB_URL")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    import asyncio
    svc = UserService()

    with SessionLocal() as db:
        if db.query(User).count() < 500:
            for i in range(500):
                u = User(
                    name=f"user-{i}",
                    user_name=f"u{i}",
                    email=f"u{i}@ex.com",
                    company="IT",
                    password_hash="x",
                )
                db.add(u)
            db.commit()

        t0 = time.perf_counter()
        items, total = asyncio.get_event_loop().run_until_complete(
            svc.get_users(db, page=3, page_size=20)
        )
        t1 = time.perf_counter()

        assert total >= 500
        assert len(items) == 20
        assert (t1 - t0) < 1.0


@pytest.mark.skipif(not IS_DM, reason="DM 环境未配置 TEST_DB_URL")
def test_message_list_perf_dm():
    db_url = os.getenv("TEST_DB_URL")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        uid = db.query(User.id).first()[0]
        if db.query(Message).count() < 300:
            for i in range(300):
                m = Message(title=f"t{i}", content="c", sender_id=str(uid))
                db.add(m)
                db.flush()
                db.add(MessageRecipient(message_id=m.id, recipient_id=str(uid)))
            db.commit()

        from services.message_service import MessageService
        svc = MessageService()
        import asyncio
        async def run():
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            # 这里仅示意：如果提供了 async DM URL，可改成异步会话
            return await svc.list_messages(db, recipient_id=str(uid), page=2, page_size=20)  # type: ignore

        t0 = time.perf_counter()
        messages, total = asyncio.get_event_loop().run_until_complete(run())
        t1 = time.perf_counter()
        assert total >= 300
        assert len(messages) == 20
        assert (t1 - t0) < 1.5
