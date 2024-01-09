import asyncio
import logging
import sys
from uuid import uuid4
from datetime import datetime

import aioconsole
import websockets
from ocpp.v201 import ChargePoint as Cp
from ocpp.v201 import call
from websockets import Subprotocol

logging.basicConfig(level=logging.ERROR)


def _get_current_time() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"


class ChargePoint(Cp):
    async def send_heartbeat(self, interval: int = 10):
        request = call.HeartbeatPayload()

        while True:
            # Send heartbeat
            await self.call(request)
            # Wait for interval
            await asyncio.sleep(interval)

    async def send_authorize(self, token: str):
        return await self.call(call.AuthorizePayload(
            id_token={
                'idToken': token,
                'type': 'ISO14443'
            }
        ))

    async def send_status_notification(self, connector_status: str, evse_id: int = 0, connector_id: int = 0):
        return await self.call(call.StatusNotificationPayload(
            timestamp=_get_current_time(),
            connector_status=connector_status,
            evse_id=evse_id,
            connector_id=connector_id
        ))

    async def send_transaction_event_authorized(self, event_type: str, transaction_id: str, seq_no: int, token: str):
        return await self.call(call.TransactionEventPayload(
            timestamp=_get_current_time(),
            event_type=event_type,
            seq_no=seq_no,
            transaction_info={'transactionId': transaction_id},

            trigger_reason='Authorized',
            id_token={'idToken': token, 'type': 'ISO14443'}
        ))

    async def send_transaction_event_cable_plugged_in(self, event_type: str, transaction_id: str, seq_no: int):
        return await self.call(call.TransactionEventPayload(
            timestamp=_get_current_time(),
            event_type=event_type,
            seq_no=seq_no,
            transaction_info={'transactionId': transaction_id},

            trigger_reason='CablePluggedIn'
        ))

    async def send_transaction_event_charging_state_changed(self, event_type: str, transaction_id: str, seq_no: int, charging_state: str):
        return await self.call(call.TransactionEventPayload(
            timestamp=_get_current_time(),
            event_type=event_type,
            seq_no=seq_no,
            transaction_info={'transactionId': transaction_id, 'chargingState': charging_state},

            trigger_reason='ChargingStateChanged',
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
    await aioconsole.ainput(f'\n{message} | Press any key to continue...\n')


async def run_simulation(cp: ChargePoint):
    # Generate unique ID for future transaction
    transaction_id = str(uuid4())
    # Use any RFID token
    rfid_token = 'AA12345'

    # === AUTHORIZATION ===

    await _wait_for_button_press('AUTHORIZATION')

    # Send authorization request
    response = await cp.send_authorize(rfid_token)

    # Check if authorization was accepted
    if response.id_token_info['status'] != "Accepted":
        logging.error("Authorization failed")
        return
    else:
        print("Charging point authorization successful!")

    # Send authorized transaction event
    response = await cp.send_transaction_event_authorized('Started', transaction_id, 1, rfid_token)

    # Check if authorization was accepted
    if response.id_token_info['status'] != "Accepted":
        logging.error("Authorization failed")
        return
    else:
        print(f"Central authorization successful! Server message: '{response.updated_personal_message['content']}'")

    # === PLUG IN CABLE ===

    await _wait_for_button_press('PLUG IN CABLE')

    # Send occupied notification (no meaningful response)
    await cp.send_status_notification('Occupied')
    print("Sent status notification for occupied cable")

    # Send cable plugged in transaction event
    response = await cp.send_transaction_event_cable_plugged_in('Updated', transaction_id, 2)
    print(f"Cable plug in successful! Server message: '{response.updated_personal_message['content']}'")

    # === START CHARGING ===

    await _wait_for_button_press('START CHARGING')

    # Send cable plugged in transaction event
    response = await cp.send_transaction_event_charging_state_changed('Updated', transaction_id, 3, 'Charging')
    print(f"Started charging! Server message: '{response.updated_personal_message['content']}'")


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
