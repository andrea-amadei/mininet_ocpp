import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import websockets
from ocpp.routing import on
from ocpp.v201 import ChargePoint as Cp
from ocpp.v201 import call_result
from websockets import Subprotocol

logging.basicConfig(level=logging.INFO)


def _get_current_time() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _get_personal_message(message: str) -> dict:
    return {
        'format': 'ASCII',
        'language': 'en',
        'content': message
    }

# Check if user can be authorized
# User is always authorized unless format is wrong
def _check_authorized(id_token: Dict) -> str:
    # Check of type and idToken fields exist
    if 'type' not in id_token or 'id_token' not in id_token:
        return 'Invalid'

    # Check if type is correct
    if id_token['type'] not in ('Central', 'eMAID', 'ISO14443', 'ISO15693'):
        return 'Unknown'

    # Always authorized
    return 'Accepted'


class ChargePoint(Cp):

    is_authorized: bool = False
    status: str = 'Available'
    charging_state: str = 'Idle'

    @on("BootNotification")
    def on_boot_notification(self,
        charging_station: Dict,
        reason: str,
        custom_data: Optional[Dict[str, Any]] = None
    ):
        logging.info(f"Got boot notification from {charging_station} for reason {reason}")

        return call_result.BootNotificationPayload(
            current_time=_get_current_time(), interval=10, status="Accepted"
        )

    @on("Heartbeat")
    def on_heartbeat(self,
        custom_data: Optional[Dict[str, Any]] = None
    ):
        return call_result.HeartbeatPayload(
            current_time=_get_current_time()
        )

    @on("Authorize")
    def on_authorize(self,
        id_token: Dict,
        certificate: Optional[str] = None,
        iso15118_certificate_hash_data: Optional[List] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ):
        logging.info(f"Got authorization request from {id_token}")

        return call_result.AuthorizePayload(id_token_info={"status": _check_authorized(id_token)})

    @on("StatusNotification")
    def on_status_notification(self,
        timestamp: str,
        connector_status: str,
        evse_id: int,
        connector_id: int,
        custom_data: Optional[Dict[str, Any]] = None
    ):
        # TODO: implement multiple connectors support
        self.status = connector_status

        return call_result.StatusNotificationPayload()

    @on("TransactionEvent")
    def on_transaction_event(self,
        event_type: str,
        timestamp: str,
        trigger_reason: str,
        seq_no: int,
        transaction_info: Dict,
        meter_value: Optional[List] = None,
        offline: Optional[bool] = None,
        number_of_phases_used: Optional[int] = None,
        cable_max_current: Optional[int] = None,
        reservation_id: Optional[int] = None,
        evse: Optional[Dict] = None,
        id_token: Optional[Dict] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ):
        logging.info(f"Got transaction event {event_type} because of {trigger_reason} with id {transaction_info['transaction_id']}")

        # When receiving an "Authorized" event
        if trigger_reason == "Authorized":

            # Check if authorized
            auth_result = _check_authorized(id_token)
            if auth_result != "Accepted":
                logging.error(f"User is not authorized for reason {auth_result}")
                return call_result.AuthorizePayload(id_token_info={"status": auth_result})

            logging.info(f"User is authorized")

            # Set as authorized
            self.is_authorized = True
            # Respond
            return call_result.TransactionEventPayload(
                id_token_info={"status": 'Accepted'},
                updated_personal_message=_get_personal_message('Charging is Authorized')
            )

        # When receiving a "CablePluggedIn" event
        elif trigger_reason == "CablePluggedIn":

            logging.info(f"Cable plugged in")

            # Respond
            return call_result.TransactionEventPayload(
                updated_personal_message=_get_personal_message('Cable is plugged in')
            )

        # When receiving a "ChargingStateChanged" event
        elif trigger_reason == "ChargingStateChanged":

            logging.info(f"Charging state changed to {transaction_info['charging_state']}")

            # Set correct charging state
            self.charging_state = transaction_info['charging_state']

            # Get correct charging message
            if self.charging_state == "Charging":
                message = "Charging started"
            elif self.charging_state in ("SuspendedEV", "SuspendedEVSE"):
                message = "Charging suspended"
            elif self.charging_state == "Idle":
                message = "Charging stopped"
            else:
                message = "Unknown"

            # Respond
            return call_result.TransactionEventPayload(
                updated_personal_message=_get_personal_message(message)
            )

        # When receiving any other event
        return call_result.TransactionEventPayload(
            updated_personal_message=_get_personal_message("Not implemented")
        )


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
