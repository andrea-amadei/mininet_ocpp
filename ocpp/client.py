import asyncio
import logging
import sys

import websockets

from ocpp.v16 import ChargePoint as cp
from ocpp.v16 import call
from ocpp.v16.enums import RegistrationStatus

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):
    async def send_boot_notification(self):
        request = call.BootNotificationPayload(
            charge_point_model="Optimus", charge_point_vendor="The Mobility House"
        )

        response = await self.call(request)

        if response.status == RegistrationStatus.accepted:
            print("Connected to central system.")


async def main(host: str = 'ip6-localhost', port: int = 9000):
    async with websockets.connect(
        f"ws://{host}:{port}/CP_1", subprotocols=["ocpp1.6"]
    ) as ws:

        cp = ChargePoint("CP_1", ws)

        await asyncio.gather(cp.start(), cp.send_boot_notification())


if __name__ == "__main__":
    arg_names = ['host', 'port']
    args = dict(zip(arg_names, sys.argv[1:]))

    asyncio.run(main(**args))
