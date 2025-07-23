/*
 * SPDX-FileCopyrightText: 2025 The LineageOS Project
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdint.h>
#include <stdio.h>

struct security_class_mapping {
  const char *name;
  const char *perms[sizeof(uint32_t) * 8 + 1];
};

#include <classmap.h>

int main(void) {
  printf("{\n");
  for (int i = 0; secclass_map[i].name != NULL; i++) {
    printf("  \"%s\": [", secclass_map[i].name);
    for (int j = 0; secclass_map[i].perms[j] != NULL; j++) {
      printf("\"%s\"", secclass_map[i].perms[j]);
      if (secclass_map[i].perms[j + 1] != NULL)
        printf(", ");
    }
    printf("]");
    if (secclass_map[i + 1].name != NULL)
      printf(",");
    printf("\n");
  }
  printf("}\n");
  return 0;
}
