#
# Transforms Wandle DSL into a parse tree, using the Arpeggio library.
#

from arpeggio import Optional, ZeroOrMore, OneOrMore, EOF, OrderedChoice
from arpeggio import RegExMatch as _
from arpeggio import ParserPython
import arpeggio


def _word():                return _(r'\w+')
def _caps():                return _(r'[A-Z][A-Z]*')
def _type():                return _(r'[A-Z][a-zA-Z0-9/,]*')
def _single_name():         return _(r'[A-Z][a-zA-Z0-9/,]*')
def _snake():               return _(r'[a-zA-Z0-9_]*')
def _note_word():           return _(r'[a-zA-Z0-9/,()-.]*')

def _csep_words():          return _word, ZeroOrMore(',', _word)
def _csep_caps():           return _caps, ZeroOrMore(',', _caps)

def _decl_stmt():           return _(r'\w+'), _(r'\w+'), '.'
def _sync_assignment():     return _(r'\w+'), '=', _(r'\w+'), '.'
def _async_assignment():    return _(r'\w+'), '<<', _(r'\w+'), '.'
def _statement():           return OrderedChoice([
                                _decl_stmt,
                                _sync_assignment,
                                _async_assignment,
                            ])

# cb: code block.
def _cb_dot_ref():          return _word, ZeroOrMore('.', _word)
def _cb_param_list():       return '(', Optional(_cb_dot_ref, ZeroOrMore(',', _cb_dot_ref)), ')'
def _cb_async_call():       return '<<', _cb_dot_ref, _cb_param_list, ';'
def _cb_sync_call():        return '=', _cb_dot_ref, _cb_param_list, ';'
def _cb_async_from():       return _cb_dot_ref, _cb_async_call
def _cb_sync_from():        return _cb_dot_ref, _cb_sync_call
def _cb_sync_copy():        return _cb_dot_ref, '=', _cb_dot_ref, ';'
def _cb_var_stub():         return _type, _snake, ';'
def _cb_var_ready():        return _type, _snake, '!'
def _cb_var_async_set():    return _type, _snake, _cb_async_call
def _cb_var_sync_set():     return _type, _snake, _cb_sync_call
def _cb_note():             return 'note', '{', ZeroOrMore(_note_word), '}'
def _cb_return():           return 'return', OrderedChoice([_cb_dot_ref, _single_name]), ';'
def _cb_grammar():          return '{', ZeroOrMore(OrderedChoice([
                                _cb_sync_copy,
                                _cb_sync_from,
                                _cb_var_stub,
                                _cb_var_ready,
                                _cb_var_async_set,
                                _cb_var_sync_set,
                                _cb_async_from,
                                _cb_note,
                            ])), Optional([
                                _cb_return,
                            ]), '}'

def _normal_sig_pair():     return _type, _snake
def _method_sig():          return '(', Optional(_normal_sig_pair, ZeroOrMore(',', _normal_sig_pair)), ')'

# cgs is short for class/generic/single
def _cgs_async_stub():      return 'async', _type, _snake, _method_sig, ';'
def _cgs_async_impl():      return 'async', _type, _snake, _method_sig, _cb_grammar
def _cgs_async_gram():      return OrderedChoice([_cgs_async_stub, _cgs_async_impl])

def _cgs_sync_stub():       return 'sync', _type, _snake, _method_sig, ';'
def _cgs_sync_impl():       return 'sync', _type, _snake, _method_sig, _cb_grammar
def _cgs_sync_gram():       return OrderedChoice([_cgs_sync_stub, _cgs_sync_impl])

def _cgs_var_stub():        return _(r'[A-Z][a-zA-Z0-9/,]*'), _(r'[a-zA-Z0-9_]*'), ';'
def _cgs_var_ready():       return _(r'[A-Z][a-zA-Z0-9/,]*'), _(r'[a-zA-Z0-9_]*'), '!'
def _cgs_block():           return '{', ZeroOrMore(OrderedChoice([
                                _cgs_var_stub,
                                _cgs_var_ready,
                                _cgs_async_gram,
                                _cgs_sync_gram,
                            ])), '}'

def _class_inh_list():      return _word, ZeroOrMore(',', _word)
def _class_base_stub():     return 'class', _word, ';'
def _class_base_impl():     return 'class', _word, _cgs_block
def _class_inh_stub():      return 'class', _word, 'is', _class_inh_list, ';'
def _class_inh_impl():      return 'class', _word, 'is', _class_inh_list, _cgs_block
def _class_gram():          return OrderedChoice([
                                _class_base_stub,
                                _class_base_impl,
                                _class_inh_stub,
                                _class_inh_impl,
                            ])

def _single_stub():         return 'single', _single_name, ';'
def _single_impl():         return 'single', _snake, _cgs_block
def _single_gram():         return OrderedChoice([_single_stub, _single_impl])

def _generic_stub():        return 'generic', _type, _csep_caps, ';'
def _generic_impl():        return 'generic', _type, _csep_caps, _cgs_block
def _generic_gram():        return OrderedChoice([
                                _generic_stub,
                                _generic_impl,
                            ])

def _alias_gram():          return 'alias', _type, 'to', _type, ';'

def _flow_stub():           return 'flow', _snake, ';'
def _flow_impl():           return 'flow', _snake, _cb_grammar
def _flow_gram():           return OrderedChoice([
                                _flow_stub,
                                _flow_impl,
                            ])

def _grammar():             return ZeroOrMore(
                                OrderedChoice([
                                    _class_gram,
                                    _single_gram,
                                    _generic_gram,
                                    _alias_gram,
                                    _flow_gram,
                                ]),
                            ), EOF

def arpeggio_parse_go(wandle_src):
    # I could not find a way in arpeggio to make it match to the end of the
    # line. But, I want to use hash as a comment marker until end of line, as
    # with bash and python. So, I am doing a pre-transform of the src
    # document where I strip all the comments.
    sb = []
    for line in wandle_src.split('\n'):
        line = line.split('#')[0]
        sb.append(line.rstrip())
    wandle_src = '\n'.join(sb)

    parser = ParserPython(_grammar)
    parse_tree = parser.parse(wandle_src)
    return parse_tree

def arpeggio_parse_debug(parse_tree):
    "Prints the parse tree."
    incl = [0]
    def recurse(entry):
        if type(entry) == arpeggio.NonTerminal:
            print('%s/%s/%s'%(' '*(incl[0]*4), entry.rule_name, entry))
            incl[0] += 1
            for itm in entry:
                recurse(itm)
            incl[0] -= 1
    recurse(parse_tree)
