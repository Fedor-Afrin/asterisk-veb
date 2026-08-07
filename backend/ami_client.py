import os
import asyncio
import collections
import collections.abc

# Патч для совместимости старой библиотеки panoramisk с Python 3.10+
collections.MutableMapping = collections.abc.MutableMapping

from panoramisk import Manager

# 172.17.0.1 - это стандартный IP-адрес хоста изнутри Docker-контейнера
# Если не сработает, поменяй на локальный IP твоего сервера (например, 10.0.0.9)
AMI_HOST = os.getenv("AMI_HOST", "10.0.0.10") 
AMI_PORT = int(os.getenv("AMI_PORT", 5038))
AMI_USER = os.getenv("AMI_USER", "admin")
AMI_SECRET = os.getenv("AMI_SECRET", "supersecret123")

class AsteriskAMI:
    def __init__(self):
        self.manager = None

    async def connect(self):
        """Подключение к AMI интерфейсу Asterisk"""
        try:
            self.manager = Manager(
                loop=asyncio.get_running_loop(),
                host=AMI_HOST,
                port=AMI_PORT,
                username=AMI_USER,
                secret=AMI_SECRET
            )
            await self.manager.connect()
            print(f"Successfully connected to Asterisk AMI at {AMI_HOST}:{AMI_PORT}")
        except Exception as e:
            print(f"Failed to connect to Asterisk AMI at {AMI_HOST}:{AMI_PORT}: {e}")
            self.manager = None

    async def send_command(self, command: str):
        """
        Выполнение консольной команды Asterisk через AMI (Action: Command)
        """
        if not self.manager:
            await self.connect()
            if not self.manager:
                print(f"Cannot send command '{command}' - AMI not connected")
                return False

        try:
            # Отправляем команду, аналогичную вводу в 'asterisk -rx'
            response = await self.manager.send_action({
                'Action': 'Command',
                'Command': command
            })
            print(f"AMI Command '{command}' executed.")
            return response
        except Exception as e:
            print(f"AMI Command '{command}' failed: {e}")
            return False

    async def get_peers_status(self):
        """
        Запрашивает статусы всех PJSIP абонентов
        """
        if not self.manager:
            await self.connect()
            if not self.manager:
                return {"status": "error", "message": "AMI not connected"}

        try:
            response = await self.manager.send_action({'Action': 'PJSIPShowEndpoints'})
            return response
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Глобальный экземпляр клиента
ami_manager = AsteriskAMI()