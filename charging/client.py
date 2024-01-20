import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional, Callable, Awaitable

import aioconsole
import websockets
from ocpp.v201 import ChargePoint as Cp
from ocpp.v201 import call
from websockets import Subprotocol


logging.basicConfig(level=logging.ERROR)


def _get_current_time() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"


class ChargePointClient(Cp):
    async def send_heartbeat(
        self,
        interval: int = 10
    ):
        request = call.HeartbeatPayload()

        while True:
            # Send heartbeat
            await self.call(request)
            # Wait for interval
            await asyncio.sleep(interval)

    async def send_authorize(
        self,
        token: str
    ):
        return await self.call(call.AuthorizePayload(
            id_token={
                'idToken': token,
                'type': 'ISO14443'
            }
        ))

    async def send_status_notification(
        self,
        connector_status: str,
        evse_id: int = 0,
        connector_id: int = 0
    ):
        return await self.call(call.StatusNotificationPayload(
            timestamp=_get_current_time(),
            connector_status=connector_status,
            evse_id=evse_id,
            connector_id=connector_id
        ))

    async def send_transaction_event_authorized(
        self,
        event_type: str,
        transaction_id: str,
        seq_no: int,
        token: str
    ):
        return await self.call(call.TransactionEventPayload(
            timestamp=_get_current_time(),
            event_type=event_type,
            seq_no=seq_no,
            transaction_info={'transactionId': transaction_id},

            trigger_reason='Authorized',
            id_token={'idToken': token, 'type': 'ISO14443'}
        ))

    async def send_transaction_event_cable_plugged_in(
        self,
        event_type: str,
        transaction_id: str,
        seq_no: int
    ):
        return await self.call(call.TransactionEventPayload(
            timestamp=_get_current_time(),
            event_type=event_type,
            seq_no=seq_no,
            transaction_info={'transactionId': transaction_id},

            trigger_reason='CablePluggedIn'
        ))

    async def send_transaction_event_charging_state_changed(
        self,
        event_type: str,
        transaction_id: str,
        seq_no: int,
        charging_state: str
    ):
        return await self.call(call.TransactionEventPayload(
            timestamp=_get_current_time(),
            event_type=event_type,
            seq_no=seq_no,
            transaction_info={'transactionId': transaction_id, 'chargingState': charging_state},

            trigger_reason='ChargingStateChanged',
        ))

    async def send_boot_notification(
        self,
        serial_number: str,
        model: str,
        vendor_name: str,
        async_runnable: Optional[Callable[['ChargePointClient'], Awaitable[None]]] = None
    ):
        # Send boot notification
        request = call.BootNotificationPayload(
            charging_station={"model": model, "vendor_name": vendor_name, "serial_number": serial_number},
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

        # Run "runnable" function (if available) to implement a specific scenario
        if async_runnable is not None:
            await async_runnable(self)

        # Await for heartbeat task to end (never)
        await heartbeat_task


# Launches client and initializes server connection
async def launch_client(
    serial_number: str,
    model: str = 'Model',
    vendor_name: str = 'Vendor',
    server: str = "[::1]",
    port: int = 9000,
    async_runnable: Optional[Callable[[ChargePointClient], Awaitable[None]]] = None
):
    # Open websocket
    async with websockets.connect(
            f"ws://{server}:{port}/{serial_number}", subprotocols=[Subprotocol("ocpp2.0.1")]
    ) as ws:

        # Initialize CP
        cp = ChargePointClient(serial_number, ws)

        # Start it
        try:
            await asyncio.gather(
                cp.start(),
                cp.send_boot_notification(
                    serial_number,
                    model,
                    vendor_name,
                    async_runnable
                )
            )
        except websockets.exceptions.ConnectionClosed:
            print("Connection was forcefully closed by the server")


def get_host_and_port() -> dict[str, str]:
    # Get host and port from command line, if not default values of main function will be used
    arg_names = ['server', 'port']
    return dict(zip(arg_names, sys.argv[1:]))


# Prints the given message and awaits for a button press, in an asynchronous way
async def wait_for_button_press(message: str):
    await aioconsole.ainput(f'\n{message} | Press any key to continue...\n')


if __name__ == "__main__":
    config = {
        'vendor_name': 'EurecomCharge',
        'model': 'E2507',
        'serial_number': 'E2507-8420-1274',
    }

    asyncio.run(launch_client(**config, **get_host_and_port()))
