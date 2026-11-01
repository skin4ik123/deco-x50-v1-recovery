#ifndef HARNESS_COMMON_H
#define HARNESS_COMMON_H
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/types.h>
#include <arpa/inet.h>
int legacy_setenv(const char *, const char *);
int saveenv(void);
void md5(const unsigned char *, unsigned int, unsigned char *);
int rsaVerifySignByBase64EncodePublicKeyBlob(unsigned char *, unsigned long,
    unsigned char *, unsigned long, unsigned char *, unsigned long);
#endif
