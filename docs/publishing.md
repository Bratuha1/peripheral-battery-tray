# Как подготовить выпуск на GitHub

## Сборка кандидата

1. Укажите версию в `settings.py`, обновите `CHANGELOG.md` и добавьте описание в `docs/releases/vX.Y.Z.md`. Для текущего выпуска см. [описание v1.0.0](releases/v1.0.0.md).
2. На Windows x64 выполните тесты и соберите дистрибутивы по разделу **Develop and build** в [README](../README.md). Для установщика укажите путь к Inno Setup через `--iscc`.
3. Внесите изменения в `main` через обычный для репозитория процесс. Поставьте аннотированный тег на этот коммит и отправьте его в GitHub.

```powershell
git tag -a v1.0.0 -m "Peripheral Battery Tray v1.0.0"
git push origin refs/tags/v1.0.0
```

GitHub Actions запускает тесты, собирает EXE, портативный ZIP и установщик, затем прикладывает их и `SHA256SUMS.txt` к черновику. В GitHub откройте **Actions → Windows build**, чтобы посмотреть результаты, и **Releases**, чтобы открыть черновик.

## Проверка и публикация

1. Скачайте файлы черновика. Сравните их контрольные суммы со списком `SHA256SUMS.txt`.

```powershell
Get-FileHash -Algorithm SHA256 .\PeripheralBatteryTray.exe
Get-FileHash -Algorithm SHA256 .\PeripheralBatteryTray-1.0.0-windows-x64-portable.zip
Get-FileHash -Algorithm SHA256 .\PeripheralBatteryTray-1.0.0-windows-x64-setup.exe
```

2. Проверьте эти же файлы на реальном оборудовании по [чек-листу](release-checklist.md). Для v1.0.0 отдельно подтвердите показания IPI и Logitech, обычный Bluetooth LE и запуск на чистой Windows 10 и 11. Если нужна правка уже собранного кандидата, соберите новую версию и повторите проверку.
3. После проверки откройте черновик в **Releases** и нажмите **Publish release**. Откройте страницу выпуска без авторизации и проверьте, что доступны три дистрибутива и файл контрольных сумм.
