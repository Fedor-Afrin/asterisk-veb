#!/usr/bin/env python3
"""Сброс пароля веб-интерфейса. Настройки АТС (номера, группы, транки, IVR) не затрагиваются.

Запуск (из папки установки):
  docker compose exec backend python reset_password.py          # задать новый пароль
  docker compose exec backend python reset_password.py --web    # вернуть "первый запуск":
                                                                 # интерфейс сам предложит пароль
"""
import asyncio
import getpass
import sys

from sqlalchemy import delete

import auth
import models
from database import Base, async_session_maker, engine


async def main(web_mode: bool) -> int:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as db:
        if web_mode:
            await db.execute(delete(models.AdminAuth))
            await db.commit()
            print("Готово. При следующем открытии веб-интерфейса он предложит создать пароль.")
            print("Откройте страницу сами, пока этого не сделал кто-то другой в вашей сети.")
            return 0

        pw1 = getpass.getpass("Новый пароль администратора: ")
        pw2 = getpass.getpass("Повторите пароль: ")
        if pw1 != pw2:
            print("Пароли не совпадают.", file=sys.stderr)
            return 1
        error = auth.validate_password(pw1)
        if error:
            print(error, file=sys.stderr)
            return 1
        await auth.set_password(db, pw1)
        print("Пароль изменён. Все открытые сессии завершены.")
        return 0


if __name__ == "__main__":
    code = asyncio.run(main("--web" in sys.argv[1:]))
    sys.exit(code)
