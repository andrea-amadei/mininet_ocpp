import requests
import click


g_host = '[::1]'
g_port = 8000


@click.group()
@click.option('--host', help='The host of the API server', default='[::1]', type=str)
@click.option('--port', help='The port of the API server', default=8000, type=int)
def cli(host: str = '[::1]', port: int = 8000):
    global g_host
    global g_port
    g_host = host
    g_port = port


@cli.command('reserve')
@click.option('--serial', help='The serial number of the charger', prompt='Serial number', required=True, type=str)
@click.option('--token-type', help='The type of the token', prompt='Token type', required=True, type=click.Choice(['Central', 'eMAID', 'ISO14443', 'ISO15693']))
@click.option('--token-id', help='The ID of the token', prompt='Token id', required=True, type=str)
def send_reservation_request(serial: str, token_type: str, token_id: str):
    # Send request
    response = requests.get(f'http://{g_host}:{g_port}/api/reserve_now/{serial}?type={token_type}&id_token={token_id}')

    # Check if the request was not successful (status code 200)
    if response.status_code != 200:
        click.echo(f"Error sending request: {response.status_code}")


if __name__ == '__main__':
    cli()
