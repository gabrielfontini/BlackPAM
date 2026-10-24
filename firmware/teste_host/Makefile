# Teste do firmware no PC:  make && ./sim_host 4 1
CC ?= gcc
CFLAGS = -O2 -Wall -Wextra -I../common -I../rx
sim_host: sim_host.c ../common/pam_frame.c ../rx/pam_rx_core.c ../rx/pam_rx_report.c
	$(CC) $(CFLAGS) -o $@ $^ -lm
clean:
	rm -f sim_host
