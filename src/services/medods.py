import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Literal

import requests

from src.constants import MEDODS_URL
from src.env import env_settings


class MedodsService:
    # MARK: Auth
    @staticmethod
    def _base64url_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    @classmethod
    def login(
        cls,
        identity: str = env_settings.MEDODS_IDENTITY_KEY,
        secret_key: str = env_settings.MEDODS_SECRET_KEY,
    ) -> str:
        issued_at = int(time.time()) - 10
        payload = {
            "iss": identity,
            "iat": issued_at,
            "exp": issued_at + 60,
        }
        header = {"alg": "HS512", "typ": "JWT"}

        encoded_header = cls._base64url_encode(
            json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        encoded_payload = cls._base64url_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )

        unsigned_token = f"{encoded_header}.{encoded_payload}"
        signature = hmac.new(
            secret_key.encode("utf-8"),
            unsigned_token.encode("ascii"),
            hashlib.sha512,
        ).digest()
        encoded_signature = cls._base64url_encode(signature)

        return f"{unsigned_token}.{encoded_signature}"

    # MARK: Doctors
    @classmethod
    def get_doctors(
        cls,
        token: str,
        name: str | None = None,
        second_name: str | None = None,
        last_name: str | None = None,
    ) -> list[dict]:
        params = {
            "limit": 100,
            "offset": 0,
            "userGroup": ["medical_staff"],
        }
        if name:
            params["name"] = name
        if second_name:
            params["surname"] = last_name
        if last_name:
            params["secondName"] = second_name

        response = requests.get(
            url=f"{MEDODS_URL}/users",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            print(
                f"Ошибка при получении врачей: {response.text}, статус: {response.status_code}"
            )
            return []

        return response.json()["data"]

    # MARK: Products
    @classmethod
    def get_products(cls, token: str, title: str | None = None) -> list[dict] | None:
        params = {
            "limit": 100,
            "offset": 0,
        }
        if title:
            params["title"] = title

        response = requests.get(
            url=f"{MEDODS_URL}/entries",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            return

        return response.json()["data"]

    # MARK: Departaments
    @classmethod
    def get_departaments(
        cls, token: str, title: str | None = None
    ) -> list[dict] | None:
        params = {
            "limit": 100,
            "offset": 0,
        }
        if title:
            params["title"] = title

        response = requests.get(
            url=f"{MEDODS_URL}/clinics",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            return

        departaments = response.json()["data"]

        if title:
            for d in departaments:
                if d["title"].strip() == title.strip():
                    return [d]

        return departaments

    # MARK: Clients
    @classmethod
    def get_client_by_phone(cls, token: str, phone: str) -> str | None:
        params = {
            "limit": 1,
            "offset": 0,
            "phone": phone,
        }

        response = requests.get(
            url=f"{MEDODS_URL}/clients",
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            return

        data = response.json()["data"]
        if data:
            return data[0]["id"]

    @classmethod
    def get_client_by_id(cls, token: str, id: int) -> str | None:
        if id > 100:
            offset = id - 100
        else:
            offset = 0

        limit = 100
        while True:
            response = requests.get(
                url=f"{MEDODS_URL}/clients",
                params={
                    "limit": limit,
                    "offset": offset,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                },
            )
            if response.status_code != 200:
                return

            clients = response.json()["data"]
            for client in clients:
                if client["id"] == id:
                    return client

            offset += limit

    @classmethod
    def create_client(
        cls,
        token: str,
        phone: str,
        first_name: str,
        last_name: str,
        second_name: str,
        gender: Literal["male", "female"] | None = None,
        birthdate: str | None = None,
    ) -> str | None:
        if gender is None:
            gender = "male"
        if birthdate is None:
            birthdate = "2000-01-01"

        response = requests.post(
            url=f"{MEDODS_URL}/clients",
            json={
                "phone": phone,
                "name": first_name,
                "surname": last_name,
                "secondName": second_name,
                "denyCalls": False,
                "denyEmail": False,
                "denySmsNotifications": False,
                "denySmsDispatches": False,
                "denyWhatsappMessages": False,
                "sex": gender,
                "birthdate": birthdate,
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при создании клиента: {response.text}, статус: {response.status_code}"
            )

        return response.json()["data"][0]["id"]

    # MARK: Records
    @classmethod
    def create_record(
        cls,
        token: str,
        client_id: str,
        doctor_id: int,
        product_id: int,
        departament_id: int,
        time: datetime,
    ) -> str | None:
        response = requests.post(
            url=f"{MEDODS_URL}/appointments",
            json={
                "clientId": client_id,
                "userId": doctor_id,
                "clinicId": departament_id,
                "date": time.strftime("%Y-%m-%d"),
                "time": time.strftime("%H:%M"),
                "duration": 60,
                "appointmentTypeId": 1,
                "appointmentSourceId": 1,
                "entryTypeIds": [int(product_id)],
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при создании записи: {response.text}, статус: {response.status_code}"
            )

        return response.json()["id"]

    @classmethod
    def get_records(
        cls, token: str, updated_at: datetime, status: str = "billed"
    ) -> list[dict]:
        records = cls._get_records(token, updated_at, status)
        new_records = []
        for record in records:
            try:
                order = cls._get_order(token, record.get("orderId"))
                entries = cls._get_entries(token, order.get("id"))
                record["entry"] = entries[0] if entries else None
                record["order"] = order
                new_records.append(record)
            except Exception:
                continue

        return new_records

    @classmethod
    def _get_records(
        cls, token: str, updated_at: datetime, status: str = "billed"
    ) -> list[dict]:
        response = requests.get(
            url=f"{MEDODS_URL}/appointments",
            params={
                "limit": 100,
                "offset": 0,
                "status": status,
                "updatedAtAfter": int(updated_at.timestamp()),
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении записей: {response.text}, статус: {response.status_code}"
            )

        return response.json()["data"]

    # MARK: Orders
    @classmethod
    def _get_order(cls, token: str, record_id: int) -> dict | None:
        response = requests.get(
            url=f"{MEDODS_URL}/orders/{record_id}",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            return

        return response.json()

    @classmethod
    def _get_entries(cls, token: str, order_id: int) -> list[dict] | None:
        response = requests.get(
            url=f"{MEDODS_URL}/entries",
            params={"limit": 100, "offset": 0, "orderId": order_id},
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            return

        return response.json()["data"]

    @classmethod
    def get_stores(cls, token: str) -> list[dict] | None:
        response = requests.get(
            url=f"{MEDODS_URL}/stores",
            params={"limit": 100, "offset": 0},
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code != 200:
            return

        return response.json()["data"]

    @classmethod
    def get_receips(cls, token: str, store_id: int) -> list[dict] | None:
        response = requests.get(
            url=f"{MEDODS_URL}/stores/receipts",
            params={
                "limit": 100,
                "offset": 0,
                "sourceStoreId": store_id,
                "destinationStoreId": store_id,
                "dateStart": (datetime.now() - timedelta(days=100)).strftime(
                    "%Y-%m-%d"
                ),
                "dateEnd": (datetime.now() + timedelta(days=100)).strftime("%Y-%m-%d"),
            },
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        print(json.dumps(response.json(), indent=4, ensure_ascii=False))
        if response.status_code != 200:
            return

        return response.json()["data"]
