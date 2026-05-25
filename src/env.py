import os

from dotenv import load_dotenv

load_dotenv()


class EnvSettings:
    ITIGRIS_COMPANY = str(os.getenv("ITIGRIS_COMPANY"))
    ITIGRIS_SECRETARY_LOGIN = str(os.getenv("ITIGRIS_SECRETARY_LOGIN"))
    ITIGRIS_SECRETARY_PASSWORD = str(os.getenv("ITIGRIS_SECRETARY_PASSWORD"))
    ITIGRIS_ADMINISTRATOR_LOGIN = str(os.getenv("ITIGRIS_ADMINISTRATOR_LOGIN"))
    ITIGRIS_ADMINISTRATOR_PASSWORD = str(os.getenv("ITIGRIS_ADMINISTRATOR_PASSWORD"))
    ITIGRIS_PASSWORD = str(os.getenv("ITIGRIS_PASSWORD"))
    ITIGRIS_DEPARTAMENT_ID = int(os.getenv("ITIGRIS_DEPARTAMENT_ID"))
    ITIGRIS_KEY = str(os.getenv("ITIGRIS_KEY"))

    BITRIX_WEBHOOK_URL = str(os.getenv("BITRIX_WEBHOOK_URL"))

    MEDODS_IDENTITY_KEY = str(os.getenv("MEDODS_IDENTITY_KEY"))
    MEDODS_SECRET_KEY = str(os.getenv("MEDODS_SECRET_KEY"))
    MEDODS_LOGIN = str(os.getenv("MEDODS_LOGIN"))
    MEDODS_PASSWORD = str(os.getenv("MEDODS_PASSWORD"))

    IS_LINUX_SERVER = bool(os.getenv("IS_LINUX_SERVER") or False)


env_settings = EnvSettings()
