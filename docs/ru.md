# Запуск и добавление устройств

Утилита показывает заряд мышек и наушников в трее Windows. Наведи курсор на иконку, чтобы увидеть процент. При заряде ниже 15% иконка красная, при отсутствии показания серая.

## Установка

Нужны Windows 10 или 11 и 64-битный Python 3.13. Эта версия запускается из исходников. На странице проекта выбери **Code → Download ZIP**, распакуй архив и открой PowerShell в получившейся папке.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe peripheral_battery.py --check
.\.venv\Scripts\python.exe peripheral_battery.py
```

IPI Haze X Pro и Logitech PRO X 2 LIGHTSPEED проверены с их USB-приёмниками. Если Windows спрятала иконки под стрелку **^**, перетащи их рядом с часами. В меню по правой кнопке **Refresh battery** обновляет заряд, **Exit** закрывает утилиту.

## Другая мышка или наушники

**Bluetooth.** Подключи устройство в параметрах Windows, разбуди его и запусти:

```powershell
.\.venv\Scripts\python.exe peripheral_battery.py --scan-ble
Copy-Item devices.example.toml devices.toml
```

Открой `devices.toml` в редакторе. Впиши имя, адрес из списка и тип `mouse` или `headset`. Повтори блок `[[bluetooth]]` для каждого устройства. Проверь через `--check`, затем перезапусти утилиту. Процент доступен у устройств, которые отдают его через стандартный Bluetooth LE Battery Service.

**USB-приёмник 2,4 ГГц.** Запусти `--list-hid` до и после подключения приёмника. Найди появившиеся **VID:PID** и пары **usage page:usage**. Для нового приёмника нужен профиль с подтверждённой командой чтения заряда. В [руководстве по устройствам](adding-devices.md) есть шаблон и порядок проверки. Для запроса поддержки открой GitHub Issue с моделью, режимом подключения, идентификаторами и ссылкой на программу производителя. Адрес Bluetooth и серийные номера в Issue не нужны.

## Если что-то не работает

| Что видно | Что проверить |
| --- | --- |
| Команда `py` отсутствует или не находит Python 3.13 | Установи [64-битный Python 3.13 для Windows](https://www.python.org/downloads/windows/) с лаунчером Python и открой PowerShell заново. |
| `No supported device found` | Подключи оригинальный USB-приёмник или добавь Bluetooth-устройство в `devices.toml`. Для диагностики запусти `--list-hid` или `--scan-ble`. |
| Иконка серая, подсказка пишет `Battery unavailable` | Разбуди устройство, проверь соединение и нажми **Refresh battery**. Если нужно, повтори `--check`. |
| `--check` показывает заряд, а иконки нет | Запусти утилиту без `--check`, оставь её запущенной и проверь меню под стрелкой **^** возле часов. |

Если проблема повторяется, создай [GitHub Issue](https://github.com/Bratuha1/peripheral-battery-tray/issues/new) и приложи модель устройства, режим подключения, версию Windows, вывод `--check` и шаги, на которых возникает проблема.
