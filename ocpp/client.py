import asyncio
import logging
import sys

import websockets

from ocpp.v201 import ChargePoint as cp
from ocpp.v201 import call
from websockets import Subprotocol

logging.basicConfig(level=logging.INFO)


class ChargePoint(cp):
    async def send_heartbeat(self, interval):
        request = call.HeartbeatPayload()
        while True:
            await self.call(request)
            await asyncio.sleep(interval)

    async def send_boot_notification(self):
        request = call.BootNotificationPayload(
            charging_station={"model": "Wallbox Optimus", "vendor_name": "The Mobility House"},
            reason="PowerUp",
        )
        response = await self.call(request)

        if response.status == "Accepted":
            logging.info("Connected to central system.")
            await self.send_heartbeat(response.interval)


async def main(host: str = 'ip6-localhost', port: int = 9000):
    async with websockets.connect(
        f"ws://{host}:{port}/CP_1", subprotocols=[Subprotocol("ocpp2.0.1")]
    ) as ws:

        cp = ChargePoint("CP_1", ws)

        await asyncio.gather(cp.start(), cp.send_boot_notification())


if __name__ == "__main__":
    arg_names = ['host', 'port']
    args = dict(zip(arg_names, sys.argv[1:]))

    asyncio.run(main(**args))
