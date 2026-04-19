from fastmcp import FastMCP
import httpx
from datetime import datetime, date
from typing import List, Optional
import os

mcp = FastMCP("AirlineTickets")

GATEWAY_URL = "https://airline-api-gateway-duf0bja8hcc8caf5.uaenorth-01.azurewebsites.net"

# We assume a fixed user for booking flights based on instructions
USERNAME = "testuser"
PASSWORD = "testpassword123"

def get_auth_token():
    # Make a request to the auth token endpoint. 
    # Depending on how the midterm was implemented, we assume standard OAuth2 form-data
    response = httpx.post(
        f"{GATEWAY_URL}/api/v1/auth/token",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=True
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    
    # Try creating the user if we get 401 or similar, though usually we assume it exists.
    # Let's fallback to creating if needed.
    httpx.post(f"{GATEWAY_URL}/api/v1/auth/register", json={"username": USERNAME, "password": PASSWORD}, follow_redirects=True)
    
    # Try again
    response = httpx.post(
        f"{GATEWAY_URL}/api/v1/auth/token",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=True
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def fetch_flights(params: dict, label: str) -> List[str]:
    """Helper to fetch all pages for a specific direction/set of params."""
    results = []
    current_skip = params.get("skip", 0)
    
    # We copy params to avoid mutating the original dictionary between calls
    local_params = params.copy()
    
    try:
        # Gemini Safety: Limit to 5 pages (50 flights) to prevent context bloating
        for _ in range(5):
            local_params["skip"] = current_skip
            response = httpx.get(f"{GATEWAY_URL}/api/v1/flights", params=local_params, timeout=10.0, follow_redirects=True)
            
            if response.status_code == 200:
                chunk = response.json()
                if not chunk:
                    break
                for f in chunk:
                    results.append(f"{label} {f}")
                if len(chunk) < 10:
                    break
                current_skip += 10
            else:
                break
    except Exception:
        pass
    return results

@mcp.tool()
def search_flights(
    airport_from: Optional[str] = None,
    airport_to: Optional[str] = None,
    date: Optional[str] = None, # ISO format date 'YYYY-MM-DD'
    date_to: Optional[str] = None, # ISO format date
    number_of_people: int = 1,
    is_round_trip: bool = False
) -> str:
    """
    Search for available flights. Returns a list of flights matching the criteria.
    date_from and date_to should be in format 'YYYY-MM-DD'.
    """
    
    # Normalize inputs
    airport_from = airport_from.upper() if airport_from else None
    airport_to = airport_to.upper() if airport_to else None
    
    if not airport_from or not airport_to or not date:
        return "CRITICAL ERROR: Missing required search information (Departure Airport, Destination Airport, or Date). Please ask the user for these missing details instead of searching."
    
    if is_round_trip and not date_to:
        return "CRITICAL ERROR: 'is_round_trip' is True but 'date_to' (Return Date) is missing. You MUST provide the return date to search for a round trip."
    
    # LEG 1: Outbound
    outbound_params = {
        "number_of_people": number_of_people,
        "is_round_trip": "false" # We always do single passes from here
    }
    if airport_from: outbound_params["airport_from"] = airport_from
    if airport_to: outbound_params["airport_to"] = airport_to
    if date: outbound_params["date_from"] = date
    
    labeled_flights = fetch_flights(outbound_params, "[OUTBOUND/GİDİŞ]")
    
    # LEG 2: Return (If requested)
    if is_round_trip and date_to:
        inbound_params = {
            "number_of_people": number_of_people,
            "is_round_trip": "false"
        }
        # Swap airports for return leg
        if airport_to: inbound_params["airport_from"] = airport_to
        if airport_from: inbound_params["airport_to"] = airport_from
        inbound_params["date_from"] = date_to
        
        return_flights = fetch_flights(inbound_params, "[RETURN/DÖNÜŞ]")
        labeled_flights.extend(return_flights)

    if not labeled_flights:
        search_info = f"{airport_from} to {airport_to} on {date}"
        if is_round_trip and date_to:
            search_info += f" and return on {date_to}"
        return f"No flights found for {search_info}. Tell the user exactly which date and route you searched."
        
    output = f"Success! Found flights: {labeled_flights}. Print this list beautifully to the user. EĞER listede '[RETURN/DÖNÜŞ]' etiketli uçuş yoksa, kullanıcıya dürüstçe 'Dönüş uçuşu bulunamadı' de."
    return output

@mcp.tool()
def book_flight(
    flight_number: str,
    date: str,
    passenger_names: List[str]
) -> str:
    """
    Book a flight. Requires the flight_number, the date of the flight ('YYYY-MM-DD'), and a list of passenger names.
    Returns the transaction status and ticket numbers.
    """
    token = get_auth_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    payload = {
        "flight_number": flight_number,
        "date": date,
        "passeger_names": passenger_names  # Note the spelling matches the schema
    }
    
    try:
        response = httpx.post(f"{GATEWAY_URL}/api/v1/tickets/buy", json=payload, headers=headers, timeout=10.0, follow_redirects=True)
        
        if response.status_code == 200:
            return f"Booking Successful! Details: {response.json()} Tell the user it was successful."
        else:
            return f"CRITICAL API ERROR: {response.status_code}. Tell the user exactly: 'Bilet alımı sırasında hata oluştu: {response.text}'"
    except Exception as e:
        return f"CRITICAL CONNECTION ERROR. Tell the user: 'Bağlantı koptu: {str(e)}'"

@mcp.tool()
def check_in(
    ticket_number: str,
    flight_number: str,
    date: str,
    passenger_name: str
) -> str:
    """
    Check-in for a flight. Requires ticket_number, flight_number, date ('YYYY-MM-DD'), and passenger_name.
    Returns the transaction status and assigned seat.
    """
    payload = {
        "ticket_number": ticket_number,
        "flight_number": flight_number,
        "date": date,
        "passenger_name": passenger_name
    }
    
    try:
        response = httpx.post(f"{GATEWAY_URL}/api/v1/tickets/check-in", json=payload, timeout=10.0, follow_redirects=True)
        
        if response.status_code == 200:
            return f"Check-in Successful! Details: {response.json()} Tell the user exactly their seat number!"
        
        # Humanize technical validation errors (400, 422)
        error_msg = response.text
        if response.status_code in [400, 422]:
            error_msg = "Some input information (ticket number, date, or name) is missing or in the wrong format."
            
        return f"API_ERROR: {response.status_code}. Message: {error_msg}. DO NOT show this technical error to user. Instead, tell them: 'Girdiğiniz bilgilerde bir eksiklik veya format hatası var. Lütfen tüm bilgileri (Tarih: YYYY-MM-DD gibi) doğru girdiğinizden emin olun.'"
    except Exception as e:
        return f"CRITICAL CONNECTION ERROR. Tell the user: 'Bağlantı koptu: {str(e)}'"

if __name__ == "__main__":
    mcp.run()
