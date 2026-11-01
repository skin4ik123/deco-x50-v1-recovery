CC ?= cc
CFLAGS ?= -O2

.PHONY: all clean
all: check_recovery

nm_fwup.o: nm_fwup.c common.h nm_fwup.h nm_lib.h nm_api.h sysProductInfo.h
	$(CC) $(CFLAGS) -Wno-format -Wno-builtin-declaration-mismatch -Dsetenv=legacy_setenv -I. -c nm_fwup.c -o $@

check_recovery: driver.c nm_fwup.o
	$(CC) $(CFLAGS) -Wno-deprecated-declarations -I. driver.c nm_fwup.o -lcrypto -o $@

clean:
	rm -f nm_fwup.o check_recovery
