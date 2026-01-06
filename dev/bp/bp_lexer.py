# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import ply.lex as lex

tokens = (
    'LPAREN',
    'RPAREN',
    'LBRACE',
    'RBRACE',
    'LBRACK',
    'RBRACK',
    'COLON',
    'COMMA',
    'STRING',
    'IDENT',
    'NUMBER',
    'PLUS',
    'EQUALS',
)

t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_LBRACK = r'\['
t_RBRACK = r'\]'
t_COLON = r':'
t_COMMA = r','
t_PLUS = r'\+'
t_EQUALS = r'='


def t_NUMBER(t):
    r"\d+(\.\d+)?"
    if '.' in t.value:
        t.value = float(t.value)
    else:
        t.value = int(t.value)
    return t


def t_STRING(t):
    r'"([^"\\]|\\.)*"'
    t.value = t.value[1:-1]
    return t


def t_IDENT(t):
    r"[a-zA-Z_][a-zA-Z0-9_]*"
    return t


t_ignore = ' \t'


def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


def t_COMMENT(t):
    r"//[^\n]*"
    pass


def t_BLOCK_COMMENT(t):
    r"/\*(.|\n)*?\*/"
    t.lexer.lineno += t.value.count('\n')
    pass


def t_error(t):
    raise SyntaxError(f'Illegal character {t.value[0]!r}')


bp_lexer = lex.lex()
