"""Configuración de la aplicación, leída del entorno o de backend/.env.

Ningún valor sensible vive en el código: la URL de la base (con su contraseña) y el secreto
del JWT llegan por variables de entorno. Si falta alguno, la aplicación no arranca.
"""

from functools import lru_cache

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VINCULO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Un JWT_SECRET o una URL inválidos no deben quedar impresos en los logs de arranque.
        hide_input_in_errors=True,
    )

    database_url: PostgresDsn

    # Nombres sin prefijo, como los pide la consigna de S05-S06-A2.
    # HS256 requiere al menos 256 bits de secreto (RFC 7518 §3.2): 32 bytes, 43 en base64.
    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET", min_length=43)
    # Segundos. Sin valor por omisión: la vigencia del token se decide en el entorno.
    jwt_expiration: int = Field(validation_alias="JWT_EXPIRATION", ge=60, le=86_400)


@lru_cache
def get_settings() -> Settings:
    """Una sola instancia por proceso; se lee el entorno la primera vez."""
    return Settings()
