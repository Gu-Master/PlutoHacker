# PlutoSDR Protocol Tool

Автор проекта: Никита Гурачевский, группа ИА-232.

## О проекте

`PlutoSDR Protocol Tool` — настольное приложение для работы с радиосигналами через `Analog Devices PlutoSDR`.

Проект ориентирован на простой учебный и лабораторный сценарий:

- наблюдение сигнала на водопаде;
- запись сигнала в файл;
- просмотр сохранённых записей;
- повтор выбранного сигнала через `PlutoSDR`;
- запуск без лишней ручной настройки.

В приложении оставлена поддержка только `PlutoSDR`, за счёт чего интерфейс стал проще и удобнее для практической работы.

## Возможности

- встроенный водопад и спектр в первой вкладке;
- автоматическая запись сигналов в папку по умолчанию `~/PlutoSDR_Signals`;
- автоматическая загрузка папки сигналов при запуске;
- список записанных сигналов во вкладках `Сигналы` и `Повтор`;
- повтор сигнала через `PlutoSDR`;
- синхронизация рабочей частоты между водопадом, записью и повтором;
- запуск в Linux одной командой;
- запуск в Windows через готовые скрипты.

## Системные требования

### Linux

- `Python 3.9+`
- `PyQt6`
- `NumPy`
- `psutil`
- `Cython`
- `setuptools`
- `libiio-dev`

Для Debian/Ubuntu:

```bash
sudo apt install python3 python3-pip python3-pyqt6 python3-numpy python3-psutil cython3 python3-setuptools libiio-dev
```

При необходимости Python-зависимости можно установить через `pip`:

```bash
python3 -m pip install PyQt6 numpy psutil cython setuptools
```

### Windows

- `Python 3.9+`
- `Microsoft C++ Build Tools`
- `libiio for Windows`

## Запуск в Linux

Из корня проекта:

```bash
./run_plutosdr.sh
```

Проверка окружения без открытия окна:

```bash
./run_plutosdr.sh --check
```

Принудительная пересборка расширений:

```bash
./run_plutosdr.sh --rebuild
```

## Запуск в Windows

Из корня проекта:

```powershell
.\run_plutosdr_windows.bat --iio-root C:\libiio
```

Проверка без открытия интерфейса:

```powershell
.\run_plutosdr_windows.bat --check --iio-root C:\libiio
```

Если `libiio` лежит в разных папках:

```powershell
.\run_plutosdr_windows.bat --iio-include C:\libiio\include --iio-lib C:\libiio\lib --iio-dll C:\libiio\bin
```

## Структура проекта

- `src/urh` — основной исходный код приложения
- `data/ui` — исходные Qt UI-файлы
- `src/urh/ui` — сгенерированные Python UI-файлы
- `run_plutosdr.sh` — основной Linux-скрипт запуска
- `run_plutosdr_windows.ps1` и `run_plutosdr_windows.bat` — запуск в Windows
- `install_plutosdr_launcher.sh` — установка ярлыка в Linux

## Примечание по лицензии

В проекте сохранён файл [LICENSE](LICENSE), поскольку при распространении производной версии необходимо сохранять лицензионные условия исходной кодовой базы.
