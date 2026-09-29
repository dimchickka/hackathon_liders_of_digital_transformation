$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$output = Join-Path $project 'build'
New-Item -ItemType Directory -Force -Path $output | Out-Null

$compiler = (Get-Command arm-none-eabi-gcc -ErrorAction Stop).Source
$objcopy = (Get-Command arm-none-eabi-objcopy -ErrorAction Stop).Source
$elf = Join-Path $output 'spi_flash_dump.elf'
$bin = Join-Path $output 'spi_flash_dump.bin'
$map = Join-Path $output 'spi_flash_dump.map'

$options = @(
    '-mcpu=cortex-m3', '-mthumb', '-std=c11', '-O2', '-g3',
    '-ffreestanding', '-fdata-sections', '-ffunction-sections',
    '-Wall', '-Wextra', '-Werror', '-nostdlib',
    '-Wl,--gc-sections', "-Wl,-Map=$map",
    '-T', (Join-Path $project 'linker.ld'),
    '-I', (Join-Path $project 'inc'),
    (Join-Path $project 'startup\startup.c'),
    (Join-Path $project 'src\hardware.c'),
    (Join-Path $project 'src\spi_flash.c'),
    (Join-Path $project 'src\main.c'),
    '-o', $elf
)
& $compiler @options
if ($LASTEXITCODE -ne 0) { throw 'arm-none-eabi-gcc failed' }
& $objcopy -O binary $elf $bin
if ($LASTEXITCODE -ne 0) { throw 'arm-none-eabi-objcopy failed' }
Get-Item $elf,$bin | Select-Object Name,Length
