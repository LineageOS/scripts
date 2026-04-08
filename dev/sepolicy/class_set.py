# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from typing import List


class ClassSet:
    def __init__(self, names: List[str], values: List[str]):
        self.__names = names
        self.__values = values
        self.__hash_values = frozenset(values)
        self.__hash = hash(self.__hash_values)

    def __iter__(self):
        return iter(self.__values)

    def __eq__(self, other: object):
        if not isinstance(other, ClassSet):
            return False

        if self.__hash != other.__hash:
            return False

        return self.__hash_values == other.__hash_values

    def __hash__(self):
        return self.__hash

    def __str__(self):
        sorted_values = sorted(self.__names)
        if len(sorted_values) == 1:
            return sorted_values[0]

        class_sets = ' '.join(sorted_values)
        return f'{{ {class_sets} }}'
