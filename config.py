import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "erp-chave-secreta"
    SQLALCHEMY_DATABASE_URI = "sqlite:///erp.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Número máximo de tentativas de login antes de bloquear e o tempo de bloqueio (segundos)
    MAX_LOGIN_ATTEMPTS = 3
    LOGIN_LOCK_SECONDS = 60
