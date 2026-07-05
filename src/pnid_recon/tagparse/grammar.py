"""Lark grammar for ISA 5.1 instrument tags (MVP core subset)."""

ISA_TAG_GRAMMAR = r"""
?start: tag

tag: letters "-" loop_number

letters: ISA_LETTERS

ISA_LETTERS: /[PFTLA][TICVESHAL]+/

loop_number: DIGITS

DIGITS: /[0-9]+/

%import common.WS
%ignore WS
"""
