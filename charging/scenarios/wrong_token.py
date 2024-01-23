import asyncio
import logging

from charging.client import launch_client, get_host_and_port, ChargePointClient


async def wrong_token(cp: ChargePointClient):
    # Send authorization request
    response = await cp.send_authorize({'type': 'ISO14443', 'id_token': 'abcd'}) # Wrong token

    # Check if authorization was accepted
    if response.id_token_info['status'] != "Accepted":
        logging.error("Authorization failed")
        return
    else:
        cp.print_message("Charging point authorization successful!")


if __name__ == "__main__":

    config = {
        'vendor_name': 'EurecomCharge',
        'model': 'E2507',
        'serial_number': 'E2507-8420-1274',
    }

    asyncio.run(launch_client(**config, **get_host_and_port(), async_runnable=wrong_token))
