import requests

class CurrencyConverter:
    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("Exchange rate provider is not configured.")
        self.base_url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/"
    
    def convert(self, amount:float, from_currency:str, to_currency:str):
        """Convert the amount from one currency to another"""
        source = from_currency.upper()
        target = to_currency.upper()
        response = requests.get(f"{self.base_url}{source}", timeout=10)
        if response.status_code != 200:
            raise RuntimeError("Exchange rate provider request failed.")
        rates = response.json().get("conversion_rates")
        if not isinstance(rates, dict) or target not in rates:
            raise ValueError(f"{target} not found in exchange rates.")
        return float(amount) * float(rates[target])