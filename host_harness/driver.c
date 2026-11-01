/* Host-only execution of the original GPL nm_fwup.c.
 * All flash/environment operations are inert logging stubs. No router I/O.
 * OpenSSL implements the same RSA-1024/SHA1(MD5(message)) verification as GPL.
 * The mock partition map is a stated assumption, not a hardware observation.
 */
#include "common.h"
#include <stdlib.h>
#include <openssl/evp.h>
#include <openssl/rsa.h>
#include <openssl/objects.h>
#include "nm_fwup.h"
#include "sysProductInfo.h"
#include "asm/arch-qca-common/smem.h"

qca_smem_flash_info_t qca_smem_flash_info = {
    .rootfs = {{0x640000, 0x2a00000}, {0x3040000, 0x2a00000}},
    .rt_data = {0x63c0000, 0x1100000}
};
int has_boot_alter_flag = 0;
static int erase_calls, write_calls, config_calls, support_calls;
static uint64_t written_length;

void md5(const unsigned char *data, unsigned int size, unsigned char *digest) {
    unsigned int out;
    if (!EVP_Digest(data, size, digest, &out, EVP_md5(), NULL)) abort();
}

int rsaVerifySignByBase64EncodePublicKeyBlob(unsigned char *blob64, unsigned long blob_len,
    unsigned char *message, unsigned long message_len,
    unsigned char *sig, unsigned long sig_len) {
    unsigned char blob[1024], reversed[128], digest[20];
    unsigned int digest_len;
    if (sig_len != 128 || EVP_DecodeBlock(blob, blob64, blob_len) < 148) return 0;
    RSA *rsa = RSA_new();
    BIGNUM *n = BN_lebin2bn(blob + 20, 128, NULL), *e = BN_new();
    uint32_t exp = blob[16] | (blob[17]<<8) | (blob[18]<<16) | (blob[19]<<24);
    BN_set_word(e, exp);
    RSA_set0_key(rsa, n, e, NULL);
    for (unsigned int i=0;i<128;i++) reversed[i] = sig[127-i];
    EVP_Digest(message, message_len, digest, &digest_len, EVP_sha1(), NULL);
    int ret = RSA_verify(NID_sha1, digest, digest_len, reversed, 128, rsa);
    RSA_free(rsa);
    printf("HARNESS_RSA_VALID=%d\n", ret);
    return ret;
}

int nm_lib_eraseNandNvram(loff_t offset, loff_t size) {
    erase_calls++;
    if ((uint64_t)offset == qca_smem_flash_info.rt_data.offset) config_calls++;
    printf("MOCK_ERASE offset=0x%llx size=0x%llx\n", (unsigned long long)offset, (unsigned long long)size);
    return 0;
}
int nm_lib_writeNandNvram(char *buf, loff_t offset, loff_t len, loff_t max_size) {
    write_calls++; written_length = len;
    if (len > max_size || memcmp(buf, "UBI#", 4)) return -1;
    printf("MOCK_WRITE offset=0x%llx bytes=%llu max=%llu\n", (unsigned long long)offset,
        (unsigned long long)len, (unsigned long long)max_size);
    return 0;
}
int legacy_setenv(const char *key, const char *value) {
    printf("MOCK_SETENV %s=%s\n", key, value); return 0;
}
int saveenv(void) { puts("MOCK_SAVEENV"); return 0; }
PRODUCT_INFO_STRUCT *sysmgr_getProductInfo(void) { static PRODUCT_INFO_STRUCT info; return &info; }
int sysmgr_cfg_checkSupportList(PRODUCT_INFO_STRUCT *p, const char *list, int len) {
    (void)p; (void)list; (void)len;
    support_calls++;
    /* Fail closed if this hardware-dependent stub is reached. */
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) return 64;
    FILE *fp = fopen(argv[1], "rb"); if (!fp) return 66;
    fseek(fp, 0, SEEK_END); long size = ftell(fp); rewind(fp);
    if (size < 6165 || size > 100*1024*1024) return 65;
    unsigned char *data = malloc(size); if (!data) return 71;
    if (fread(data, 1, size, fp) != (size_t)size) return 74;
    fclose(fp);
    for (int i=2;i<argc;i++) {
        if (!strcmp(argv[i], "--clamp")) {
            uint32_t declared = htonl(0x2001814); memcpy(data, &declared, 4);
        } else if (!strcmp(argv[i], "--proud")) {
            data[0x1c] = 'P'; data[0x1d] = 'r';
        } else if (!strcmp(argv[i], "--flip")) {
            data[0x2814] ^= 1;
        } else if (!strcmp(argv[i], "--manu")) {
            data[0x101f] = 1;
        } else return 64;
    }
    puts("HOST_ONLY: flash and environment calls are stubbed; no physical router is involved.");
    int ret = nm_upgradeFirmware((char *)data, (int)size);
    printf("HARNESS_RESULT ret=%d erase_calls=%d write_calls=%d config_erase_calls=%d support_stub_calls=%d written_bytes=%llu\n",
        ret, erase_calls, write_calls, config_calls, support_calls, (unsigned long long)written_length);
    free(data);
    return ret ? 2 : 0;
}
