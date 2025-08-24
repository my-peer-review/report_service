import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: str = os.getenv("ENV", "unit-test")
    jwt_algorithm: str
    jwt_public_key: str 
    postgres_url: str
    rabbitmq_username: str
    rabbitmq_password: str
    rabbitmq_url: str

    class Config:
        env_file = None

settings = Settings()