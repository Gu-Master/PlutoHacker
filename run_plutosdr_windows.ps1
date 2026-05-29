$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $rootDir

function Show-Usage {
    @"
Usage:
  .\run_plutosdr_windows.ps1 [--check] [--rebuild] [--skip-build] [--python PATH]
                            [--venv PATH] [--iio-root PATH] [--iio-include PATH]
                            [--iio-lib PATH] [--iio-dll PATH] [app args...]

Examples:
  .\run_plutosdr_windows.ps1
  .\run_plutosdr_windows.ps1 --check --iio-root C:\libiio
  .\run_plutosdr_windows.ps1 --rebuild --iio-include C:\libiio\include --iio-lib C:\libiio\lib --iio-dll C:\libiio\bin

Notes:
  - Native Windows launch is recommended for PlutoSDR. Docker is not recommended
    for this GUI + hardware workflow.
  - The script creates a local virtual environment in .venv-windows by default.
"@
}

function Resolve-PathSafe([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return ""
    }

    return [System.IO.Path]::GetFullPath($PathValue)
}

function Resolve-ProjectPath([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return Resolve-PathSafe $PathValue
    }

    return Resolve-PathSafe (Join-Path $rootDir $PathValue)
}

function Add-UniqueString([System.Collections.Generic.List[string]]$Target, [string]$Value) {
    if (-not [string]::IsNullOrWhiteSpace($Value) -and (Test-Path $Value) -and -not $Target.Contains($Value)) {
        $Target.Add($Value)
    }
}

function Find-FirstParentDirWithFile([string]$Root, [string]$FileName) {
    if ([string]::IsNullOrWhiteSpace($Root) -or -not (Test-Path $Root)) {
        return ""
    }

    $match = Get-ChildItem -Path $Root -Recurse -File -Filter $FileName -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if ($null -eq $match) {
        return ""
    }

    return $match.Directory.FullName
}

function Resolve-PythonBootstrap {
    param([string]$PreferredPython)

    if (-not [string]::IsNullOrWhiteSpace($PreferredPython)) {
        $pythonCommand = $PreferredPython
        if (Test-Path $PreferredPython) {
            $pythonCommand = Resolve-PathSafe $PreferredPython
        }

        return @{
            Exe = $pythonCommand
            PrefixArgs = @()
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        foreach ($candidate in @("3.12", "3.11", "3.10", "3.9", "3.13", "3")) {
            & $pyLauncher.Source "-$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" *> $null
            if ($LASTEXITCODE -eq 0) {
                return @{
                    Exe = $pyLauncher.Source
                    PrefixArgs = @("-$candidate")
                }
            }
        }
    }

    $pythonExe = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonExe) {
        return @{
            Exe = $pythonExe.Source
            PrefixArgs = @()
        }
    }

    throw "Python 3.9+ was not found. Install Python and try again."
}

function Invoke-CheckedCommand {
    param(
        [string]$Exe,
        [string[]]$Arguments
    )

    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Exe $($Arguments -join ' ')"
    }
}

function Test-CompiledExtensions([string]$PythonExe) {
    $code = @"
modules = (
    "urh.cythonext.signal_functions",
    "urh.cythonext.path_creator",
    "urh.cythonext.util",
    "urh.dev.native.lib.plutosdr",
)

missing = []
for module in modules:
    try:
        __import__(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")

if missing:
    print("Missing or unusable compiled extensions:")
    print("\n".join("  " + item for item in missing))
    raise SystemExit(1)
"@

    & $PythonExe -c $code
    return $LASTEXITCODE -eq 0
}

function Resolve-IioDirectories {
    param(
        [string]$ExplicitRoot,
        [string]$ExplicitInclude,
        [string]$ExplicitLib,
        [string]$ExplicitDll
    )

    $roots = New-Object 'System.Collections.Generic.List[string]'
    Add-UniqueString $roots (Resolve-PathSafe $ExplicitRoot)
    Add-UniqueString $roots (Resolve-PathSafe $env:IIO_ROOT)
    Add-UniqueString $roots (Resolve-PathSafe $env:LIBIIO_ROOT)
    Add-UniqueString $roots (Join-Path $rootDir "third_party\libiio")
    Add-UniqueString $roots "C:\libiio"
    Add-UniqueString $roots (Join-Path $env:ProgramFiles "libiio")
    Add-UniqueString $roots (Join-Path $env:ProgramFiles "ADI\libiio")

    if (${env:ProgramFiles(x86)}) {
        Add-UniqueString $roots (Join-Path ${env:ProgramFiles(x86)} "libiio")
        Add-UniqueString $roots (Join-Path ${env:ProgramFiles(x86)} "ADI\libiio")
    }

    $includeDir = Resolve-PathSafe $ExplicitInclude
    if ([string]::IsNullOrWhiteSpace($includeDir)) {
        $includeDir = Resolve-PathSafe $env:IIO_INCLUDE_DIR
    }
    if ([string]::IsNullOrWhiteSpace($includeDir)) {
        $includeDir = Resolve-PathSafe $env:LIBIIO_INCLUDE_DIR
    }

    $libDir = Resolve-PathSafe $ExplicitLib
    if ([string]::IsNullOrWhiteSpace($libDir)) {
        $libDir = Resolve-PathSafe $env:IIO_LIBRARY_DIR
    }
    if ([string]::IsNullOrWhiteSpace($libDir)) {
        $libDir = Resolve-PathSafe $env:LIBIIO_LIBRARY_DIR
    }

    $dllDir = Resolve-PathSafe $ExplicitDll
    if ([string]::IsNullOrWhiteSpace($dllDir)) {
        $dllDir = Resolve-PathSafe $env:IIO_DLL_DIR
    }
    if ([string]::IsNullOrWhiteSpace($dllDir)) {
        $dllDir = Resolve-PathSafe $env:LIBIIO_DLL_DIR
    }

    foreach ($candidateRoot in $roots) {
        if ([string]::IsNullOrWhiteSpace($includeDir)) {
            $includeDir = Find-FirstParentDirWithFile -Root $candidateRoot -FileName "iio.h"
        }

        if ([string]::IsNullOrWhiteSpace($libDir)) {
            $libDir = Find-FirstParentDirWithFile -Root $candidateRoot -FileName "iio.lib"
        }

        if ([string]::IsNullOrWhiteSpace($dllDir)) {
            $dllDir = Find-FirstParentDirWithFile -Root $candidateRoot -FileName "iio.dll"
        }
    }

    if ([string]::IsNullOrWhiteSpace($includeDir) -or [string]::IsNullOrWhiteSpace($libDir) -or [string]::IsNullOrWhiteSpace($dllDir)) {
        throw @"
Could not locate libiio for PlutoSDR.

Install a Windows libiio package first, then run one of these forms:
  .\run_plutosdr_windows.ps1 --iio-root C:\libiio
  .\run_plutosdr_windows.ps1 --iio-include C:\libiio\include --iio-lib C:\libiio\lib --iio-dll C:\libiio\bin

You can also set environment variables:
  IIO_ROOT / IIO_INCLUDE_DIR / IIO_LIBRARY_DIR / IIO_DLL_DIR
"@
    }

    return @{
        Include = $includeDir
        Library = $libDir
        Dll = $dllDir
    }
}

$checkOnly = $false
$forceRebuild = $false
$skipBuild = $false
$preferredPython = ""
$venvDir = ".venv-windows"
$iioRoot = ""
$iioIncludeDir = ""
$iioLibDir = ""
$iioDllDir = ""
$appArgs = New-Object System.Collections.Generic.List[string]

for ($i = 0; $i -lt $args.Count; $i++) {
    $arg = [string]$args[$i]

    switch -Regex ($arg) {
        '^--help$|^-h$' {
            Show-Usage
            exit 0
        }
        '^--check$' {
            $checkOnly = $true
            continue
        }
        '^--rebuild$' {
            $forceRebuild = $true
            continue
        }
        '^--skip-build$' {
            $skipBuild = $true
            continue
        }
        '^--python=(.+)$' {
            $preferredPython = $Matches[1]
            continue
        }
        '^--venv=(.+)$' {
            $venvDir = $Matches[1]
            continue
        }
        '^--iio-root=(.+)$' {
            $iioRoot = $Matches[1]
            continue
        }
        '^--iio-include=(.+)$' {
            $iioIncludeDir = $Matches[1]
            continue
        }
        '^--iio-lib=(.+)$' {
            $iioLibDir = $Matches[1]
            continue
        }
        '^--iio-dll=(.+)$' {
            $iioDllDir = $Matches[1]
            continue
        }
        '^--python$' {
            $i++
            if ($i -ge $args.Count) { throw "--python requires a value." }
            $preferredPython = [string]$args[$i]
            continue
        }
        '^--venv$' {
            $i++
            if ($i -ge $args.Count) { throw "--venv requires a value." }
            $venvDir = [string]$args[$i]
            continue
        }
        '^--iio-root$' {
            $i++
            if ($i -ge $args.Count) { throw "--iio-root requires a value." }
            $iioRoot = [string]$args[$i]
            continue
        }
        '^--iio-include$' {
            $i++
            if ($i -ge $args.Count) { throw "--iio-include requires a value." }
            $iioIncludeDir = [string]$args[$i]
            continue
        }
        '^--iio-lib$' {
            $i++
            if ($i -ge $args.Count) { throw "--iio-lib requires a value." }
            $iioLibDir = [string]$args[$i]
            continue
        }
        '^--iio-dll$' {
            $i++
            if ($i -ge $args.Count) { throw "--iio-dll requires a value." }
            $iioDllDir = [string]$args[$i]
            continue
        }
        default {
            $appArgs.Add($arg)
        }
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "run_plutosdr_windows.ps1 must be started on Windows."
}

$bootstrap = Resolve-PythonBootstrap -PreferredPython $preferredPython
$resolvedVenvDir = Resolve-ProjectPath $venvDir
$venvPython = Join-Path $resolvedVenvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Invoke-CheckedCommand -Exe $bootstrap.Exe -Arguments ($bootstrap.PrefixArgs + @("-m", "venv", $resolvedVenvDir))
}

$pythonExe = $venvPython
Invoke-CheckedCommand -Exe $pythonExe -Arguments @("-m", "pip", "install", "--upgrade", "pip", "wheel")
Invoke-CheckedCommand -Exe $pythonExe -Arguments @("-m", "pip", "install", "-r", (Join-Path $rootDir "data\requirements.txt"))

$iioDirs = Resolve-IioDirectories -ExplicitRoot $iioRoot -ExplicitInclude $iioIncludeDir -ExplicitLib $iioLibDir -ExplicitDll $iioDllDir

$env:IIO_INCLUDE_DIR = $iioDirs.Include
$env:IIO_LIBRARY_DIR = $iioDirs.Library
$env:IIO_DLL_DIR = $iioDirs.Dll
$env:PLUTOSDR_SHARED_LIB_DIR = $iioDirs.Dll
$pythonPathEntry = Join-Path $rootDir "src"
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $pythonPathEntry
}
else {
    $env:PYTHONPATH = $pythonPathEntry + [System.IO.Path]::PathSeparator + $env:PYTHONPATH
}

if ([string]::IsNullOrWhiteSpace($env:PATH)) {
    $env:PATH = $iioDirs.Dll
}
else {
    $env:PATH = $iioDirs.Dll + [System.IO.Path]::PathSeparator + $env:PATH
}

$dependencyCheck = @"
import sys

if sys.version_info < (3, 9):
    raise SystemExit("Python 3.9 or newer is required.")

required = {
    "PyQt6": "PyQt6",
    "numpy": "numpy<3.0",
    "psutil": "psutil",
    "Cython": "cython",
    "setuptools": "setuptools",
}

missing = []
for module, package in required.items():
    try:
        __import__(module)
    except ImportError:
        missing.append(package)

if missing:
    print("Missing Python packages: " + ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
"@

Invoke-CheckedCommand -Exe $pythonExe -Arguments @("-c", $dependencyCheck)

if ($forceRebuild -or -not (Test-CompiledExtensions -PythonExe $pythonExe)) {
    if ($skipBuild) {
        throw "Compiled extensions are missing and --skip-build was set."
    }

    Write-Host "Building Cython and PlutoSDR native extensions for Windows..."
    Invoke-CheckedCommand -Exe $pythonExe -Arguments @("setup.py", "build_ext", "--inplace", "--with-plutosdr")

    if (-not (Test-CompiledExtensions -PythonExe $pythonExe)) {
        throw "Build finished, but compiled extensions are still unavailable."
    }
}

if ($checkOnly) {
    Write-Host "Windows launch check passed. PlutoSDR Protocol Tool is ready."
    exit 0
}

Invoke-CheckedCommand -Exe $pythonExe -Arguments (@("-m", "urh.main") + $appArgs.ToArray())
