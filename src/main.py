import time

from src.constants import FETCH_PERIOD_MINUTES, AppointmentStatusEnum, ServiceStatusEnum
from src.services.integration import IntegrationService

appointment_statuses = [
    AppointmentStatusEnum.CONFIRMED,
    AppointmentStatusEnum.ACCEPTED,
    AppointmentStatusEnum.SALE,
    AppointmentStatusEnum.EXPECTATION,
    AppointmentStatusEnum.RECEIPT,
]

service_statuses = [
    ServiceStatusEnum.REQUEST,
    ServiceStatusEnum.ACCEPTED,
    ServiceStatusEnum.MANUFACTURE,
    ServiceStatusEnum.DELIVERY,
    ServiceStatusEnum.COMPLETED,
]


def main() -> None:
    print("Запуск скрипта")
    explored_ids = {status: [] for status in appointment_statuses + service_statuses}

    while True:
        IntegrationService.handle_appointment_deals(appointment_statuses, explored_ids)
        IntegrationService.handle_service_deals(service_statuses, explored_ids)

        print(f"Ожидаем {FETCH_PERIOD_MINUTES} минут")
        time.sleep(60 * FETCH_PERIOD_MINUTES)


main()
