import asyncio
import logging
from datetime import datetime

import websockets
from ocpp.routing import on
from ocpp.v201 import ChargePoint as Cp
from ocpp.v201 import call_result
from websockets import Subprotocol

logging.basicConfig(level=logging.INFO)


class ChargePoint(Cp):

    is_authorized = False

    @on("BootNotification")
    def on_boot_notification(self, charging_station, reason, **kwargs):
        logging.info(f"Got boot notification from {charging_station} for reason {reason}")

        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(), interval=10, status="Accepted"
        )

    @on("Heartbeat")
    def on_heartbeat(self):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        )

    @on("Authorize")
    def on_authorize(self, id_token, **kwargs):
        logging.info(f"Got authorization request from {id_token}")

        if self.is_authorized:
            status = 'ConcurrentTx'
        else:
            status = 'Accepted'

        return call_result.AuthorizePayload(id_token_info={"status": status})


async def on_connect(websocket, path):
    # Check if protocol is specified
    try:
        requested_protocols = websocket.request_headers["Sec-WebSocket-Protocol"]
    except KeyError:
        logging.error("Client hasn't requested any protocol. Closing Connection")
        return await websocket.close()

    # Check if protocol matches with the one on the server
    if websocket.subprotocol:
        logging.info("Protocols Matched: %s", websocket.subprotocol)
    else:
        logging.warning(f"Protocols Mismatched: client is using {websocket.subprotocol}. Closing connection")
        return await websocket.close()

    # Get id from path
    charge_point_id = path.strip("/")

    # Initialize CP
    cp = ChargePoint(charge_point_id, websocket)

    # Start
    await cp.start()


async def main():
    # Start websocket with callback function
    server = await websockets.serve(
        on_connect, "::", 9000, subprotocols=[Subprotocol("ocpp2.0.1")]
    )
    logging.info("Server Started listening to new connections...")

    # Wait for connection to be closed
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
