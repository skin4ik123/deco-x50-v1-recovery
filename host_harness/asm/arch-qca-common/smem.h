#ifndef HARNESS_SMEM_H
#define HARNESS_SMEM_H
#include <stdint.h>
typedef struct { uint64_t offset; uint64_t size; } qca_part_entry_t;
typedef struct { qca_part_entry_t rootfs[2]; qca_part_entry_t rt_data; } qca_smem_flash_info_t;
extern qca_smem_flash_info_t qca_smem_flash_info;
#endif
