import asyncio
import logging
from uuid import uuid4

from charging.client import ChargePointClient, launch_client, get_host_and_port, wait_for_button_press

logging.basicConfig(level=logging.ERROR)


# ID of the RFID token used to authenticate
RFID_TOKEN = 'AA12345'


# Emulates a normal charging process:
#   1. Authentication
#   2. Plug cable in
#   3. Start charging
async def charge_normally(cp: ChargePointClient):
    # Generate unique ID for future transaction
    transaction_id = str(uuid4())

    # === AUTHORIZATION ===

    await wait_for_button_press('AUTHORIZATION')

    # Send authorization request
    response = await cp.send_authorize(RFID_TOKEN)

    # Check if authorization was accepted
    if response.id_token_info['status'] != "Accepted":
        logging.error("Authorization failed")
        return
    else:
        print("Charging point authorization successful!")

    # Send authorized transaction event
    response = await cp.send_transaction_event_authorized('Started', transaction_id, 1, RFID_TOKEN)

    # Check if authorization was accepted
    if response.id_token_info['status'] != "Accepted":
        logging.error("Authorization failed")
        return
    else:
        print(f"Central authorization successful! Server message: '{response.updated_personal_message['content']}'")

    # === PLUG IN CABLE ===

    await wait_for_button_press('PLUG IN CABLE')

    # Send occupied notification (no meaningful response)
    await cp.send_status_notification('Occupied')
    print("Sent status notification for occupied cable")

    # Send cable plugged in transaction event
    response = await cp.send_transaction_event_cable_plugged_in('Updated', transaction_id, 2)
    print(f"Cable plug in successful! Server message: '{response.updated_personal_message['content']}'")

    # === START CHARGING ===

    await wait_for_button_press('START CHARGING')

    # Send cable plugged in transaction event
    response = await cp.send_transaction_event_charging_state_changed('Updated', transaction_id, 3, 'Charging')
    print(f"Started charging! Server message: '{response.updated_personal_message['content']}'")


if __name__ == "__main__":
    asyncio.run(launch_client(**get_host_and_port(), async_runnable=charge_normally))
