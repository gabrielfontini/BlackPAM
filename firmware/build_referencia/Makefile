# Build de REFERÊNCIA (fora do CubeIDE) — serve para provar que TX e RX compilam
# com a HAL oficial. Uso:
#   ./baixar_hal.sh            (uma vez: baixa HAL + CMSIS da ST no GitHub)
#   make                       (gera tx.elf/.bin e rx.elf/.bin)
#   STM32_Programmer_CLI -c port=SWD -w tx.bin 0x08000000 -rst   (opcional)
HAL_DIR  ?= ./ext
PREFIX   ?= arm-none-eabi-
CC        = $(PREFIX)gcc
OBJCOPY   = $(PREFIX)objcopy
SIZE      = $(PREFIX)size

HAL_SRC  = $(HAL_DIR)/hal/Src
HAL_FILES = stm32f4xx_hal.c stm32f4xx_hal_cortex.c stm32f4xx_hal_rcc.c stm32f4xx_hal_rcc_ex.c \
            stm32f4xx_hal_gpio.c stm32f4xx_hal_dma.c stm32f4xx_hal_dma_ex.c stm32f4xx_hal_pwr.c \
            stm32f4xx_hal_pwr_ex.c stm32f4xx_hal_flash.c stm32f4xx_hal_flash_ex.c \
            stm32f4xx_hal_tim.c stm32f4xx_hal_tim_ex.c stm32f4xx_hal_adc.c stm32f4xx_hal_adc_ex.c \
            stm32f4xx_hal_uart.c stm32f4xx_hal_exti.c
HAL      = $(addprefix $(HAL_SRC)/,$(HAL_FILES))

MCU      = -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
DEFS     = -DSTM32F411xE -DUSE_HAL_DRIVER
INC      = -Icomum -I../common -I../tx -I../rx -I$(HAL_DIR)/hal/Inc \
           -I$(HAL_DIR)/dev/Include -I$(HAL_DIR)/core/CMSIS/Core/Include
CFLAGS   = $(MCU) $(DEFS) $(INC) -O2 -g -Wall -Wextra -Wno-unused-parameter -ffunction-sections -fdata-sections
LDFLAGS  = $(MCU) -Tcomum/STM32F411CEUX_FLASH.ld -Wl,--gc-sections -specs=nano.specs -specs=nosys.specs -Wl,-Map=$@.map

COMUM    = comum/startup_stm32f411xe.s comum/system_stm32f4xx.c comum/clock_f411.c ../common/pam_frame.c $(HAL)
TX_SRC   = tx/main_tx.c tx/stm32f4xx_it_tx.c tx/stm32f4xx_hal_msp_tx.c ../tx/pam_tx.c
RX_SRC   = rx/main_rx.c rx/stm32f4xx_it_rx.c rx/stm32f4xx_hal_msp_rx.c ../rx/pam_rx.c ../rx/pam_rx_core.c ../rx/pam_rx_report.c

all: tx.bin rx.bin
tx.elf: $(TX_SRC) $(COMUM)
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@
	$(SIZE) $@
rx.elf: $(RX_SRC) $(COMUM)
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@
	$(SIZE) $@
%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
clean:
	rm -f *.elf *.bin *.map
.PHONY: all clean
