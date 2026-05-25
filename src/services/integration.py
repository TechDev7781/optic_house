import json
import time
from datetime import datetime, timedelta, timezone

from src.constants import (
    ITGRIS_ITEM_ID,
    AppointmentStatusEnum,
    ServiceStatusEnum,
    ServiceTypeEnum,
)
from src.env import env_settings
from src.services.bitrix import BitrixService
from src.services.itigris import ItigrisService
from src.services.medods import MedodsService
from src.services.parser import ParserService


class IntegrationService:
    @classmethod
    def handle_appointment_deals(
        cls,
        statuses: list[AppointmentStatusEnum],
        explored_ids: dict[str, list[int]],
    ) -> None:
        print(
            f"Начата обработка сделок: statuses={statuses}, started_at={datetime.now().strftime('%Y-%m-%d %H;:%M:%S')})"
        )

        try:
            categories = BitrixService.get_categories(
                filters={
                    "entityTypeId": 2,
                }
            )

            category_id = None
            for category in categories:
                if category.get("name") == "Посещение":
                    category_id = category.get("id")
                    break

            if not category_id:
                print("Категория 'Посещение' не найдена")
                exit()

            itigris_token = ItigrisService.login(
                login=env_settings.ITIGRIS_SECRETARY_LOGIN,
                password=env_settings.ITIGRIS_SECRETARY_PASSWORD,
            )
            for status in statuses:
                if status == AppointmentStatusEnum.CONFIRMED:
                    itgris_admin_token = ItigrisService.login(
                        login=env_settings.ITIGRIS_ADMINISTRATOR_LOGIN,
                        password=env_settings.ITIGRIS_ADMINISTRATOR_PASSWORD,
                    )
                    medods_token = MedodsService.login()

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": AppointmentStatusEnum.CONFIRMED.value,
                        }
                    )

                    print(f"Получены сделки для статуса '{status}': {len(deals)}")

                    for deal in deals:
                        try:
                            if deal["id"] in explored_ids[status]:
                                continue

                            explored_ids[status].append(deal["id"])

                            doctor = BitrixService.get_doctor(
                                deal.get("ufCrm_1777383278")
                            )
                            product = BitrixService.get_products(deal.get("id"))
                            departament = BitrixService.get_departament(
                                deal.get("ufCrm_1777383408")
                            )
                            comments = deal.get("comments", "")
                            date = datetime.fromisoformat(
                                deal.get("ufCrm_653FAD295CC62", "")
                            )
                            phone_number = (
                                deal.get("contact", {})
                                .get("PHONE", [{}])[0]
                                .get("VALUE")[1:]
                            )
                            first_name = (
                                deal.get("contact", {}).get("NAME") or "Отсутствует"
                            )
                            second_name = (
                                deal.get("contact", {}).get("SECOND_NAME")
                                or "Отсутствует"
                            )
                            last_name = (
                                deal.get("contact", {}).get("LAST_NAME")
                                or "Отсутствует"
                            )
                            birthday = deal.get("contact", {}).get("BIRTHDATE")
                            if birthday:
                                birthday = datetime.fromisoformat(birthday)

                            gender = (
                                "FEMALE"
                                if deal.get("contact", {}).get("UF_CRM_1697191828264")
                                == "47"
                                else "MALE"
                            )

                            print(
                                f"Обработка сделки {deal['id']}: doctor={doctor.get('NAME')} {doctor.get('LAST_NAME')} {doctor.get('SURNAME', 'Отсутствует')}, "
                                f"product={product.get('productName')}, department={departament.get('TITLE')}, date={date}, phone={phone_number}, "
                                f"fio={first_name} {second_name} {last_name}"
                            )
                            for service_type_enum in [
                                ServiceTypeEnum.ITIGRIS,
                                ServiceTypeEnum.MEDODS,
                            ]:
                                try:
                                    # MARK: Itigris
                                    if service_type_enum == ServiceTypeEnum.ITIGRIS:
                                        # Получение врача и услуги
                                        doctor_name = doctor.get("NAME") or ""
                                        doctor_last_name = doctor.get("LAST_NAME") or ""
                                        doctor_surname = doctor.get("SURNAME") or ""

                                        itigris_doctor = ItigrisService.get_doctor(
                                            itigris_token,
                                            first_name=doctor_name,
                                            second_name=doctor_last_name,
                                            last_name=doctor_surname,
                                        )
                                        if not itigris_doctor:
                                            print(
                                                f"Врач {doctor_name} {doctor_last_name} {doctor_surname} не найден в Itigris для сделки {deal['id']}"
                                            )
                                            continue

                                        itigris_product = ItigrisService.get_product(
                                            token=itgris_admin_token,
                                            name=product["productName"],
                                        )
                                        if not itigris_product:
                                            print(
                                                f"Товар {product['productName']} не найден в Itigris для сделки {deal['id']}"
                                            )
                                            continue

                                        # Получение ID клиента в Itigris по номеру телефона
                                        client_id = ItigrisService.get_client_id(
                                            token=itigris_token,
                                            phone=phone_number,
                                        )
                                        # Если клиент не найден, создаем нового
                                        if not client_id:
                                            client_id = ItigrisService.create_client(
                                                token=itigris_token,
                                                first_name=first_name,
                                                second_name=second_name,
                                                last_name=last_name,
                                                phone=phone_number,
                                                comment=comments,
                                                gender=gender,
                                                birthday_day=birthday.day
                                                if birthday
                                                else None,
                                                birthday_year=birthday.year
                                                if birthday
                                                else None,
                                                birthday_month=birthday.month
                                                if birthday
                                                else None,
                                            )
                                            ItigrisService.prepare_client(
                                                itigris_token, client_id
                                            )

                                        # Создание записи в Itigris
                                        dt_utc = date.astimezone(
                                            timezone(timedelta(hours=3))
                                        )
                                        date_formatted = dt_utc.strftime(
                                            "%Y-%m-%dT%H:%M:%S"
                                        )

                                        ItigrisService.create_record(
                                            client_id=client_id,
                                            time=date_formatted,
                                            doctor_id=itigris_doctor.get("id"),
                                            product_id=itigris_product.get("id"),
                                        )

                                        time.sleep(2)

                                        records = ItigrisService.get_records(
                                            itigris_token
                                        )
                                        if not records:
                                            print(
                                                f"Записи для клиента Itigris {client_id} не найдены"
                                            )
                                            continue

                                        max_id = None
                                        for record in records:
                                            if not max_id:
                                                max_id = int(record.get("id", 0))
                                            else:
                                                if int(record.get("id", 0)) > max_id:
                                                    max_id = int(record.get("id", 0))
                                    elif service_type_enum == ServiceTypeEnum.MEDODS:
                                        # MARK: Medods
                                        doctor_name = doctor.get("NAME") or ""
                                        doctor_last_name = doctor.get("LAST_NAME") or ""
                                        doctor_surname = doctor.get("SURNAME") or ""

                                        doctors = MedodsService.get_doctors(
                                            medods_token,
                                            name=doctor_name or None,
                                            second_name=doctor_last_name or None,
                                            last_name=doctor_surname or None,
                                        )
                                        if not doctors:
                                            print(
                                                f"Врач {doctor_name} {doctor_last_name} {doctor_surname} не найден в Medods для сделки {deal['id']}"
                                            )
                                            continue
                                        doctor_id = doctors[0].get("id")

                                        products = MedodsService.get_products(
                                            medods_token,
                                            title=product["productName"],
                                        )
                                        if not products:
                                            print(
                                                f"Товар {product['productName']} не найден в Medods для сделки {deal['id']}"
                                            )
                                            continue
                                        product_id = products[0].get("entryTypeId")

                                        departaments = MedodsService.get_departaments(
                                            medods_token,
                                            title=departament["TITLE"],
                                        )
                                        if not departaments:
                                            print(
                                                f"Отделение {departament['TITLE']} не найдено в Medods для сделки {deal['id']}"
                                            )
                                            continue

                                        departament_id = departaments[0].get("id")

                                        client_id = MedodsService.get_client_by_phone(
                                            token=medods_token,
                                            phone=phone_number,
                                        )
                                        # Если клиент не найден, создаем нового
                                        if not client_id:
                                            try:
                                                client_id = MedodsService.create_client(
                                                    token=medods_token,
                                                    first_name=first_name,
                                                    second_name=second_name,
                                                    last_name=last_name,
                                                    phone=phone_number,
                                                    gender="male"
                                                    if gender == "MALE"
                                                    else "female",
                                                    birthdate=birthday.strftime(
                                                        "%Y-%m-%d"
                                                    )
                                                    if birthday
                                                    else None,
                                                )
                                            except Exception as e:
                                                print(
                                                    f"Ошибка при создании клиента в Medods для сделки {deal['id']}: {e}"
                                                )
                                                time.sleep(2)
                                                client_id = (
                                                    MedodsService.get_client_by_phone(
                                                        token=medods_token,
                                                        phone=phone_number,
                                                    )
                                                )

                                        # Создание записи в Medods
                                        MedodsService.create_record(
                                            token=medods_token,
                                            client_id=client_id,
                                            time=date,
                                            doctor_id=doctor_id,
                                            product_id=product_id,
                                            departament_id=departament_id,
                                        )

                                    print(
                                        f"Сделка {deal['id']} обработана успешно для системы {service_type_enum.value}"
                                    )
                                except Exception as e:
                                    explored_ids[status].remove(deal["id"])
                                    print(
                                        f"Ошибка при обработке сделки {deal['id']}: {e}"
                                    )
                                    BitrixService.add_log(
                                        deal["id"],
                                        "Ошибка при обработке сделки для системы {service_type_enum.value}",
                                        f"Ошибка при обработке сделки {deal['id']} для системы {service_type_enum.value}: {e}",
                                    )
                                    continue

                            BitrixService.add_log(
                                deal["id"],
                                "Сделка перенесена в системы битрикс и медодс",
                                "Сделка перенесена в системы битрикс и медодс",
                            )
                        except Exception as e:
                            print(f"Ошибка при обработке сделок: {e}")
                elif status == AppointmentStatusEnum.ACCEPTED:
                    medods_token = MedodsService.login()

                    billed_orders = MedodsService.get_records(
                        medods_token,
                        datetime.now() - timedelta(days=1),
                        status="serviced",
                    )
                    print(
                        f"Получено заказов Medods к обработке: {len(billed_orders or [])}"
                    )

                    if not billed_orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    for driver in ParserService.initialize():
                        deals = BitrixService.get_deals(
                            filters={
                                "categoryId": category_id,
                                "%searchContent": AppointmentStatusEnum.CONFIRMED.value,
                            }
                        )

                        for order in billed_orders:
                            try:
                                if not order.get("order"):
                                    continue

                                if order["id"] in explored_ids[status]:
                                    continue

                                explored_ids[status].append(order["id"])

                                receipt = ParserService.parse_receipt(
                                    driver, order["order"]
                                )
                                if not receipt:
                                    print(
                                        f"Не удалось получить чек для заказа {order.get('id')}"
                                    )
                                    continue

                                client = MedodsService.get_client_by_id(
                                    medods_token,
                                    id=order.get("clientId"),
                                )

                                deal_id = None
                                found_deal = None
                                for deal in deals:
                                    phone_number = None
                                    for content in deal.get("searchContent", []).split(
                                        " "
                                    ):
                                        if content.startswith("7"):
                                            phone_number = content
                                            break

                                    if phone_number == client["phone"]:
                                        deal_id = deal.get("id")
                                        found_deal = deal
                                        break

                                if deal_id:
                                    print(
                                        f"Найдена сделка Bitrix {deal_id} для клиента {client['phone']}, обновляем"
                                    )

                                    comment = (
                                        (found_deal.get("ufCrm_1775443778587") + "\n\n")
                                        if found_deal.get("ufCrm_1775443778587")
                                        else ""
                                    )

                                    result = BitrixService.update_deal(
                                        deal_id,
                                        {
                                            "ufCrm_1775443778587": receipt,
                                            "stageId": "C9:FINAL_INVOICE",
                                        },
                                    )

                                    print(
                                        f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                                    )

                                    new_category_id = None
                                    for category in categories:
                                        if category.get("name") == "Сервисный центр":
                                            new_category_id = category.get("id")
                                            break

                                    if not new_category_id:
                                        print("Категория 'Сервисный центр' не найдена")
                                        continue

                                    products = BitrixService.get_products(
                                        found_deal.get("id"), all=True
                                    )

                                    result = BitrixService.create_deal(
                                        title=found_deal.get("title"),
                                        category_id=new_category_id,
                                        stage_id="C11:NEW",
                                        contact_id=found_deal.get("contact", {}).get(
                                            "ID"
                                        ),
                                        company_id=found_deal.get("ufCrm_1777383408"),
                                        products=products,
                                    )

                                    print(
                                        f"Ответ от битрикса при создании сделки в новой воронке: {json.dumps(result, indent=4, ensure_ascii=False)}"
                                    )
                                else:
                                    print(
                                        f"Сделка Bitrix для клиента {client['phone']} не найдена"
                                    )

                                itigris_client = ItigrisService.get_client(
                                    token=itigris_token,
                                    phone=client["phone"],
                                )

                                if itigris_client:
                                    print(
                                        f"Обновление клиента Itigris id={itigris_client.get('id')} phone={client.get('phone')}"
                                    )
                                    comment = (
                                        (client.get("comment") + "\n\n")
                                        if client.get("comment")
                                        else ""
                                    )

                                    update_result = ItigrisService.update_client(
                                        id=itigris_client.get("id"),
                                        token=itigris_token,
                                        data={
                                            **itigris_client,
                                            "comment": receipt,
                                            "gender": client.get("gender") or True,
                                            "informationSource": "Сайт",
                                            "birthdayDay": client.get("birthdayDay")
                                            or 1,
                                            "birthdayYear": client.get("birthdayYear")
                                            or 1990,
                                            "birthdayMonth": client.get("birthdayMonth")
                                            or 1,
                                        },
                                    )

                                    print(
                                        f"Результат обновления клиента {client.get('phone')}: {json.dumps(update_result, indent=4, ensure_ascii=False)}"
                                    )
                                else:
                                    print(
                                        f"Клиент Itigris для клиента {client['phone']} не найден"
                                    )
                            except Exception as e:
                                explored_ids[status].remove(order["id"])
                                print(f"Ошибка при обработке сделки: {e}")
                elif status == AppointmentStatusEnum.SALE:
                    orders = ItigrisService.get_orders(
                        token=itigris_token,
                        status="ACCEPTED",
                    )
                    print(
                        f"Получено заказов Itigris со статусом ACCEPTED: {len(orders or [])}"
                    )

                    if not orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": AppointmentStatusEnum.ACCEPTED.value,
                        }
                    )

                    for order in orders:
                        try:
                            if order["id"] in explored_ids[status]:
                                continue

                            print(
                                f"Обработка заказа {json.dumps(order, indent=4, ensure_ascii=False)}"
                            )
                            explored_ids[status].append(order["id"])

                            client = ItigrisService.get_client_by_id(
                                token=itigris_token,
                                id=order.get("clientId"),
                            )
                            if not client:
                                continue

                            deal_id = None
                            found_deal = None
                            for deal in deals:
                                phone_number = None
                                for content in deal.get("searchContent", []).split(" "):
                                    if content.startswith("7"):
                                        phone_number = content
                                        break

                                if phone_number == client["phone"]:
                                    deal_id = deal.get("id")
                                    found_deal = deal
                                    break

                            if deal_id:
                                result = BitrixService.update_deal(
                                    deal_id,
                                    {
                                        "stageId": "C9:UC_TOJ76V",
                                    },
                                )

                                if found_deal["opportunity"] != order["sum"]:
                                    products = BitrixService.get_products(
                                        deal_id,
                                        all=True,
                                    )
                                    existing_products = [
                                        {"id": p["productId"], "price": p["price"]}
                                        for p in products
                                    ]

                                    BitrixService.add_products(
                                        deal_id,
                                        [
                                            {
                                                "id": ITGRIS_ITEM_ID,
                                                "price": order["sum"]
                                                - found_deal["opportunity"],
                                            },
                                            *existing_products,
                                        ],
                                    )

                                print(
                                    f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                                )
                            else:
                                print(
                                    f"Сделка Bitrix для клиента {client['phone']} не найдена"
                                )
                        except Exception as e:
                            explored_ids[status].remove(order["id"])
                            print(f"Ошибка при обработке сделки: {e}")
                elif status == AppointmentStatusEnum.EXPECTATION:
                    orders = ItigrisService.get_orders(
                        token=itigris_token,
                        status="ORDER_READY",
                    )
                    print(
                        f"Получено заказов Itigris со статусом ORDER_READY: {len(orders or [])}"
                    )

                    if not orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": AppointmentStatusEnum.SALE.value,
                        }
                    )

                    for order in orders:
                        try:
                            if order["id"] in explored_ids[status]:
                                continue

                            explored_ids[status].append(order["id"])

                            client = ItigrisService.get_client_by_id(
                                token=itigris_token,
                                id=order.get("clientId"),
                            )

                            if not client:
                                continue

                            deal_id = None
                            for deal in deals:
                                phone_number = None
                                for content in deal.get("searchContent", []).split(" "):
                                    if content.startswith("7"):
                                        phone_number = content
                                        break

                                if phone_number == client["phone"]:
                                    deal_id = deal.get("id")
                                    break

                            if deal_id:
                                result = BitrixService.update_deal(
                                    deal_id,
                                    {
                                        "stageId": "C9:UC_0SQG1D",
                                        "ufCrm_1778046956": "1993",
                                    },
                                )

                                if deal["opportunity"] != order["sum"]:
                                    products = BitrixService.get_products(
                                        deal_id,
                                        all=True,
                                    )
                                    existing_products = [
                                        {"id": p["productId"], "price": p["price"]}
                                        for p in products
                                    ]

                                    BitrixService.add_products(
                                        deal_id,
                                        [
                                            {
                                                "id": ITGRIS_ITEM_ID,
                                                "price": order["sum"]
                                                - deal["opportunity"],
                                            },
                                            *existing_products,
                                        ],
                                    )

                                print(
                                    f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                                )
                            else:
                                print(
                                    f"Сделка Bitrix для клиента {client['phone']} не найдена"
                                )
                        except Exception as e:
                            explored_ids[status].remove(order["id"])
                            print(f"Ошибка при обработке сделки: {e}")
                elif status == AppointmentStatusEnum.RECEIPT:
                    orders = ItigrisService.get_orders(
                        token=itigris_token,
                        status="ORDER_COMPLETED",
                    )
                    print(
                        f"Получено заказов Itigris со статусом ORDER_COMPLETED: {len(orders or [])}"
                    )

                    if not orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": AppointmentStatusEnum.EXPECTATION.value,
                        }
                    )

                    for order in orders:
                        try:
                            if order["id"] in explored_ids[status]:
                                print(f"Заказ {order['id']} уже обработан, пропуск")
                                continue

                            explored_ids[status].append(order["id"])

                            client = ItigrisService.get_client_by_id(
                                token=itigris_token,
                                id=order.get("clientId"),
                            )

                            if not client:
                                continue

                            deal_id = None
                            for deal in deals:
                                phone_number = None
                                for content in deal.get("searchContent", []).split(" "):
                                    if content.startswith("7"):
                                        phone_number = content
                                        break

                                if phone_number == client["phone"]:
                                    deal_id = deal.get("id")
                                    break

                            if deal_id:
                                print(
                                    f"Найдена сделка Bitrix {deal_id} для клиента {client['phone']}, обновляем"
                                )

                                result = BitrixService.update_deal(
                                    deal_id,
                                    {
                                        "stageId": "C9:UC_3QNIAV",
                                        "ufCrm_1778057879": "1997",
                                    },
                                )

                                if deal["opportunity"] != order["sum"]:
                                    products = BitrixService.get_products(
                                        deal_id,
                                        all=True,
                                    )
                                    existing_products = [
                                        {"id": p["productId"], "price": p["price"]}
                                        for p in products
                                    ]

                                    BitrixService.add_products(
                                        deal_id,
                                        [
                                            {
                                                "id": ITGRIS_ITEM_ID,
                                                "price": order["sum"]
                                                - deal["opportunity"],
                                            },
                                            *existing_products,
                                        ],
                                    )

                                print(
                                    f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                                )
                            else:
                                print(
                                    f"Сделка Bitrix для клиента {client['phone']} не найдена"
                                )
                        except Exception as e:
                            explored_ids[status].remove(order["id"])
                            print(f"Ошибка при обработке сделки: {e}")

                time.sleep(5)
        except Exception as e:
            print(f"Критическая ошибка при обработке сделок: {e}")

    @classmethod
    def handle_service_deals(
        cls,
        statuses: list[ServiceStatusEnum],
        explored_ids: dict[str, list[int]],
    ) -> None:
        print(
            f"Начата обработка сделок услуг: statuses={statuses}, started_at={datetime.now().strftime('%Y-%m-%d %H;:%M:%S')})"
        )

        try:
            categories = BitrixService.get_categories(
                filters={
                    "entityTypeId": 2,
                }
            )

            category_id = None
            for category in categories:
                if category.get("name") == "Сервисный центр":
                    category_id = category.get("id")
                    break

            if not category_id:
                print("Категория 'Сервисный центр' не найдена")
                exit()

            itigris_token = ItigrisService.login(
                login=env_settings.ITIGRIS_SECRETARY_LOGIN,
                password=env_settings.ITIGRIS_SECRETARY_PASSWORD,
            )
            for status in statuses:
                if status == ServiceStatusEnum.REQUEST:
                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": ServiceStatusEnum.REQUEST.value,
                        }
                    )
                    print(f"Получены сделки для статуса '{status}': {len(deals)}")

                    for deal in deals:
                        try:
                            if deal["id"] in explored_ids[status]:
                                continue

                            explored_ids[status].append(deal["id"])

                            client = deal["contact"]
                            if not client:
                                print(f"Контакт для сделки {deal['id']} не найден")
                                continue

                            itigris_client = ItigrisService.get_client(
                                token=itigris_token,
                                phone=client.get("PHONE", [{}])[0].get("VALUE"),
                            )
                            if not itigris_client:
                                print(f"Клиент {client['PHONE']} не найден в Itigris")
                                continue

                            products = BitrixService.get_products(
                                deal.get("id"), all=True
                            )
                            departament = BitrixService.get_departament(
                                deal.get("ufCrm_1777383408")
                            )
                            price = deal.get("opportunity")

                            itigris_departaments = ItigrisService.get_departaments()

                            itigris_departament_id = None
                            for d in itigris_departaments:
                                if d.get("name") == departament["TITLE"]:
                                    itigris_departament_id = d.get("id")
                                    break

                            if not itigris_departament_id:
                                print(
                                    f"Отделение {departament['TITLE']} не найдено в Itigris"
                                )
                                continue

                            goods = []
                            for p in products:
                                try:
                                    full_p = BitrixService.get_product_by_id(
                                        p["productId"]
                                    )
                                except Exception as e:
                                    print(f"Ошибка при получении товара: {e}")
                                    goods.append(
                                        {
                                            "accessories": {
                                                "accessCategory": p.get("productName"),
                                                # "model": None,
                                            },
                                            "price": p.get("price"),
                                            "num": p.get("quantity"),
                                        }
                                    )
                                    continue

                                print(f"section: {full_p['iblockSectionId']}")
                                if full_p["iblockSectionId"] == 103:
                                    goods.append(
                                        {
                                            "contactlenses": {
                                                "manufacturer": (
                                                    full_p.get("property373") or {}
                                                ).get("value"),
                                                "name": (
                                                    full_p.get("property401") or {}
                                                ).get("value"),
                                                "color": None,
                                                "radiusOfCurvature": (
                                                    full_p.get("property403") or {}
                                                ).get("value"),
                                                "diameter": (
                                                    full_p.get("property383") or {}
                                                ).get("value"),
                                                "dioptre": (
                                                    full_p.get("property395") or {}
                                                ).get("value"),
                                                "cylinder": None,
                                                "axis": None,
                                                "addidation": None,
                                                "wearingPeriod": (
                                                    full_p.get("property407") or {}
                                                ).get("value"),
                                                "packageNum": (
                                                    full_p.get("property409") or {}
                                                ).get("value"),
                                            },
                                            "price": p.get("price"),
                                            "num": p.get("quantity"),
                                        }
                                    )
                                elif full_p["iblockSectionId"] == 105:
                                    goods.append(
                                        {
                                            "glasses": {
                                                "manufacturer": (
                                                    full_p.get("property373") or {}
                                                ).get("value"),
                                                "brand": (
                                                    full_p.get("property375") or {}
                                                ).get("value"),
                                                "model": (
                                                    full_p.get("property371") or {}
                                                ).get("value"),
                                                "color": (
                                                    full_p.get("property381") or {}
                                                ).get("value"),
                                                "targetGroup": (
                                                    full_p.get("property411") or {}
                                                ).get("value"),
                                                "material": (
                                                    full_p.get("property385") or {}
                                                ).get("value"),
                                                "type": (
                                                    full_p.get("property413") or {}
                                                ).get("value"),
                                                "size": (
                                                    full_p.get("property415") or {}
                                                ).get("value"),
                                            },
                                            "price": p.get("price"),
                                            "num": p.get("quantity"),
                                        }
                                    )
                                elif full_p["iblockSectionId"] == 107:
                                    goods.append(
                                        {
                                            "lenses": {
                                                "manufacturer": (
                                                    full_p.get("property373") or {}
                                                ).get("value"),
                                                "brand": (
                                                    full_p.get("property375") or {}
                                                ).get("value"),
                                                "refractionIndex": (
                                                    full_p.get("property377") or {}
                                                ).get("value"),
                                                "cover": (
                                                    full_p.get("property379") or {}
                                                ).get("value"),
                                                "color": (
                                                    full_p.get("property381") or {}
                                                ).get("value"),
                                                "diameter": (
                                                    full_p.get("property383") or {}
                                                ).get("value"),
                                                "material": (
                                                    full_p.get("property385") or {}
                                                ).get("value"),
                                                "geometry": (
                                                    full_p.get("property387") or {}
                                                ).get("value"),
                                                "dioptre": (
                                                    full_p.get("property395") or {}
                                                ).get("value"),
                                                "cylinderDioptre": None,
                                                "addidation": None,
                                                "type": (
                                                    full_p.get("property389") or {}
                                                ).get("value"),
                                                "lensClass": (
                                                    full_p.get("property391") or {}
                                                ).get("value"),
                                                "technology": None,
                                            },
                                            "price": p.get("price"),
                                            "num": p.get("quantity"),
                                        }
                                    )
                                elif full_p["iblockSectionId"] == 109:
                                    goods.append(
                                        {
                                            "sunglasses": {
                                                "manufacturer": (
                                                    full_p.get("property373") or {}
                                                ).get("value"),
                                                "brand": (
                                                    full_p.get("property375") or {}
                                                ).get("value"),
                                                "model": (
                                                    full_p.get("property371") or {}
                                                ).get("value"),
                                                "color": (
                                                    full_p.get("property381") or {}
                                                ).get("value"),
                                                "targetGroup": (
                                                    full_p.get("property411") or {}
                                                ).get("value"),
                                                "material": (
                                                    full_p.get("property385") or {}
                                                ).get("value"),
                                                "frameType": (
                                                    full_p.get("property413") or {}
                                                ).get("value"),
                                                "lensesType": (
                                                    full_p.get("property415") or {}
                                                ).get("value"),
                                            },
                                            "price": p.get("price"),
                                            "num": p.get("quantity"),
                                        }
                                    )

                            ItigrisService.create_order(
                                client_id=itigris_client["id"],
                                departament_id=itigris_departament_id,
                                goods=goods,
                                price=price,
                            )

                            print("Заказ создан в системе Itigris")
                            BitrixService.add_log(
                                deal["id"],
                                "Заказ создан в системе Itigris",
                                "Заказ создан в системе Itigris",
                            )
                        except Exception as e:
                            print(
                                f"Ошибка при создании заказа для сделки {deal['id']}: {e}"
                            )
                            explored_ids[status].remove(deal["id"])
                            BitrixService.add_log(
                                deal["id"],
                                "Ошибка при создании заказа для системы Itigris",
                                f"Ошибка при создании заказа для сделки {deal['id']} для системы Itigris: {e}",
                            )
                elif status == ServiceStatusEnum.ACCEPTED:
                    orders = ItigrisService.get_orders(
                        token=itigris_token,
                        status="ACCEPTED",
                    )
                    print(
                        f"Получено заказов Itigris со статусом ACCEPTED: {len(orders or [])}"
                    )

                    if not orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": ServiceStatusEnum.REQUEST.value,
                        }
                    )

                    for order in orders:
                        try:
                            if order["id"] in explored_ids[status]:
                                continue

                            explored_ids[status].append(order["id"])

                            client = ItigrisService.get_client_by_id(
                                token=itigris_token,
                                id=order.get("clientId"),
                            )
                            if not client:
                                print(
                                    f"Клиент {order.get('clientId')} не найден в Itigris"
                                )
                                continue

                            deal_id = None
                            for deal in deals:
                                phone_number = (
                                    deal["contact"].get("PHONE", [{}])[0].get("VALUE"),
                                )[0].replace("+", "")
                                print(phone_number, client["phone"])
                                if phone_number == client["phone"]:
                                    deal_id = deal.get("id")
                                    break

                            if not deal_id:
                                print(
                                    f"Сделка для клиента {client['phone']} не найдена"
                                )
                                continue

                            result = BitrixService.update_deal(
                                deal_id,
                                {
                                    "stageId": "C11:PREPARATION",
                                },
                            )

                            if deal["opportunity"] != order["sum"]:
                                products = BitrixService.get_products(
                                    deal_id,
                                    all=True,
                                )
                                existing_products = [
                                    {"id": p["productId"], "price": p["price"]}
                                    for p in products
                                ]

                                BitrixService.add_products(
                                    deal_id,
                                    [
                                        {
                                            "id": ITGRIS_ITEM_ID,
                                            "price": order["sum"] - deal["opportunity"],
                                        },
                                        *existing_products,
                                    ],
                                )

                            print(
                                f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                            )
                        except Exception as e:
                            explored_ids[status].remove(order["id"])
                            print(f"Ошибка при обработке сделки: {e}")
                elif status == ServiceStatusEnum.MANUFACTURE:
                    orders = ItigrisService.get_orders(
                        token=itigris_token,
                        status="IN_WORK",
                    )
                    print(
                        f"Получено заказов Itigris со статусом IN_WORK: {len(orders or [])}"
                    )

                    if not orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": ServiceStatusEnum.ACCEPTED.value,
                        }
                    )

                    for order in orders:
                        if order["id"] in explored_ids[status]:
                            continue

                        explored_ids[status].append(order["id"])

                        client = ItigrisService.get_client_by_id(
                            token=itigris_token,
                            id=order.get("clientId"),
                        )
                        if not client:
                            print(f"Клиент {order.get('clientId')} не найден в Itigris")
                            continue

                        deal_id = None
                        for deal in deals:
                            phone_number = (
                                deal["contact"].get("PHONE", [{}])[0].get("VALUE"),
                            )[0].replace("+", "")
                            if phone_number == client["phone"]:
                                deal_id = deal.get("id")
                                break

                        if not deal_id:
                            print(f"Сделка для клиента {client['phone']} не найдена")
                            continue

                        result = BitrixService.update_deal(
                            deal_id,
                            {
                                "stageId": "C11:PREPAYMENT_INVOIC",
                            },
                        )

                        if deal["opportunity"] != order["sum"]:
                            products = BitrixService.get_products(
                                deal_id,
                                all=True,
                            )
                            existing_products = [
                                {"id": p["productId"], "price": p["price"]}
                                for p in products
                            ]

                            BitrixService.add_products(
                                deal_id,
                                [
                                    {
                                        "id": ITGRIS_ITEM_ID,
                                        "price": order["sum"] - deal["opportunity"],
                                    },
                                    *existing_products,
                                ],
                            )

                        print(
                            f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                        )
                elif status == ServiceStatusEnum.DELIVERY:
                    orders = ItigrisService.get_orders(
                        token=itigris_token,
                        status="ORDER_READY",
                    )
                    print(
                        f"Получено заказов Itigris со статусом ORDER_READY: {len(orders or [])}"
                    )

                    if not orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": ServiceStatusEnum.MANUFACTURE.value,
                        }
                    )

                    for order in orders:
                        try:
                            if order["id"] in explored_ids[status]:
                                continue

                            explored_ids[status].append(order["id"])

                            client = ItigrisService.get_client_by_id(
                                token=itigris_token,
                                id=order.get("clientId"),
                            )
                            if not client:
                                print(
                                    f"Клиент {order.get('clientId')} не найден в Itigris"
                                )
                                continue

                            deal_id = None
                            for deal in deals:
                                phone_number = (
                                    deal["contact"].get("PHONE", [{}])[0].get("VALUE"),
                                )[0].replace("+", "")
                                print(phone_number, client["phone"])
                                if phone_number == client["phone"]:
                                    deal_id = deal.get("id")
                                    break

                            if not deal_id:
                                print(
                                    f"Сделка для клиента {client['phone']} не найдена"
                                )
                                continue

                            result = BitrixService.update_deal(
                                deal_id,
                                {
                                    "stageId": "C11:EXECUTING",
                                    "ufCrm_1778046956": "1993",
                                },
                            )

                            if deal["opportunity"] != order["sum"]:
                                products = BitrixService.get_products(
                                    deal_id,
                                    all=True,
                                )
                                existing_products = [
                                    {"id": p["productId"], "price": p["price"]}
                                    for p in products
                                ]

                                BitrixService.add_products(
                                    deal_id,
                                    [
                                        {
                                            "id": ITGRIS_ITEM_ID,
                                            "price": order["sum"] - deal["opportunity"],
                                        },
                                        *existing_products,
                                    ],
                                )

                            print(
                                f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                            )
                        except Exception as e:
                            explored_ids[status].remove(order["id"])
                            print(f"Ошибка при обработке сделки: {e}")
                elif status == ServiceStatusEnum.COMPLETED:
                    orders = ItigrisService.get_orders(
                        token=itigris_token,
                        status="ORDER_COMPLETED",
                    )
                    print(
                        f"Получено заказов Itigris со статусом ORDER_COMPLETED: {len(orders or [])}"
                    )

                    if not orders:
                        print(f"Нет заказов для обработки в статусе '{status}'")
                        continue

                    deals = BitrixService.get_deals(
                        filters={
                            "categoryId": category_id,
                            "%searchContent": ServiceStatusEnum.DELIVERY.value,
                        }
                    )

                    for order in orders:
                        try:
                            if order["id"] in explored_ids[status]:
                                continue

                            explored_ids[status].append(order["id"])

                            client = ItigrisService.get_client_by_id(
                                token=itigris_token,
                                id=order.get("clientId"),
                            )
                            if not client:
                                print(
                                    f"Клиент {order.get('clientId')} не найден в Itigris"
                                )
                                continue

                            deal_id = None
                            for deal in deals:
                                phone_number = (
                                    deal["contact"].get("PHONE", [{}])[0].get("VALUE"),
                                )[0].replace("+", "")
                                if phone_number == client["phone"]:
                                    deal_id = deal.get("id")
                                    break

                            if not deal_id:
                                print(
                                    f"Сделка для клиента {client['phone']} не найдена"
                                )
                                continue

                            result = BitrixService.update_deal(
                                deal_id,
                                {
                                    "ufCrm_1778057879": "1997",
                                },
                            )

                            if deal["opportunity"] != order["sum"]:
                                products = BitrixService.get_products(
                                    deal_id,
                                    all=True,
                                )
                                existing_products = [
                                    {"id": p["productId"], "price": p["price"]}
                                    for p in products
                                ]

                                BitrixService.add_products(
                                    deal_id,
                                    [
                                        {
                                            "id": ITGRIS_ITEM_ID,
                                            "price": order["sum"] - deal["opportunity"],
                                        },
                                        *existing_products,
                                    ],
                                )

                            print(
                                f"Результат обновления сделки {deal_id}: {json.dumps(result, indent=4, ensure_ascii=False)}"
                            )
                        except Exception as e:
                            explored_ids[status].remove(order["id"])
                            print(f"Ошибка при обработке сделки: {e}")

                time.sleep(5)
        except Exception as e:
            print(f"Критическая ошибка при обработке сделок услуг: {e}")
