from fastapi import APIRouter

from app.api.v1 import (
    advice,
    asset_catalog,
    audit_logs,
    auth,
    bes,
    budget,
    cash,
    cash_flow,
    commodity,
    credit_cards,
    credits,
    expenses,
    goal,
    income,
    integrations,
    manual_crypto,
    metrics,
    mfa,
    planned_expenses,
    portfolio,
    recurring,
    release,
    stocks,
    tefas,
    user,
    wallets,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(mfa.router)
api_router.include_router(user.router)
api_router.include_router(integrations.router)
api_router.include_router(wallets.router)
api_router.include_router(portfolio.router)
api_router.include_router(tefas.router)
api_router.include_router(stocks.router)
api_router.include_router(bes.router)
api_router.include_router(expenses.router)
api_router.include_router(planned_expenses.router)
api_router.include_router(goal.router)
api_router.include_router(income.router)
api_router.include_router(recurring.router)
api_router.include_router(release.router)
api_router.include_router(budget.router)
api_router.include_router(commodity.router)
api_router.include_router(cash.router)
api_router.include_router(cash_flow.router)
api_router.include_router(credit_cards.router)
api_router.include_router(credits.router)
api_router.include_router(manual_crypto.router)
api_router.include_router(asset_catalog.router)
api_router.include_router(advice.router)
api_router.include_router(audit_logs.router)
api_router.include_router(metrics.router)
