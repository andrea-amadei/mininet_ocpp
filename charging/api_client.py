import requests


BASE_URL = 'http://[::1]:8000/api'

def send_reservation_request(charger_serial_number: str, token_type: str, token_id: str):
    # Send request
    response = requests.get(f'{BASE_URL}/reserve_now/{charger_serial_number}?type={token_type}&id_token={token_id}')

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        print("GET request successful")
    else:
        print(f"Error: {response.status_code}")
