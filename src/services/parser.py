import re
import time
from datetime import datetime, timedelta, timezone
from typing import Generator

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from src.constants import MEDODS_RECEIPT_URL, MEDODS_WEBSITE_URL
from src.env import env_settings


class ParserService:
    _driver: WebDriver | None = None

    @staticmethod
    def _get_driver() -> WebDriver:
        options = ChromeOptions()
        chrome_arguments = [
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]

        if env_settings.IS_LINUX_SERVER:
            chrome_arguments.extend(
                (
                    "--headless=new",
                    "--window-size=1920,1080",
                )
            )
        else:
            chrome_arguments.append("--start-maximized")

        for argument in chrome_arguments:
            options.add_argument(argument)

        driver = webdriver.Chrome(options=options)
        if not env_settings.IS_LINUX_SERVER:
            driver.maximize_window()
        return driver

    @classmethod
    def get_driver(cls) -> WebDriver:
        if cls._driver is not None and cls._is_driver_active(cls._driver):
            return cls._driver

        if cls._driver is not None:
            cls.close_driver(cls._driver)

        cls._driver = cls._get_driver()

        return cls._driver

    @staticmethod
    def _is_driver_active(driver: WebDriver | None) -> bool:
        if driver is None:
            return False

        try:
            # Any remote command is enough to verify that chromedriver session is alive.
            _ = driver.current_url
            return True
        except Exception:
            return False

    @staticmethod
    def _get_visible_element(driver: WebDriver, by: str, value: str):
        elements = driver.find_elements(by, value)
        for element in elements:
            if element.is_displayed() and element.is_enabled():
                return element
        return None

    @staticmethod
    def _clean_field_value(raw_text: str) -> str:
        value = raw_text
        if ":" in raw_text:
            value = raw_text.split(":", 1)[1]

        value = value.replace("_", " ").replace("\xa0", " ")
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _parse_documents_table(cls, documents_table) -> list[dict]:
        parsed_rows: list[dict] = []
        for row in documents_table.find_elements(
            By.CSS_SELECTOR, "tbody tr.clickable-row"
        ):
            cells = row.find_elements(By.CSS_SELECTOR, "td")
            if len(cells) < 4:
                continue

            parsed_rows.append(
                {
                    "id": row.get_attribute("data-id"),
                    "href": row.get_attribute("data-href"),
                    "name": cells[1].text.strip(),
                    "number": cells[2].text.strip(),
                    "date": cells[3].text.strip(),
                }
            )

        return parsed_rows

    @classmethod
    def _parse_prescription_table(cls, driver: WebDriver) -> list[dict]:
        candidate_tables = driver.find_elements(
            By.XPATH,
            (
                "//table["
                ".//*[self::td or self::th][contains(normalize-space(.), 'Правый')]"
                " and "
                ".//*[self::td or self::th][contains(normalize-space(.), 'Левый')]"
                "]"
            ),
        )

        for table in candidate_tables:
            rows = table.find_elements(By.CSS_SELECTOR, "tr")
            raw_matrix: list[list[str]] = []
            for row in rows:
                cols = row.find_elements(By.CSS_SELECTOR, "th, td")
                parsed_cells = []
                for col in cols:
                    cell_text = col.get_attribute("innerText") or col.text
                    parsed_cells.append(re.sub(r"\s+", " ", cell_text).strip())
                raw_matrix.append(parsed_cells)

            if not raw_matrix:
                continue

            flat_text = " ".join(" ".join(row) for row in raw_matrix)
            if "Правый" not in flat_text or "Левый" not in flat_text:
                continue

            headers = raw_matrix[0]
            data_rows = []
            for raw_row in raw_matrix[1:]:
                if not any(raw_row):
                    continue

                parsed_row = {"Глаз": raw_row[0] if raw_row else ""}
                for idx in range(1, len(raw_row)):
                    header = headers[idx] if idx < len(headers) else f"col_{idx}"
                    parsed_row[header or f"col_{idx}"] = raw_row[idx]
                data_rows.append(parsed_row)

            return data_rows

        raise RuntimeError("Не удалось найти таблицу рецепта (Правый/Левый)")

    @staticmethod
    def _normalize_header_key(value: str) -> str:
        normalized = value.strip().lower().replace(" ", "")
        normalized = normalized.replace("о", "o")
        return normalized

    @classmethod
    def _extract_centering_distance(cls, driver: WebDriver) -> dict:
        candidate_tables = driver.find_elements(
            By.XPATH,
            "//table[.//td[contains(normalize-space(.), 'Центровое расстояние')]]",
        )
        if not candidate_tables:
            raise RuntimeError("Не найдена таблица с 'Центровое расстояние'")

        for table in candidate_tables:
            rows = table.find_elements(By.CSS_SELECTOR, "tr")
            raw_matrix: list[list[str]] = []
            for row in rows:
                cols = row.find_elements(By.CSS_SELECTOR, "th, td")
                parsed_cells = []
                for col in cols:
                    cell_text = col.get_attribute("innerText") or col.text
                    parsed_cells.append(re.sub(r"\s+", " ", cell_text).strip())
                raw_matrix.append(parsed_cells)

            if len(raw_matrix) < 2:
                continue

            headers = raw_matrix[0]
            center_row = None
            for row in raw_matrix[1:]:
                if row and "центровое расстояние" in row[0].strip().lower():
                    center_row = row
                    break

            if center_row is None:
                continue

            result = {"OU": "", "Правый": "", "Левый": ""}
            for idx in range(1, len(center_row)):
                header = headers[idx] if idx < len(headers) else f"col_{idx}"
                normalized_key = cls._normalize_header_key(header)
                value = center_row[idx]

                if normalized_key in ("ou", "оu"):
                    result["OU"] = value
                elif normalized_key == "Правый":
                    result["Правый"] = value
                elif normalized_key == "Левый":
                    result["Левый"] = value

            # Fallback by position for documents with unstable headers.
            if not result["OU"] and len(center_row) > 1:
                result["OU"] = center_row[1]
            if not result["Правый"] and len(center_row) > 2:
                result["Правый"] = center_row[2]
            if not result["Левый"] and len(center_row) > 3:
                result["Левый"] = center_row[3]

            return result

        raise RuntimeError("Не удалось извлечь OU/Правый/Левый из таблицы центровки")

    @staticmethod
    def _switch_to_login_mode(driver: WebDriver, wait: WebDriverWait) -> None:
        switch_on_selector = "input#switch-on.switcher"
        switch_on = wait.until(
            ec.presence_of_element_located((By.CSS_SELECTOR, switch_on_selector))
        )
        if switch_on.is_selected():
            return

        click_selectors = (
            "div.switch label:nth-of-type(2)",
            "div.switch span.toggle",
            switch_on_selector,
        )
        for selector in click_selectors:
            try:
                candidate = wait.until(
                    ec.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", candidate
                )
                try:
                    candidate.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", candidate)

                if switch_on.is_selected():
                    return
            except Exception:
                continue

        driver.execute_script(
            """
            const element = document.querySelector(arguments[0]);
            if (!element) return;
            element.checked = true;
            element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.dispatchEvent(new Event('input', { bubbles: true }));
            """,
            switch_on_selector,
        )
        wait.until(lambda _: switch_on.is_selected())

    @classmethod
    def login(cls, driver: WebDriver) -> None:
        driver.get(MEDODS_WEBSITE_URL)
        wait = WebDriverWait(driver, 20)

        cls._switch_to_login_mode(driver, wait)

        username_input = wait.until(
            lambda d: cls._get_visible_element(
                d, By.CSS_SELECTOR, "input#user_username"
            )
        )
        username_input.clear()
        username_input.send_keys(env_settings.MEDODS_LOGIN)

        password_input = wait.until(
            lambda d: cls._get_visible_element(
                d, By.CSS_SELECTOR, "input#user_password"
            )
        )
        password_input.clear()
        password_input.send_keys(env_settings.MEDODS_PASSWORD)

        submit_button = wait.until(
            ec.element_to_be_clickable(
                (By.CSS_SELECTOR, "button.btn.btn-primary[type='submit']")
            )
        )
        submit_button.click()

    @classmethod
    def close_driver(cls, driver: WebDriver) -> None:
        if driver is None:
            return

        try:
            driver.quit()
        except Exception:
            pass
        finally:
            if driver is cls._driver:
                cls._driver = None

    @classmethod
    def initialize(cls) -> Generator[WebDriver, None, None]:
        driver = None
        try:
            driver = cls.get_driver()
            cls.login(driver)
            yield driver
        finally:
            cls.close_driver(driver)

    @classmethod
    def parse_receipt(cls, driver: WebDriver, order: dict) -> str | None:
        """
        Парсинг чека заказа.

        Пример order:
         {
            "id": 4438,
            "createdById": 51,
            "clientId": 2581,
            "customerId": 2581,
            "customerType": "client",
            "orderPaidStatus": "not_paid",
            "sum": 1500,
            "clinicId": 1,
            "finalSum": 1500,
            "discountSum": 0,
            "unpaidSum": 1500,
            "date": "2026-04-30",
            "deletedAt": None
         }
        """

        try:
            order_url = MEDODS_RECEIPT_URL.format(order_id=order["id"])
            wait = WebDriverWait(driver, 20)

            navigation_error = None
            for _ in range(4):
                try:
                    driver.get(order_url)
                    wait.until(
                        lambda d: d.execute_script("return document.readyState")
                        in ("interactive", "complete")
                    )

                    if "users/sign_in" in driver.current_url:
                        cls.login(driver)
                        driver.get(order_url)
                        wait.until(
                            lambda d: d.execute_script("return document.readyState")
                            in ("interactive", "complete")
                        )

                    if f"/orders/{order['id']}" not in driver.current_url:
                        raise RuntimeError(
                            f"После перехода открыт другой URL: {driver.current_url}"
                        )

                    wait.until(
                        ec.presence_of_element_located(
                            (By.CSS_SELECTOR, "button#orders_for_print")
                        )
                    )
                    navigation_error = None
                    break
                except Exception as e:
                    navigation_error = e
                    time.sleep(1)

            if navigation_error is not None:
                print(
                    f"Ошибка при получении чека: {navigation_error}. target_url={order_url}, current_url={driver.current_url}"
                )
                return

            open_docs_error = None
            documents_table = None
            for _ in range(4):
                try:
                    actions_button = wait.until(
                        ec.element_to_be_clickable(
                            (By.CSS_SELECTOR, "button#orders_for_print")
                        )
                    )
                    try:
                        actions_button.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", actions_button)

                    client_documents_button = wait.until(
                        ec.element_to_be_clickable(
                            (By.CSS_SELECTOR, "a#client_documents_btn")
                        )
                    )
                    try:
                        client_documents_button.click()
                    except ElementClickInterceptedException:
                        driver.execute_script(
                            "arguments[0].click();", client_documents_button
                        )

                    documents_table = wait.until(
                        ec.presence_of_element_located(
                            (By.CSS_SELECTOR, "table#documents_list")
                        )
                    )
                    open_docs_error = None
                    break
                except Exception as e:
                    open_docs_error = e
                    # On flaky redirects, force-open order page again and retry.
                    driver.get(order_url)
                    time.sleep(1)

            if open_docs_error is not None or documents_table is None:
                print(
                    f"Ошибка при открытии документов пациента: {open_docs_error}. current_url={driver.current_url}"
                )
                return
            parsed_documents = cls._parse_documents_table(documents_table)
            if not parsed_documents:
                raise RuntimeError(
                    "Не найдено ни одного документа в таблице документов"
                )

            first_document = documents_table.find_elements(
                By.CSS_SELECTOR, "tbody tr.clickable-row"
            )[0]
            try:
                first_document.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", first_document)
            wait.until(
                ec.presence_of_element_located(
                    (
                        By.XPATH,
                        "//span[contains(normalize-space(.), 'Назначение рецепта')]",
                    )
                )
            )

            prescription_table = cls._parse_prescription_table(driver)
            centering_distance = cls._extract_centering_distance(driver)
            assignment_text = wait.until(
                ec.presence_of_element_located(
                    (
                        By.XPATH,
                        "//span[contains(normalize-space(.), 'Назначение рецепта')]",
                    )
                )
            ).text
            notes_text = wait.until(
                ec.presence_of_element_located(
                    (By.XPATH, "//span[contains(normalize-space(.), 'Примечания')]")
                )
            ).text
            device_name_text = wait.until(
                ec.presence_of_element_located(
                    (
                        By.XPATH,
                        "//span[contains(normalize-space(.), 'Наименование медицинского изделия')]",
                    )
                )
            ).text

            recipe_rows: list[str] = []
            for row in prescription_table:
                label = row.get("Глаз", "")
                field_parts = [
                    f"{key}={value}" for key, value in row.items() if key != "Глаз"
                ]
                recipe_rows.append(
                    f"\t{label}: {', '.join(field_parts)}"
                    if field_parts
                    else f"{label}: Нет данных"
                )

            recipe_text = "\n".join(recipe_rows) if recipe_rows else "Нет данных"
            return (
                f"{(datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M')}\n"
                f"Рецепт:\n{recipe_text}\n"
                "Центровое расстояние:\n"
                f"\tOU: {centering_distance.get('OU', '')}\n"
                f"\tПравый: {centering_distance.get('Правый', '')}\n"
                f"\tЛевый: {centering_distance.get('Левый', '')}\n"
                f"Назначение рецепта: {cls._clean_field_value(assignment_text)}\n"
                f"Примечания: {cls._clean_field_value(notes_text)}\n"
                "Наименование медицинского изделия: "
                f"{cls._clean_field_value(device_name_text).replace('Наименование медицинского изделия', '').strip()}"
            )

        except Exception as e:
            print(f"Ошибка при парсинге чека: {e}")
