# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.v1 import health
from app.routers.v1 import report

from sqlalchemy.ext.asyncio import create_async_engine
from app.database.postgres_report import PostgresReportRepository
from app.services.consumer_service import ReportConsumerService

def create_app() -> FastAPI:
    engine = create_async_engine(settings.postgres_url, echo=True, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        report_repository = PostgresReportRepository(engine)

        await report_repository.ensure_schema()

        app.state.report_repo = report_repository

        exchange_name = "elearning.reports"

        consumer = ReportConsumerService(
            rabbitmq_url=settings.rabbitmq_url,
            repo=report_repository,
            exchange_name=exchange_name,
            durable=True
        )
        app.state.consumer = consumer
        await consumer.start()

        try:
            yield
        finally:
            try:
                await consumer.stop()
            finally:
                # Chiudi connessione DB
                await engine.dispose()

    app = FastAPI(
        title="Report Microservice",
        description="Microservizio per la gestione degli Report",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(report.router, prefix="/api/v1", tags=["review"])
    return app


app = create_app()
