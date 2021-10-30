import yaml
import json
import sys
import string
import random
import earleyparser as P

EXPR_GRAMMAR = {
    '<start>': [['<bexpr>']],
    '<bexpr>': [
        ['<expr>', *list('!='), '<bexpr>'],
        ['<expr>', *list('=='), '<bexpr>'],
        ['<expr>', '<', '<bexpr>'],
        ['<expr>', '>', '<bexpr>'],
        ['<expr>', *list('>='), '<bexpr>'],
        ['<expr>', *list('<='), '<bexpr>'],
        ['(','<bexpr>', ')'],
        ['<expr>']
        ],
    '<expr>': [
        ['<term>', '+', '<expr>'],
        ['<term>', '-', '<expr>'],
        ['(', '<expr>', ')'],
        ['<term>']
        ],
    '<term>': [
        ['<fact>', '*', '<term>'],
        ['<fact>', '/', '<term>'],
        ['<fact>', '&', '<term>'],
        ['<fact>', *list('<<'), '<term>'],
        ['(', '<term>', ')'],
        ['<fact>']],
    '<fact>': [
        ['<number>'],
        ['<identifier>'],
        ['(','<expr>',')']
        ],
    '<identifier>': [
        ['<letter>', '<identifier_charz>']
    ],
    '<identifier_charz>': [
        ['<identifier_char>', '<identifier_charz>'],
        []
    ],
    '<number>': [
        ['<binarynumber>'],
        ['<digits>']
    ],
    '<binarynumber>': [
        [*list('0b'),'<digits>']
    ],
    '<letter>': [[s] for s in (string.ascii_letters + '_')],
    '<identifier_char>': [[i] for i in (string.ascii_letters + string.digits + '._')],
    '<digits>': [
        ['<digit>','<digits>'],
        ['<digit>']],
    '<digit>': [["%s" % str(i)] for i in range(10)],
}
START = '<start>'
TOKENS = ['<number>', '<identifier>']

class ExprSemantics:
    def __init__(self, tree, env):
        self.env = env
        self.tree = tree

    def lookup(self, dotted, env):
        if '.' not in dotted:
            # process env
            if isinstance(dotted, ExprEvaluator):
                return (dotted.eval(env))
            else:
                return (env[dotted])
        lst = dotted.split('.')
        val = env
        while lst:
            env = val
            first, *lst = lst
            val = env[first]

        # process env
        if isinstance(val, ExprEvaluator):
            return (val.eval(env))
        else:
            return (val)

    def unwrap_tuples(self, tup):
        if isinstance(tup, tuple):
            return ''.join([self.unwrap_tuples(t) for t in tup])
        else:
            return str(tup)

    def eval(self):
        t_src = self.tree_eval(self.tree)
        s = self.unwrap_tuples(t_src)
        return eval(s)

    def tree_eval(self, tree):
        name, children = tree
        if name == '<start>':
            return self.tree_eval(children[0])
        elif name == '<number>':
            return (children[0][0])
        elif name == '<identifier>':
            key = children[0][0]
            return self.lookup(key, self.env)
        elif name == '<bexpr>':
            if len(children) == 1:
                return self.tree_eval(children[0])
            elif self.with_paren(children):
                return self.tree_eval((name, children[1:-1]))
            else:
                operator = children[1][0]
                return (self.tree_eval(children[0]), operator, self.tree_eval(children[2]))
        elif name == '<expr>':
            if len(children) == 1:
                return self.tree_eval(children[0])
            elif self.with_paren(children):
                return self.tree_eval((name, children[1:-1]))
            else:
                operator = children[1][0]
                return (self.tree_eval(children[0]), operator, self.tree_eval(children[2]))
        elif name == '<term>':
            if len(children) == 1:
                return self.tree_eval(children[0])
            elif self.with_paren(children):
                return self.tree_eval((name, children[1:-1]))
            else:
                operator = children[1][0]
                return (self.tree_eval(children[0]), operator, self.tree_eval(children[2]))
        elif name == '<fact>':
            if len(children) == 1:
                return self.tree_eval(children[0])
            elif self.with_paren(children):
                return self.tree_eval((name, children[1:-1]))
            else:
                operator = children[1][0]
                return (self.tree_eval(children[0]), operator, self.tree_eval(children[2]))
        else:
            assert False, name

    def with_paren(self, children):
        return (children[0][0], children[-1][0]) == ('(', ')')

class ExprEvaluator:
    def __init__(self, src):
        parser = P.EarleyParser(EXPR_GRAMMAR)
        t_ = list(parser.parse_on(src.replace(' ',''), START))[0]
        self.tree = self.cleanup_tree(t_)

    def eval(self, env):
        result = ExprSemantics(self.tree, env).eval()
        return result

    def detokenize(self, tokens, tree):
        name, children = tree
        if not children: return (name, [])
        if name in tokens: return (name, [(P.tree_to_str(tree), [])])
        return (name, [self.detokenize(tokens, c) for c in children])

    def is_nonterminal(self, t):
        return t and ((t[0],t[-1]) == ('<', '>'))

    def delistify(self, tree):
        name, children = tree
        if not children: return (name, [])
        new_children = []
        last_is_terminal=False
        for c in children:
            if self.is_nonterminal(c[0]):
                new_children.append(c)
                last_is_terminal=False
            else:
                if last_is_terminal:
                    new_children[-1][0] = new_children[-1][0] + c[0]
                else:
                    new_children.append(list(c))
                last_is_terminal=True
        return (name, [self.delistify(c) for c in new_children])

    def cleanup_tree(self, t):
        t1 = self.detokenize(TOKENS, t)
        t2 = self.delistify(t1)
        return t2


CHARS = string.ascii_uppercase + string.digits
def randstring(n):
    return ''.join(random.choice(CHARS) for _ in range(n))

def randbytes(n):
    return bytes([random.randrange(0, 256) for _ in range(n)])

# Load meta data.

class BasicGenerators:
    def unwrap(self, val):
        if isinstance(val, tuple):
            typ = val[1]
            value = val[0]
            bo = val[2]
            return int.from_bytes(value, byteorder=bo)
        else:
            return val

    def get_endian(self):
        if self.default_endian is None:
            return 'big'
        elif self.default_endian == 'le':
            return 'little'
        elif self.default_endian == 'be':
            return 'big'
        assert False

    def dispatch(self, my_type, attrib):
        if my_type == 'u1':
            return self.gen_u1()
        elif my_type == 'u2':
            return self.gen_u2()
        elif my_type == 'u4':
            return self.gen_u4()
        elif my_type == 'f4':
            return self.gen_f4()
        elif my_type == 'f8':
            return self.gen_f8()
        elif my_type == 's1':
            return self.gen_s1()
        elif my_type == 's2':
            return self.gen_s2()
        elif my_type == 's4':
            return self.gen_s4()
        elif my_type == 's8':
            return self.gen_s8()
        elif my_type == 'str':
            return self.gen_string(attrib['size'], attrib['encoding'])
        else:
            assert False
    # integers
    def gen_u1(self):
        return (randbytes(1), 'u1', self.get_endian())
    def gen_u2(self):
        return (randbytes(2), 'u2', self.get_endian())
    def gen_u4(self):
        return (randbytes(4), 'u4', self.get_endian())
    def gen_s1(self):
        return (randbytes(1), 's1', self.get_endian())
    def gen_s2(self):
        return (randbytes(2), 's2', self.get_endian())
    def gen_s4(self):
        return (randbytes(4), 's4', self.get_endian())
    # floating point
    def gen_f4(self):
        return (randbytes(4), 'f4', self.get_endian())
    def gen_f8(self):
        return (randbytes(8), 'f8', self.get_endian())

    def gen_bytes(self, length):
        return (randbytes(length), '_', self.get_endian())

    def gen_string(self, length, encoding):
        #length = elt['size']
        #encoding = elt['encoding']
        s = randstring(length)
        return (bytes(s, encoding), 'str', self.get_endian())

    def gen_contents(self, elt):
        c = elt['contents']
        if isinstance(c, str): # A UTF-8 string e.g. JFIF is [0x4A, 0x46, 0x49, 0x46]
            return (c.encode(), 'str', self.get_endian())
        elif isinstance(c, list):
            # A list of bytes in hex. e.g. [0x4A, 0x46, 0x49, 0x46] or in decimal
            # or [0xCA, 0xFE, 0xBA, 0xBE]
            # or [CAFE, 0, BABE] => 43 41 46 45 00 42 41 42 45
            raise NotImplemented()
        else:
            raise NotImplemented()

class KaitaiFuzz(BasicGenerators):
    def __init__(self, fn):
        self.title = None
        self.id = None
        self.default_endian = None
        # enums are at the top level.
        self.enums = {}
        self.load_struct(fn)

    def load_struct(self, fname):
        with open(fname) as f:
            self.data = yaml.safe_load(f)
        self.load_meta()
        self.load_types()
        self.load_enums()

    def load_meta(self):
        metadata = self.data['meta']
        self.default_endian = metadata['endian']
        self.title = metadata.get('title', None)
        self.id = metadata['id']

    def load_types(self):
        # may not exist
        self.types = self.data.get('types', {})

    def load_enums(self):
        self.enums = self.data.get('enums', {})

# Start fuzzing

class KaitaiFuzz(KaitaiFuzz):
    def fuzz(self):
        env, res = self.gen_seq(self.data)
        return res

# a sequence in KaitaiStruct is weird. It looks like a list, but it is
# actually a map which can be accessed by the `id` key.
# So, we need an environment where each processed keys are defined.

class KaitaiFuzz(KaitaiFuzz):
    def gen_seq(self, data):
        sequence = data['seq']
        my_env = {}
        my_result = []

        # We need to define instances before processing seq because
        # seq attributes can refer to instances. For now, we only
        # deal with value instances. One problem is that instances
        # can also refer to members. So, we go for a bit of
        # reprocessing. First, we iterate through seq, looking for
        # ids, define them in our environment, then implement
        # instances and finally, process the attributes.

        #all_eval = ['%s=lambda: O["%s"]' % (attr['id'], attr['id']) for attr in seq]
        my_instances = data.get('instances', {})
        my_value_fns = []
        for prop_key in my_instances:
            value = my_instances[prop_key]['value']
            my_env[prop_key] = ExprEvaluator(value)

        for attr in sequence:
            assert 'repeat' not in attr
            if 'if' in attr:
                result = ExprEvaluator(attr['if']).eval(my_env)
                if not result: continue
            # KaitaiStruct calls them attributes.
            env, out = self.gen_attribute(attr, my_env)
            assert attr['id'] in env
            my_result.append(out)
            my_env.update(env)

        return my_env, my_result

class KaitaiFuzz(KaitaiFuzz):
    def switch_on(self, my_type, attrib):
        var = my_type['switch-on']
        cases = my_type['cases']
        #self.enums[var]key is int, and val is desc.
        possible_values = [k for k in self.enums[var]]
        # is it one of them? If not, set it to one of the above.
        # look in the scope for our var.
        val_lst = self.scope_lookup(var)
        val, length = val_lst[0][var][0]
        ival = int.from_bytes(val, self.get_endian())
        my_type = None

        if ival in possible_values:
            return self.enums[var][ival]
        else:
            ival = random.choice(possible_values)
            bval = ival.to_bytes(length, byteorder=self.get_endian())
            val_lst[0][var][0] = (bval, length)
            return self.enums[var][ival]

    def gen_attribute(self, attrib, env):
        my_id = attrib['id']
        if 'contents' in attrib:
            res = self.gen_contents(attrib)
            return {my_id: self.unwrap(res)}, res
        else:
            if 'type' not in attrib:
                res = self.gen_bytes(attrib['size'])
                return {my_id: self.unwrap(res)}, res
            else:
                my_type = attrib['type']
                if isinstance(my_type, str):
                    if my_type in self.types:
                        env, res =  self.gen_seq(self.types[my_type])
                        return {my_id: env}, res
                    res = self.dispatch(my_type, attrib)
                    return {my_id: self.unwrap(res)}, res
                elif isinstance(my_type, dict):
                    my_type = self.switch_on(my_type, attrib)
                    if my_type in self.types:
                        env, res =  self.gen_seq(self.types[my_type])
                        return {my_id: env}, res
                    res = self.dispatch(my_type, attrib)
                    return {my_id: self.unwrap(res)}, res
                else:
                    assert False


kf = KaitaiFuzz(sys.argv[1])
res = kf.fuzz()
print(res)
