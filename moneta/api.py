from ninja import NinjaAPI
from transactions.api import router as transactions_router

api = NinjaAPI(title="Moneta API", version="1.0.0", description="API para o sistema de controle Finaneiro Moneta")

api.add_router("/transactions", transactions_router)