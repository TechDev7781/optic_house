import time
from datetime import datetime, timedelta
from typing import Literal

import requests

from src.constants import (
    ITIGRIS_URL,
)
from src.env import env_settings


class ItigrisService:
    REQUEST_TIMEOUT = 5

    default_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Host": "optima.itigris.ru",
    }

    # MARK: Auth
    @classmethod
    def login(
        cls,
        login: str,
        password: str,
        company: str = env_settings.ITIGRIS_COMPANY,
        department_id: int = env_settings.ITIGRIS_DEPARTAMENT_ID,
    ) -> str:
        response = requests.post(
            url=f"{ITIGRIS_URL}/api/v2/sign/in",
            json={
                "company": company,
                "login": login,
                "password": password,
                "departmentId": department_id,
            },
            headers=cls.default_headers,
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(f"Ошибка при входе в систему: {response.text}")

        return response.json()["accessToken"]

    # MARK: Clients
    @classmethod
    def get_client_id(cls, token: str, phone: str) -> str | None:
        response = requests.get(
            url=f"{ITIGRIS_URL}/api/v2/clients",
            params={
                "clientSearchType": "PHONE_NUMBER",
                "searchString": phone,
                "deleted": False,
            },
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении клиента: {response.text}, статус: {response.status_code}"
            )

        try:
            return response.json().get("content", [{}])[0].get("id")
        except Exception as e:
            print(f"Ошибка при получении клиента, создаем новый: {e}")

    @classmethod
    def get_client(cls, token: str, phone: str) -> dict | None:
        response = requests.get(
            url=f"{ITIGRIS_URL}/api/v2/clients",
            params={
                "clientSearchType": "PHONE_NUMBER",
                "searchString": phone,
                "deleted": False,
            },
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении клиента: {response.text}, статус: {response.status_code}"
            )

        try:
            return response.json().get("content", [{}])[0]
        except Exception as e:
            print(f"Ошибка при получении клиента, создаем новый: {e}")

    @classmethod
    def get_client_by_id(cls, token: str, id: int) -> dict | None:
        response = requests.get(
            url=f"{ITIGRIS_URL}/api/v2/clients/{id}/info",
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении клиента: {response.text}, статус: {response.status_code}"
            )

        try:
            client = response.json()

            client["phone"] = (
                client["tel1"]
                .replace("+", "")
                .replace("(", "")
                .replace(")", "")
                .replace("-", "")
                .replace(" ", "")
            )

            return client
        except Exception as e:
            print(f"Ошибка при получении клиента: {e}")

    @classmethod
    def create_client(
        cls,
        token: str,
        first_name: str,
        second_name: str,
        last_name: str,
        phone: str,
        comment: str,
        gender: Literal["MALE", "FEMALE"] | None = None,
        birthday_day: int | None = None,
        birthday_year: int | None = None,
        birthday_month: int | None = None,
    ):
        gender = True if gender == "MALE" else False

        if birthday_day is None:
            birthday_day = 1
        if birthday_year is None:
            birthday_year = 1990
        if birthday_month is None:
            birthday_month = 1

        response = requests.post(
            url=f"{ITIGRIS_URL}/api/v2/clients",
            json={
                "firstName": first_name,
                "familyName": second_name,
                "patronymicName": last_name,
                "tel1": phone,
                "comment": comment,
                "gender": gender,
                "informationSource": "Сайт",
                "birthdayDay": birthday_day,
                "birthdayYear": birthday_year,
                "birthdayMonth": birthday_month,
            },
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 201:
            raise Exception(
                f"Ошибка при создании клиента: {response.text}, статус: {response.status_code}"
            )

        return response.json()["id"]

    @classmethod
    def prepare_client(cls, token: str, id: int) -> None:
        response = requests.post(
            url=f"{ITIGRIS_URL}/api/v2/clients/{id}/agreements/prepare-text",
            json={
                "agreementType": "PERSONAL_DATA_PROCESSING",
                "collectionMethod": "QUESTIONNAIRE",
            },
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при подготовке клиента на первом этапе: {response.text}, статус: {response.status_code}"
            )

        response = requests.post(
            url=f"{ITIGRIS_URL}/api/v2/clients/{id}/agreements",
            json={
                "agreementType": "PERSONAL_DATA_PROCESSING",
                "collectionMethod": "QUESTIONNAIRE",
            },
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при подготовке клиента на втором этапе: {response.text}, статус: {response.status_code}"
            )

    @classmethod
    def update_client(cls, token: str, id: int, data: dict) -> dict:
        response = requests.put(
            url=f"{ITIGRIS_URL}/api/v2/clients/{id}",
            json=data,
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при обновлении клиента: {response.text}, статус: {response.status_code}"
            )

        return response.json()

    # MARK: Doctors
    @classmethod
    def get_doctor(
        cls,
        token: str,
        first_name: str | None = None,
        second_name: str | None = None,
        last_name: str | None = None,
    ) -> list[dict]:
        response = requests.get(
            url=f"{ITIGRIS_URL}/api/v2/users/available/doctors",
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if not response.status_code == 200:
            raise Exception(
                f"Ошибка при получении врачей: {response.text}, статус: {response.status_code}"
            )

        doctors = response.json()

        if first_name or second_name or last_name:
            filtered_doctors = []
            for d in doctors:
                if (
                    (not first_name or d.get("firstName") == first_name)
                    and (not second_name or d.get("familyName") == second_name)
                    and (not last_name or d.get("patronymicName") == last_name)
                ):
                    filtered_doctors.append(d)

            doctors = filtered_doctors

        return doctors[0] if doctors else None

    # MARK: Products
    @classmethod
    def get_product(
        cls,
        token: str,
        name: str,
    ) -> list[dict]:
        page = 0
        while True:
            response = requests.get(
                url=f"{ITIGRIS_URL}/api/v2/services/types",
                params={
                    "page": page,
                    "size": 10,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    **cls.default_headers,
                },
                timeout=cls.REQUEST_TIMEOUT,
            )

            if not response.status_code == 200:
                raise Exception(
                    f"Ошибка при получении типов услуг: {response.text}, статус: {response.status_code}"
                )

            products = response.json()["content"]
            if not products:
                break

            for product in products:
                if product.get("name") == name:
                    return product

            page += 1

            time.sleep(1)

    # MARK: Departaments
    @classmethod
    def get_departaments(
        cls,
        key: str = env_settings.ITIGRIS_KEY,
    ) -> list[dict]:
        response = requests.get(
            url=f"{ITIGRIS_URL}/remoteRegistry/getDepartments",
            params={
                "key": key,
            },
            headers={
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if not response.status_code == 200:
            raise Exception(
                f"Ошибка при получении отделений: {response.text}, статус: {response.status_code}"
            )

        return response.json()

    # MARK: Records
    @classmethod
    def create_record(
        cls,
        client_id: int,
        time: str,
        product_id: int,
        doctor_id: int,
        key: str = env_settings.ITIGRIS_KEY,
    ) -> None:
        params = {
            "key": key,
            "clientId": client_id,
            "userId": doctor_id,
            "serviceTypeId": product_id,
            "time": time,
        }

        response = requests.get(
            url=f"{ITIGRIS_URL}/remoteRegistry/register",
            params=params,
            headers={
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if not response.status_code == 200:
            raise Exception(
                f"Ошибка при создании записи: {response.text}, статус: {response.status_code}"
            )

    @classmethod
    def get_records(
        cls,
        token: str,
        status: str | None = None,
    ) -> list[dict]:
        params = {}
        if status:
            params["status"] = status

        params["appointmentFrom"] = datetime.now().strftime("%Y-%m-%d")

        response = requests.get(
            url=f"{ITIGRIS_URL}/api/v2/registry-records",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if not response.status_code == 200:
            raise Exception(
                f"Ошибка при получении записей с подтвержденным статусом: {response.text}, статус: {response.status_code}"
            )

        return response.json()

    # MARK: Orders
    @classmethod
    def get_orders(
        cls,
        token: str,
        status: str | None = None,
        department_id: int | None = None,
        created_from: str | None = datetime.now().strftime("%Y-%m-%d"),
        created_to: str | None = (datetime.now() + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        ),
        size: int = 100,
        page: int = 0,
    ) -> list[dict]:
        params = {}
        if status:
            params["status"] = status
        if department_id:
            params["departmentId"] = department_id
        if created_from:
            params["createdOnFrom"] = created_from
        if created_to:
            params["createdOnTo"] = created_to

        response = requests.get(
            url=f"{ITIGRIS_URL}/api/v2/orders",
            params={
                "size": size,
                "page": page,
                **params,
            },
            headers={
                "Authorization": f"Bearer {token}",
                **cls.default_headers,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if not response.status_code == 200:
            raise Exception(
                f"Ошибка при получении записей с подтвержденным статусом: {response.text}, статус: {response.status_code}"
            )

        orders = response.json()["content"]
        filtered_orders = []
        for order in orders:
            # if order["createdAt"] < (datetime.now() - timedelta(minutes=30)).strftime(
            #     "%Y-%m-%dT%H:%M:%S"
            # ):
            #     continue

            if status:
                if order.get("status") == status:
                    if status == "ORDER_READY":
                        if order["readyStatusInStore"] is True:
                            filtered_orders.append(order)
                    else:
                        filtered_orders.append(order)
            else:
                filtered_orders.append(order)

        return filtered_orders

    @classmethod
    def create_order(
        cls,
        client_id: int,
        departament_id: int,
        goods: list,
        price: float,
        key: str = env_settings.ITIGRIS_KEY,
    ) -> None:
        response = requests.post(
            url=f"{ITIGRIS_URL}/remoteSale/create",
            params={
                "key": key,
            },
            json={
                "departmentId": departament_id,
                "clientId": client_id,
                "paidSum": price,
                "goods": goods,
            },
            timeout=cls.REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при создании заказа: {response.text}, статус: {response.status_code}"
            )
