# Local Steam Downloader

Кроссплатформенная утилита для скачивания коллекций и отдельных модов Steam Workshop.

- Windows 10/11 и Linux.
- CLI и простое окно на Tkinter.
- Метаданные — через Steam Web API, файлы — через официальный SteamCMD.
- Выборочная загрузка, resume по манифесту, человекочитаемые имена папок.
- Оба режима входа: анонимный и под аккаунтом Steam.

> Скачивание возможно только для контента, к которому у аккаунта есть доступ.
> Проект не обходит приватность, платные моды и ограничения Steam.

## Установка

Требуется Python 3.11+ и установленный [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD).

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Использование

```bash
# посмотреть состав коллекции
steam-workshop-dl "https://steamcommunity.com/sharedfiles/filedetails/?id=123456789" --list

# скачать коллекцию анонимно
steam-workshop-dl 123456789 --type collection -o ~/Downloads/workshop --anonymous

# скачать один мод
steam-workshop-dl 123456789 --type mod -o ~/Downloads/workshop

# графический интерфейс
steam-workshop-dl --gui
```

Полный список флагов: `steam-workshop-dl --help`.

## Статус

Проект в разработке. Готовы метаданные, разбор коллекций, CLI-предпросмотр и базовая загрузка.
GUI, интерактивный вход и расширенная надёжность — следующие этапы.

## Структура

```
steam_workshop_dl/
├── core/       # модели, события, ошибки, имена, обход дерева
├── services/   # конфиг, логи, манифест, Web API, SteamCMD, авторизация
├── app/        # resolver и оркестрация загрузки
└── ui/         # CLI и GUI
```
