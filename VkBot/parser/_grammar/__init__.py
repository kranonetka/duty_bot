from pathlib import Path

import parsimonious

with (Path(__file__).parent / 'message.grammar').open('r', encoding='utf-8') as fp:
    message_grammar = parsimonious.Grammar(fp.read())
