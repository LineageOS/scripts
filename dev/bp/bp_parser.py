# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import ply.yacc as yacc

import bp.bp_lexer as bp_lexer

tokens = bp_lexer.tokens


def p_file(p):
    """file : statements
    | empty"""
    p[0] = p[1]


def p_statements(p):
    """statements : statements statement
    | statement"""
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[2]]


def p_statement(p):
    """statement : module
    | var_declaration"""
    p[0] = p[1]


def p_var_declaration(p):
    """var_declaration : IDENT EQUALS value"""
    p[0] = {'var': p[1], 'value': p[3]}


def p_module(p):
    """module : IDENT object"""
    p[0] = {'module': p[1], **p[2]}


def p_object(p):
    """object : LBRACE pairs_opt RBRACE"""
    p[0] = p[2]


def p_pairs_opt(p):
    """pairs_opt : pairs
    | empty_pairs"""
    p[0] = p[1]


def p_pairs(p):
    """pairs : pairs COMMA pair
    | pairs COMMA
    | pair"""
    if len(p) == 2 or len(p) == 3:
        p[0] = p[1]
    else:
        p[0] = {**p[1], **p[3]}


def p_pair(p):
    """pair : value COLON value"""
    p[0] = {p[1]: p[3]}


def p_value(p):
    """value : value PLUS value
    | STRING
    | NUMBER
    | array
    | tuple
    | object
    | function_call
    | IDENT"""
    if p[1] == 'true':
        p[0] = True
    elif p[1] == 'false':
        p[0] = False
    else:
        p[0] = p[1]


def p_function_call(p):
    """function_call : IDENT LPAREN items_opt RPAREN"""
    p[0] = {'function': p[1], 'args': p[3]}


def p_array(p):
    """array : LBRACK items_opt RBRACK"""
    p[0] = p[2]


def p_tuple(p):
    """tuple : LPAREN items_opt RPAREN"""
    p[0] = tuple(p[2])


def p_items_opt(p):
    """items_opt : items
    | empty"""
    p[0] = p[1]


def p_items(p):
    """items : items COMMA value
    | items COMMA
    | value"""
    if len(p) == 2:
        p[0] = [p[1]]
    elif len(p) == 3:
        p[0] = p[1]
    elif len(p) == 4:
        p[0] = p[1] + [p[3]]


def p_empty(p):
    "empty :"
    p[0] = []


def p_empty_pairs(p):
    "empty_pairs :"
    p[0] = {}


def p_error(p):
    if not p:
        raise SyntaxError('Syntax error at EOF')

    # Get the input text from the lexer
    data = p.lexer.lexdata

    # Find the line where the error occurred
    line_start = data.rfind('\n', 0, p.lexpos) + 1
    line_end = data.find('\n', p.lexpos)

    if line_end == -1:
        line_end = len(data)

    line = data[line_start:line_end]
    col = p.lexpos - line_start

    raise SyntaxError(
        f'Syntax error at token {p.type} ({p.value!r}) on line {p.lineno}\n'
        f'> {line}\n' + (' ' * (col + 2)) + '^'
    )


precedence = (
    ('left', 'PLUS'),
    ('left', 'EQUALS'),
)

bp_parser = yacc.yacc()
