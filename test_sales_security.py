import requests

BASE_URL = "http://127.0.0.1:5000"

session = requests.Session()

# Login as employee
login_response = session.post(
    f"{BASE_URL}/login",
    data={
        "username": "funcionario",
        "password": "funcionario123"
    }
)

print("Login status:", login_response.status_code)

# Get the sale form's product and client IDs
page = session.get(f"{BASE_URL}/sales/new")
print("Sales page status:", page.status_code)

# Replace these with IDs of an existing client and active product
client_id = 1
product_id = 1

# Submit an invalid quantity directly to Flask
response = session.post(
    f"{BASE_URL}/sales/new",
    data={
        "client_id": client_id,
        "product_id": product_id,
        "quantity": "-1"
    },
    allow_redirects=False
)

print("Response status:", response.status_code)
print("Response contains validation message:",
      "A quantidade deve ser maior que zero." in response.text)
