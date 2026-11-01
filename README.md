# Local Steam Downloader

Download Steam Workshop collections and individual mods through the official SteamCMD.

[**⬇ Download for Windows 10/11**](https://github.com/mimore18/Local_Steam_Downloader/releases/latest/download/steam-workshop-dl-windows-x64.zip)

[English](#english) · [Русский](#русский) · [Releases](https://github.com/mimore18/Local_Steam_Downloader/releases) · [GitHub](https://github.com/mimore18/Local_Steam_Downloader)

---

## English

### What it is

A simple Steam Workshop downloader with a GUI and a CLI:

- Windows 10/11 and Linux;
- collections and single mods;
- checkbox selection for individual mods;
- anonymous login or a Steam account with Steam Guard;
- automatic SteamCMD setup on first use;
- parallel downloads (1–4 threads) with an optional one-SteamCMD-per-mod mode;
- resume, file validation and optional ZIP packaging.

> Only content available to the signed-in account can be downloaded.
> This project does not bypass Steam privacy or access restrictions.

### Screenshot

Dark theme:

![Main window in the dark theme](https://raw.githubusercontent.com/mimore18/Local_Steam_Downloader/main/docs/screenshots/main-en-dark.png)

### Download a ready build

The easiest way is to grab a ready archive from the
[Releases](https://github.com/mimore18/Local_Steam_Downloader/releases/latest) page:

| System | File | Contents |
|---|---|---|
| Windows 10/11 | [`steam-workshop-dl-windows-x64.zip`](https://github.com/mimore18/Local_Steam_Downloader/releases/latest/download/steam-workshop-dl-windows-x64.zip) | `steam-workshop-dl.exe` (CLI) and `steam-workshop-dl-gui.exe` (GUI), built with PyInstaller |
| Linux | [`steam-workshop-dl-linux-source.tar.gz`](https://github.com/mimore18/Local_Steam_Downloader/releases/latest/download/steam-workshop-dl-linux-source.tar.gz) | Python source code (`.py`) |

**Windows.** Unzip the archive and run the `.exe` you need. Python and package
installation are not required. Windows may show a SmartScreen warning — this is
normal for an unsigned exe; choose “More info → Run anyway”.

**Linux.** Extract the archive, install Python 3.11+, and run:

```bash
tar -xzf steam-workshop-dl-linux-source.tar.gz
cd steam-workshop-dl
python3 run_gui.py      # graphical interface
python3 run_cli.py      # command line / wizard
```

Installing from source manually is described below.

### Installation

Python 3.11 or newer is required.

From the project folder:

```bash
python -m pip install -e .
```

On Linux you may need `python3`; on Windows use `py` if `python` is not found.

### Start with the GUI

```bash
python run_gui.py
```

After installing the package:

```bash
steam-workshop-dl-gui
```

How to use it:

1. Choose the target type: **Collection** or **Mod**.
2. Paste a link or ID and choose the download folder.
3. Click **“Load mod list”**.
4. Clear the checkboxes for mods you do not need.
5. Click **“Download selected mods”**.

The **“Settings…”** button contains:

- **Interface language** — English / Русский;
- **Theme** — Light / Dark;
- Steam authorization;
- SteamCMD path;
- download options (resume, validate, ZIP).

Other buttons:

- **“Retry failed”** — retry only failed or canceled downloads;
- **“Select all” / “Clear selection”** — manage checkboxes;
- **“Stop download”** — cancel the current operation.

Drag the divider between the mod list and the log to make the list smaller.
The GitHub link stays visible when the window is resized.

### Start the CLI without arguments

```bash
python run_cli.py
```

After installing the package:

```bash
steam-workshop-dl
```

The wizard asks for:

1. the target type (collection or mod);
2. a link or ID;
3. the download folder;
4. then shows the mod list;
5. and asks for `y/n` confirmation.

Defaults: collection, `~/Downloads/workshop`, confirmation “no”,
anonymous login.

### CLI options

Main options:

| Option | Description |
|---|---|
| `URL_OR_ID` | collection/mod link or ID |
| `--type collection` | target is a collection |
| `--type mod` | target is a single mod |
| `-o, --output DIR` | download folder |
| `--list` | show the mod list and exit |
| `--dry-run` | show the plan without downloading |
| `--only ID,ID` | download only these IDs |
| `--exclude ID,ID` | exclude these IDs |
| `--login USER` | sign in with a Steam account |
| `--anonymous` | use anonymous login |
| `--steamcmd PATH` | custom SteamCMD path |
| `--no-steamcmd-bootstrap` | do not download SteamCMD automatically |
| `--validate` | validate files after download |
| `--zip` | pack each mod into a ZIP |

Additional options:

| Option | Description |
|---|---|
| `--no-resume` | do not resume; download again |
| `--force` | ignore the manifest |
| `--retries N` | number of retries on errors |
| `--jobs N` | metadata worker threads |
| `--timeout SEC` | request timeout |
| `--by-app` | group by application folders |
| `--flat` | no nested folders |
| `--config FILE` | custom `config.toml` |
| `--log-file FILE` | write the log to a file |
| `-v, --verbose` | verbose output |
| `--gui` | open the GUI |
| `--version` | show the version |

Full help:

```bash
python run_cli.py --help
```

### Examples

```bash
# show a collection's contents
python run_cli.py "https://steamcommunity.com/sharedfiles/filedetails/?id=123456789" --list

# download a collection
python run_cli.py 123456789 --type collection -o ~/Downloads/workshop

# download a single mod
python run_cli.py 123456789 --type mod

# download only two mods from a collection
python run_cli.py 123456789 --type collection --only 111,222

# sign in with a Steam account
python run_cli.py 123456789 --login MY_LOGIN
```

### Interface language

In the GUI open **“Settings…” → “Interface” → “Interface language”**.

- Available languages: **English** and **Русский**.
- The default is the primary language of the operating system.
- The choice is remembered in `gui.json` and restored on the next launch.
- Error dialogs and log messages are translated too.

### Theme

In the GUI open **“Settings…” → “Interface” → “Theme”**.

- Available themes: **Light** and **Dark**.
- The dark theme recolours the window, mod list, log and dialogs.
- The choice is stored in `gui.json` and restored on the next launch.

### Parallel downloads

In the GUI open **“Settings…” → “Download options”**.

- **Download threads**: `1` runs one sequential SteamCMD batch; `2–4` start
  several SteamCMD processes in parallel. Each thread logs in once and then
  downloads its balanced share of the selected mods sequentially.
- **Unstable mode** adds **One per mod** to the selector and starts a separate
  SteamCMD process for every selected mod. This has the highest startup and
  login overhead and is usually slower than 1–4 threads.
- Parallel mode may hit Steam rate limits or overload the computer. Start with
  2 threads if you are unsure; use 1 if parallelism makes downloads slower.

### SteamCMD

You do not need to install SteamCMD manually. If it is missing, the app downloads
the official Valve archive and extracts it:

- into `steamcmd/` next to the project when running from source;
- into the user data folder when running an installed command.

You can set a custom path in the GUI settings or with `--steamcmd`.
To disable automatic download, use `--no-steamcmd-bootstrap` or clear the
corresponding checkbox in the settings.

### Requirements and limitations

- Access to Steam Workshop and Valve servers is required.
- Paid or private mods need an account with access.
- SteamCMD downloads files sequentially, so large collections take time.
  Raise the number of download threads to 2–4 if your connection allows it.

---

---

## Русский

### Что это

Простая утилита с графическим интерфейсом и командной строкой:

- Windows 10/11 и Linux;
- коллекции и одиночные моды;
- выбор нужных модов галочками;
- анонимный вход или аккаунт Steam со Steam Guard;
- автоматическая установка SteamCMD при первом запуске;
- параллельная загрузка (1–4 потока) и необязательный режим «каждый мод в своём SteamCMD»;
- докачка, проверка файлов и упаковка в ZIP.

> Скачивается только тот контент, к которому у аккаунта есть доступ.
> Проект не обходит приватность и ограничения Steam.

### Скриншот

Тёмная тема:

![Главное окно в тёмной теме](https://raw.githubusercontent.com/mimore18/Local_Steam_Downloader/main/docs/screenshots/main-en-dark.png)

### Скачивание готовой сборки

Самый простой способ — взять готовый архив со страницы
[Releases](https://github.com/mimore18/Local_Steam_Downloader/releases/latest):

| Система | Файл | Что внутри |
|---|---|---|
| Windows 10/11 | [`steam-workshop-dl-windows-x64.zip`](https://github.com/mimore18/Local_Steam_Downloader/releases/latest/download/steam-workshop-dl-windows-x64.zip) | `steam-workshop-dl.exe` (CLI) и `steam-workshop-dl-gui.exe` (GUI), собранные PyInstaller |
| Linux | [`steam-workshop-dl-linux-source.tar.gz`](https://github.com/mimore18/Local_Steam_Downloader/releases/latest/download/steam-workshop-dl-linux-source.tar.gz) | исходники на Python (`.py`) |

**Windows.** Распакуйте ZIP и запустите нужный `.exe`. Python и установка
пакета не нужны. Windows может показать предупреждение SmartScreen — это
нормально для неподписанного exe, выберите «Подробнее → Выполнить в любом случае».

**Linux.** Распакуйте архив, установите Python 3.11+ и запустите:

```bash
tar -xzf steam-workshop-dl-linux-source.tar.gz
cd steam-workshop-dl
python3 run_gui.py      # графический интерфейс
python3 run_cli.py      # командная строка / мастер
```

Ниже описана установка из исходников вручную.

### Установка

Нужен Python 3.11 или новее.

Из папки проекта:

```bash
python -m pip install -e .
```

Если `python` не найден, на Linux используйте `python3`, на Windows — `py`.

### Запуск с графическим интерфейсом

```bash
python run_gui.py
```

После установки пакета:

```bash
steam-workshop-dl-gui
```

Порядок работы:

1. Выберите тип: **Коллекция** или **Мод**.
2. Вставьте ссылку или ID и укажите папку загрузки.
3. Нажмите **«Загрузить список модов»**.
4. Снимите галочки с ненужных модов.
5. Нажмите **«Скачать выбранные моды»**.

Кнопка **«Настройки…»** открывает:

- **Язык интерфейса** — English / Русский;
- **Тема** — светлая / тёмная;
- авторизацию Steam;
- путь к SteamCMD;
- параметры загрузки (resume, validate, ZIP).

Остальные кнопки:

- **«Повторить неудачные»** — только ошибки и отменённые загрузки;
- **«Выбрать все» / «Снять выделение»** — работа с галочками;
- **«Остановить загрузку»** — прервать текущую операцию.

Перетащите разделитель между списком модов и логом, чтобы уменьшить список.
Ссылка на GitHub остаётся видимой при изменении размера окна.

### Запуск CLI без параметров

```bash
python run_cli.py
```

После установки пакета:

```bash
steam-workshop-dl
```

Мастер спросит:

1. тип объекта (коллекция или мод);
2. ссылку или ID;
3. папку загрузки;
4. покажет список модов;
5. попросит подтверждение `y/n`.

По умолчанию: тип — коллекция, папка — `~/Downloads/workshop`,
подтверждение — «нет», вход — анонимный.

### Параметры CLI

Основные:

| Параметр | Описание |
|---|---|
| `URL_ИЛИ_ID` | ссылка или ID коллекции/мода |
| `--type collection` | тип цели: коллекция |
| `--type mod` | тип цели: один мод |
| `-o, --output ПАПКА` | папка загрузки |
| `--list` | показать список модов и выйти |
| `--dry-run` | показать план без скачивания |
| `--only ID,ID` | скачать только указанные ID |
| `--exclude ID,ID` | исключить указанные ID |
| `--login USER` | вход под аккаунтом Steam |
| `--anonymous` | анонимный вход |
| `--steamcmd ПУТЬ` | свой путь к SteamCMD |
| `--no-steamcmd-bootstrap` | не скачивать SteamCMD автоматически |
| `--validate` | проверить файлы после загрузки |
| `--zip` | упаковать каждый мод в ZIP |

Дополнительные:

| Параметр | Описание |
|---|---|
| `--no-resume` | не докачивать, скачать заново |
| `--force` | игнорировать манифест |
| `--retries N` | число повторов при ошибках |
| `--jobs N` | потоков для получения метаданных |
| `--timeout СЕК` | таймаут запросов |
| `--by-app` | раскладывать по папкам приложений |
| `--flat` | без вложенных папок |
| `--config ФАЙЛ` | свой `config.toml` |
| `--log-file ФАЙЛ` | записывать лог в файл |
| `-v, --verbose` | подробный вывод |
| `--gui` | открыть графический интерфейс |
| `--version` | показать версию |

Полная справка:

```bash
python run_cli.py --help
```

### Примеры

```bash
# посмотреть состав коллекции
python run_cli.py "https://steamcommunity.com/sharedfiles/filedetails/?id=123456789" --list

# скачать коллекцию
python run_cli.py 123456789 --type collection -o ~/Downloads/workshop

# скачать один мод
python run_cli.py 123456789 --type mod

# скачать только два мода из коллекции
python run_cli.py 123456789 --type collection --only 111,222

# вход под аккаунтом Steam
python run_cli.py 123456789 --login МОЙ_ЛОГИН
```

### Язык интерфейса

В GUI откройте **«Настройки…» → «Интерфейс» → «Язык интерфейса»**.

- Доступны **English** и **Русский**.
- По умолчанию выбирается основной язык ОС.
- Выбор запоминается в `gui.json` и применяется при следующем запуске.
- Сообщения об ошибках и строки лога тоже переводятся.

### Тема

В GUI откройте **«Настройки…» → «Интерфейс» → «Тема»**.

- Доступны **светлая** и **тёмная** темы.
- Тёмная тема меняет оформление окна, списка модов, лога и диалогов.
- Выбор запоминается в `gui.json` и применяется при следующем запуске.

### Параллельная загрузка

В GUI откройте **«Настройки…» → «Параметры загрузки»**.

- **Потоков загрузки**: `1` — один последовательный запуск SteamCMD;
  `2–4` — несколько процессов SteamCMD одновременно. Каждый поток один раз
  входит в Steam, а затем последовательно скачивает свою часть модов.
- **Нестабильный режим** добавляет в список вариант **«Каждый мод отдельно»**
  и запускает отдельный SteamCMD для каждого выбранного мода. У этого режима
  самые большие накладные расходы, и обычно он медленнее 1–4 потоков.
- Параллельный режим может упереться в ограничения Steam или перегрузить
  компьютер. Если не уверены, начните с 2 потоков; если параллельность
  замедляет загрузку, используйте 1.

### SteamCMD

Устанавливать SteamCMD вручную не нужно. Если он не найден, программа скачает
официальный архив Valve и распакует его:

- в папку `steamcmd/` рядом с проектом при запуске из исходников;
- в пользовательскую папку данных при запуске установленной команды.

Свой путь можно указать в настройках GUI или флагом `--steamcmd`.
Отключить автозагрузку: `--no-steamcmd-bootstrap` или снять галочку в настройках.

### Требования и ограничения

- Нужен доступ к Steam Workshop и серверам Valve.
- Для платных или приватных модов нужен аккаунт с доступом.
- SteamCMD скачивает файлы последовательно, поэтому большие коллекции
  загружаются не мгновенно. Увеличьте число потоков до 2–4, если позволяет
  соединение.

---

---

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```
