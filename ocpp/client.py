import asyncio
import logging
import sys

import aioconsole
import websockets
from ocpp.v201 import ChargePoint as Cp
from ocpp.v201 import call
from websockets import Subprotocol

logging.basicConfig(level=logging.ERROR)


class ChargePoint(Cp):
    async def send_heartbeat(self, interval):
        request = call.HeartbeatPayload()

        while True:
            # Send heartbeat
            await self.call(request)
            # Wait for interval
            await asyncio.sleep(interval)

    async def send_authorize(self, token):
        return await self.call(call.AuthorizePayload(
            id_token={
                'idToken': token,
                'type': 'ISO14443'
            }
        ))

    async def send_boot_notification(self):
        # Send boot notification
        request = call.BootNotificationPayload(
            charging_station={"model": "Wallbox Optimus", "vendor_name": "The Mobility House"},
            reason="PowerUp",
        )
        response = await self.call(request)

        # Check if boot notification is accepted
        if response.status != "Accepted":
            logging.error("Authorization failed")
            return
        else:
            print("Connected to central system!")

        # Schedule heartbeat to be run in background
        heartbeat_task = asyncio.create_task(self.send_heartbeat(response.interval))

        # Run simulation
        await run_simulation(self)

        # Await for heartbeat task to end (never)
        await heartbeat_task


async def _wait_for_button_press(message: str):
    await aioconsole.ainput(f'{message} | Press any key to continue...')


async def run_simulation(cp: ChargePoint):
    # Start authorization
    await _wait_for_button_press('AUTHORIZATION')

    # Send authorization request
    response = await cp.send_authorize('AA12345')

    # Check if authorization was accepted
    if response.id_token_info['status'] != "Accepted":
        logging.error("Authorization failed")
        return
    else:
        print("Authorization successful!")


async def main(host: str = "[::1]", port: int = 9000):
    # Open websocket
    async with websockets.connect(
            f"ws://{host}:{port}/CP_1", subprotocols=[Subprotocol("ocpp2.0.1")]
    ) as ws:

        # Initialize CP and start it
        cp = ChargePoint("CP_1", ws)
        await asyncio.gather(cp.start(), cp.send_boot_notification())


if __name__ == "__main__":
    # Get host and port from command line, if not default values of main function will be used
    arg_names = ['host', 'port']
    args = dict(zip(arg_names, sys.argv[1:]))

    # Run async function
    asyncio.run(main(**args))
