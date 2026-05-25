Переменные окружения (указаны в .env.example файле):
```
ITIGRIS_COMPANY - компания в Itigris
ITIGRIS_LOGIN - логин в Itigris
ITIGRIS_PASSWORD - пароль в Itigris
ITIGRIS_DEPARTAMENT_ID - ID отделения в Itigris
ITIGRIS_KEY - ключ для работы с Itigris
ITIGRIS_USER_ID - ID пользователя в Itigris
ITIGRIS_SERVICE_TYPE_ID - ID типа услуги в Itigris
ITIGRIS_SECRETARY_LOGIN - логин секретаря в Itigris
ITIGRIS_SECRETARY_PASSWORD - пароль секретаря в Itigris
ITIGRIS_ADMINISTRATOR_LOGIN - логин администратора в Itigris
ITIGRIS_ADMINISTRATOR_PASSWORD - пароль администратора в Itigris    

BITRIX_WEBHOOK_URL - URL вебхука Bitrix24

MEDODS_IDENTITY_KEY - ключ для работы с Medods
MEDODS_SECRET_KEY - секретный ключ для работы с Medods
MEDODS_LOGIN - логин в Medods
MEDODS_PASSWORD - пароль в Medods
`````

Запуск приложения (необходимо иметь установленный Python):
- Задать переменные окружения в .env файле
- Создать виртуальное окруение и активировать его (по желанию):
```
python -m venv venv
source venv/bin/activate
```
- Установить зависимости:
```
pip install .
```
- Запустить приложение:
```
python -m src.main
```

Структура проекта:
```
src/
├── services/
│   ├── bitrix.py - сервис для работы с Bitrix24
│   ├── integration.py - сервис для интеграции с Itigris, Medods и Bitrix24
│   └── itigris.py - сервис для работы с Itigris
│   └── medods.py - сервис для работы с Medods
│   └── parser.py - сервис для работы с парсером
├── constants.py - константы
├── env.py - переменные окружения
└── main.py - файл входа приложения
```
