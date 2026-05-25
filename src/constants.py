from enum import Enum

from src.env import env_settings

ITIGRIS_URL = f"https://optima.itigris.ru/{env_settings.ITIGRIS_COMPANY}"
MEDODS_URL = "https://moyvzglyad.medods.ru/api/v2"

MEDODS_WEBSITE_URL = "https://moyvzglyad.medods.ru/users/sign_in"
MEDODS_RECEIPT_URL = "https://moyvzglyad.medods.ru/orders/{order_id}"


class ServiceTypeEnum(Enum):
    MEDODS = "medods"
    BITRIX = "bitrix"
    ITIGRIS = "itigris"


class AppointmentStatusEnum(Enum):
    CONFIRMED = "Запись подтверждена"
    ACCEPTED = "Прием"
    SALE = "Продажа"
    EXPECTATION = "Ожидание"
    RECEIPT = "Получение"


class ServiceStatusEnum(Enum):
    REQUEST = "Заявка"
    ACCEPTED = "Принято"
    MANUFACTURE = "Изготовка/Ремонт"
    DELIVERY = "Выдача"
    COMPLETED = "Выполнено"


ITGRIS_ITEM_ID = 117505

FETCH_PERIOD_MINUTES = (
    1  # Период паузы между поиском обновленных сущностей в Bitrix24 и Itigris
)
