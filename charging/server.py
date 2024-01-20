import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

import websockets
import yaml
from ocpp.routing import on, after
from ocpp.v201 import ChargePoint as Cp
from ocpp.v201 import call_result
from websockets import Subprotocol

logging.basicConfig(level=logging.INFO)


# Will be loaded from server_config.yaml on startup
ACCEPTED_TOKENS = []
ACCEPTED_CHARGES = []
ALLOW_MULTIPLE_SERIAL_NUMBERS = True

# Holds ID and instance of all connected clients
connected_clients = []


def _get_current_time() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _get_personal_message(message: str) -> dict:
    return {
        'format': 'ASCII',
        'language': 'en',
        'content': message
    }

# Check if user can be authorized
def _check_authorized(id_token: Dict) -> str:
    # Check if type is correct
    if id_token['type'] not in ('Central', 'eMAID', 'ISO14443', 'ISO15693'):
        return 'Unknown'

    # Check if token is hexadecimal
    try:
        # Check if it can be converted to int from base 16
        int(id_token['id_token'], 16)
    except ValueError:
        return 'Unknown'

    # Check if it respects the specs of the type
    if id_token['type'] == 'Central':
        # Everything is accepted
        pass

    elif id_token['type'] == 'eMAID':
        # Not allowed in this implementation
        return 'Invalid'

    elif id_token['type'] == 'ISO14443':
        # Check if length is either 4 or 7 bytes
        if len(id_token['id_token']) != 8 and len(id_token['id_token']) != 14:
            return 'Invalid'

    elif id_token['type'] == 'ISO15693':
        # Check if length is 8 bytes
        if len(id_token['id_token']) != 16:
            return 'Invalid'

    else:
        return 'Unknown'

    # Check if token is in allowed list
    for i in ACCEPTED_TOKENS:
        if i['type'] == id_token['type'] and i['id_token'] == id_token['id_token']:
            return 'Accepted'

    # If no matching token was found in list
    return 'Invalid'


# Check if new CP is authorized based on vendor, model and serial number
def _check_charger(vendor_name: str, model: str, serial_number: str) -> bool:
    for i in ACCEPTED_CHARGES:
        # Check if vendor_name and model match
        if i['vendor_name'] == vendor_name and i['model'] == model:
            # Check if regex matches
            if re.match(i['serial_number_regex'], serial_number):
                return True

    # If no model match, return False
    return False


class ChargePointServer(Cp):

    is_booted: bool = False
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

        # Check if new CP has valid vendor, model and serial number
        self.is_booted = _check_charger(**charging_station)

        return call_result.BootNotificationPayload(
            current_time=_get_current_time(), interval=10, status=('Accepted' if self.is_booted else 'Rejected')
        )

    @after("BootNotification")
    async def after_boot_notification(self, *args, **kwargs):
        # If the CP was not booted (which means rejected)
        if not self.is_booted:
            # Force close websocket
            await self._connection.close()

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
        logging.error(f"Protocols Mismatched: client is using {websocket.subprotocol}. Closing connection")
        return await websocket.close()

    # Get id from path
    charge_point_id = path.strip("/")

    # Initialize CP
    cp = ChargePointServer(charge_point_id, websocket)

    # If only one CP per id is allowed, check it doesn't exist
    if not ALLOW_MULTIPLE_SERIAL_NUMBERS:
        for cp_id, cp in connected_clients:
            if cp_id == charge_point_id:
                logging.error(f"Client tried to connect with ID {cp_id}, but another client already exists")
                return await websocket.close()

    # Add to list of connected clients
    connected_clients.append((charge_point_id, cp))

    # Start and await for disconnection
    try:
        await cp.start()
    except websockets.exceptions.ConnectionClosed:
        logging.info(f"Client {charge_point_id} disconnected")

        # Remove from list of connected clients
        connected_clients.remove((charge_point_id, cp))


async def main():
    # Start websocket with callback function
    server = await websockets.serve(
        on_connect, "::", 9000, subprotocols=[Subprotocol("ocpp2.0.1")]
    )
    logging.info("Server Started listening to new connections...")

    # Wait for connection to be closed
    await server.wait_closed()


def load_config() -> bool:
    global ACCEPTED_TOKENS
    global ACCEPTED_CHARGES
    global ALLOW_MULTIPLE_SERIAL_NUMBERS

    # Open server config file
    with open("server_config.yaml", "r") as file:
        try:
            # Parse YAML content
            content = yaml.safe_load(file)

            # Set accepted tokens
            if "accepted_tokens" in content:
                ACCEPTED_TOKENS = content["accepted_tokens"]

            # Set accepted chargers
            if "accepted_chargers" in content:
                ACCEPTED_CHARGES = content["accepted_chargers"]

            # Set security parameters
            if "security" in content and "allow_multiple_serial_numbers" in content["security"]:
                ALLOW_MULTIPLE_SERIAL_NUMBERS = content["security"]["allow_multiple_serial_numbers"]

        except yaml.YAMLError as e:
            print('Failed to parse server_config.yaml')
            return False

        return True


if __name__ == "__main__":
    # Load config file
    if not load_config():
        quit(1)

    # Launch server
    asyncio.run(main())
