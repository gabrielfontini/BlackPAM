#!/bin/sh
# Baixa somente o necessário para o build de referência (HAL F4 + CMSIS) da ST.
set -e
mkdir -p ext && cd ext
[ -d hal ]  || git clone --depth 1 https://github.com/STMicroelectronics/stm32f4xx-hal-driver.git hal
[ -d dev ]  || git clone --depth 1 https://github.com/STMicroelectronics/cmsis-device-f4.git dev
[ -d core ] || git clone --depth 1 https://github.com/STMicroelectronics/cmsis-core.git core
echo "OK: HAL em $(pwd)"
