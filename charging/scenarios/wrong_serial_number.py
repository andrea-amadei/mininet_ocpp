import asyncio

from charging.client import launch_client, get_host_and_port, ChargePointClient


async def main():
    config = {
        'vendor_name': 'EurecomCharge',
        'model': 'E2507',
        'serial_number': 'E2507-abcd-efgh',  # Wrong serial number
    }

    await launch_client(**config, **get_host_and_port())


if __name__ == "__main__":
    asyncio.run(main())
