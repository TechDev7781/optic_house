import requests

from src.env import env_settings


class BitrixService:
    # MARK: Deals
    @classmethod
    def get_deals(cls, filters: dict | None = None) -> list[dict]:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.item.list",
            json={
                "entityTypeId": 2,
                "filter": filters if filters else {},
                "select": ["*"],
            },
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении сделок: {response.text}, статус: {response.status_code}"
            )

        deals = response.json().get("result", {}).get("items", [])
        for deal in deals:
            contacts = deal.get("contactIds", [])
            if contacts:
                deal["contact"] = cls.get_contact(contacts[0])

        return deals

    @classmethod
    def create_deal(
        cls,
        title: str,
        category_id: int,
        stage_id: int,
        contact_id: int,
        company_id: int,
        products: list[dict],
    ) -> dict:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.deal.add",
            json={
                "fields": {
                    "TITLE": title,
                    "CATEGORY_ID": category_id,
                    "STAGE_ID": stage_id,
                    "CONTACT_ID": contact_id,
                    "UF_CRM_1777383408": company_id,
                },
            },
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при создании сделки: {response.text}, статус: {response.status_code}"
            )

        cls.add_products(response.json().get("result", {}), products)

        return response.json().get("result", {})

    @classmethod
    def update_deal(cls, deal_id: int, fields: dict) -> dict:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.item.update",
            json={"entityTypeId": 2, "id": deal_id, "fields": fields},
        )

        return response.json().get("result", {})

    @classmethod
    def get_contact(cls, contact_id: int) -> dict | None:
        response = requests.get(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.contact.get",
            params={"ID": contact_id},
        )

        if response.status_code != 200:
            return

        return response.json().get("result", {})

    # MARK: Categories
    @classmethod
    def get_categories(cls, filters: dict | None = None) -> list[dict]:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.category.list",
            json=filters if filters else {},
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении категорий: {response.text}, статус: {response.status_code}"
            )

        return response.json().get("result", {}).get("categories", [])

    # MARK: Doctors
    @classmethod
    def get_doctor(cls, id: int) -> dict:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/user.search",
            json={"ID": id},
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении врача: {response.text}, статус: {response.status_code}"
            )

        return response.json().get("result", [{}])[0]

    # MARK: Departaments
    @classmethod
    def get_departament(cls, id: int) -> list[dict]:
        response = requests.get(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.company.get",
            params={"id": id},
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении отделения: {response.text}, статус: {response.status_code}"
            )

        return response.json().get("result", [])

    # MARK: Products
    @classmethod
    def get_products(cls, deal_id: int, all: bool = False) -> list[dict]:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.item.productrow.list",
            json={
                "filter": {"=ownerType": "D", "=ownerId": deal_id},
                "select": ["*"],
            },
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении товарных позиций: {response.text}, статус: {response.status_code}"
            )

        products = response.json().get("result", {}).get("productRows", [])
        if all:
            return products

        return products[0]

    @classmethod
    def get_product_by_id(cls, product_id: int) -> dict:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/catalog.product.get",
            json={"id": product_id},
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при получении товара: {response.text}, статус: {response.status_code}"
            )

        return response.json().get("result", {}).get("product", {})

    @classmethod
    def add_products(cls, deal_id: int, products: list[dict]) -> dict:
        data = {
            "id": deal_id,
            "rows": [
                {
                    "PRODUCT_ID": p.get("id"),
                    "PRODUCT_NAME": p.get("productName"),
                    "PRICE": p.get("price"),
                    "PRICE_EXCLUSIVE": p.get("priceExclusive") or p.get("price"),
                    "PRICE_NETTO": p.get("priceNetto") or p.get("price"),
                    "PRICE_BRUTTO": p.get("priceBrutto") or p.get("price"),
                    "QUANTITY": p.get("quantity") or 1,
                    "DISCOUNT_TYPE_ID": p.get("discountTypeId") or 1,
                    "DISCOUNT_RATE": p.get("discountRate") or 0,
                    "DISCOUNT_SUM": p.get("discountSum") or 0,
                    "TAX_RATE": p.get("taxRate") or 0,
                    "TAX_INCLUDED": p.get("taxIncludeD") or 0,
                    "MEASURE_CODE": p.get("measureCode"),
                    "MEASURE_NAME": p.get("measureName"),
                    "SORT": p.get("sort"),
                }
                for p in products
            ],
        }

        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.deal.productrows.set",
            json=data,
        )

        if response.status_code != 200:
            raise Exception(
                f"Ошибка при добавлении товарных позиций: {response.text}, статус: {response.status_code}"
            )

        return response.json().get("result", {})

    # MARK: Logs
    @classmethod
    def get_logs_icons(cls) -> list[dict]:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.timeline.icon.list",
            json={},
        )

        return response.json().get("result", {}).get("icons", [])

    @classmethod
    def add_log(cls, deal_id: int, title: str, message: str) -> dict:
        response = requests.post(
            url=f"{env_settings.BITRIX_WEBHOOK_URL}/crm.timeline.logmessage.add",
            json={
                "fields": {
                    "entityTypeId": 2,
                    "entityId": deal_id,
                    "title": title,
                    "text": message,
                    "iconCode": "sms",
                },
            },
        )

        return response.json().get("result", {})
