
import logging
from portfolio_source_collector.services.price_service import PriceService
from portfolio_source_collector.core.config import get_settings

logging.basicConfig(level=logging.DEBUG)

def main():
    settings = get_settings()
    service = PriceService(settings=settings)
    
    print("Fetching Yahoo Price for RUB...")
    price = service._fetch_yahoo_price("RUB")
    print(f"Result: {price}")

if __name__ == "__main__":
    main()
