import os
import asyncio
import collections
import collections.abc

# Compatibility patch for panoramisk on Python 3.10+
collections.MutableMapping = collections.abc.MutableMapping

from panoramisk import Manager

AMI_HOST = os.getenv("AMI_HOST", "host.docker.internal")
AMI_PORT = int(os.getenv("AMI_PORT", "5038"))
AMI_USER = os.getenv("AMI_USER", "pbx_api")
AMI_SECRET = os.getenv("AMI_SECRET")


class AsteriskAMI:
    def __init__(self):
        self.manager = None

    async def connect(self):
        """Connect to the Asterisk AMI interface."""
        if not AMI_SECRET:
            print("AMI_SECRET is not configured; AMI connection is disabled")
            self.manager = None
            return

        try:
            self.manager = Manager(
                loop=asyncio.get_running_loop(),
                host=AMI_HOST,
                port=AMI_PORT,
                username=AMI_USER,
                secret=AMI_SECRET,
            )
            await self.manager.connect()
            print(f"Successfully connected to Asterisk AMI at {AMI_HOST}:{AMI_PORT}")
        except Exception as exc:
            print(f"Failed to connect to Asterisk AMI at {AMI_HOST}:{AMI_PORT}: {exc}")
            self.manager = None

    async def send_command(self, command: str):
        """Execute an Asterisk CLI command through AMI."""
        if not self.manager:
            await self.connect()
            if not self.manager:
                print(f"Cannot send command '{command}' - AMI not connected")
                return False

        try:
            response = await self.manager.send_action({"Action": "Command", "Command": command})
            print(f"AMI command '{command}' executed")
            return response
        except Exception as exc:
            print(f"AMI command '{command}' failed: {exc}")
            return False

    async def get_peers_status(self):
        """Return the status of configured PJSIP endpoints."""
        if not self.manager:
            await self.connect()
            if not self.manager:
                return {"status": "error", "message": "AMI not connected"}

        try:
            return await self.manager.send_action({"Action": "PJSIPShowEndpoints"})
        except Exception as exc:
            return {"status": "error", "message": str(exc)}


ami_manager = AsteriskAMI()
