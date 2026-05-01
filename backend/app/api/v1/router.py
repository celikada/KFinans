from fastapi import APIRouter
from app.api.v1 import auth, bes, integrations, wallets, portfolio, advice, tefas, stocks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(wallets.router)
api_router.include_router(portfolio.router)
api_router.include_router(tefas.router)
api_router.include_router(stocks.router)
api_router.include_router(bes.router)
api_router.include_router(advice.router)
