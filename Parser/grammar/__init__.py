from pathlib import Path

import parsimonious

with (Path(__file__).parent / 'commands.grammar').open(mode='r', encoding='utf-8') as fp:
    commands_grammar = parsimonious.Grammar(fp.read())
