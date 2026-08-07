from ninja import NinjaAPI

from transactions.api import router as transactions_router
from wallets.api import router as wallets_router
from planning.api import router as planning_router
from investments.api import router as investments_router
from users.api import router as users_router

api = NinjaAPI(
    title="Moneta API",
    version="1.0.0",
    description="API para o sistema de controle Financeiro Moneta"
)

api.add_router("/transactions", transactions_router)
api.add_router("/wallets", wallets_router)
api.add_router("/planning", planning_router)
api.add_router("/investments", investments_router)
api.add_router("/users", users_router)