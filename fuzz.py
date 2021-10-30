#import kaitaistruct
#import gif

#g = gif.Gif.from_file("handtinyblack.gif")

#print("width = %d" % (g.logical_screen.image_width))
#print("height = %d" % (g.logical_screen.image_height))
import yaml
import json
import sys
import string
import random


def randbytes(n):
    return bytes([random.randrange(0, 256) for _ in range(n)])

CHARS = string.ascii_uppercase + string.digits
def randstring(n):
    return ''.join(random.choice(CHARS) for _ in range(n))

class KaitaiFuzz:
    def __init__(self, fn):
        self.default_endian = None
        self.out_buffer = []
        self.json_out = []
        self.scope_stack = []
        self.enums = {}

        self.load_struct(fn)

    def fuzz(self):
        self.gen_seq(self.data, self.json_out) # pass a list to seq.
        return self.json_out

    def out(self, var, o):
        assert isinstance(var, bytes)
        self.out_buffer.append(var)
        # Need to store the size also.
        o.append((var, len(var)))

    def get_endian(self):
        if self.default_endian is None:
            return 'big'
        elif self.default_endian == 'le':
            return 'little'
        elif self.default_endian == 'be':
            return 'big'
        assert False

    def load_struct(self, fn):
        with open(fn) as f:
            self.data = yaml.safe_load(f)
        self.load_meta()
        self.load_types()
        self.load_enums()

    def load_enums(self):
        if 'enums' in self.data:
            enums = self.data['enums']
            for k in enums:
                self.enums[k] = enums[k]
        else:
            self.enums = {}

    # integers
    def gen_u1(self, o):
        self.out(randbytes(1), o)
    def gen_u2(self, o):
        self.out(randbytes(2), o) 
    def gen_u4(self, o):
        self.out(randbytes(4), o) 
    def gen_s1(self, o):
        self.out(randbytes(1), o) 
    def gen_s2(self, o):
        self.out(randbytes(2), o) 
    def gen_s4(self, o):
        self.out(randbytes(4), o) 

    # floating point
    def gen_f4(self, o):
        self.out(randbytes(4), o) 
    def gen_f8(self, o):
        self.out(randbytes(8), o) 

    def gen_bytes(self, elt, o):
        length = elt['size']
        self.out(randbytes(length), o) 

    def gen_string(self, elt, o):
        length = elt['size']
        encoding = elt['encoding']
        s = randstring(length)
        self.out(bytes(s, encoding), o)

    def gen_contents(self, elt, o):
        c = elt['contents']
        if isinstance(c, str): # A UTF-8 string e.g. JFIF is [0x4A, 0x46, 0x49, 0x46]
            self.out(c.encode(), o)
        elif isinstance(c, list):
            # A list of bytes in hex. e.g. [0x4A, 0x46, 0x49, 0x46] or in decimal
            # or [0xCA, 0xFE, 0xBA, 0xBE]
            # or [CAFE, 0, BABE] => 43 41 46 45 00 42 41 42 45
            raise NotImplemented()
        else:
            raise NotImplemented()

    def scope_lookup(self, var):
        cur_scope = self.scope_stack[-1]
        lst = [elt for elt in cur_scope if var in elt]
        return lst

    def dispatch(self, my_type, elt, olst):
        if my_type in self.types:
            self.gen_seq(self.types[my_type], olst)
        elif my_type == 'u1':
            self.gen_u1(olst)
        elif my_type == 'u2':
            self.gen_u2(olst)
        elif my_type == 'u4':
            self.gen_u4(olst)
        elif my_type == 'f4':
            self.gen_f4(olst)
        elif my_type == 'f8':
            self.gen_f8(olst)
        elif my_type == 's1':
            self.gen_s1(olst)
        elif my_type == 's2':
            self.gen_s2(olst)
        elif my_type == 's4':
            self.gen_s4(olst)
        elif my_type == 's8':
            self.gen_s8(olst)
        elif my_type == 'str':
            self.gen_string(elt, olst)
        else:
            assert False

    def gen_element(self, elt, odict): 
        my_id = elt['id']
        olst = []
        odict[elt['id']] = olst
        if 'contents' in elt:
            self.gen_contents(elt, olst)
        else:
            if 'type' not in elt:
                self.gen_bytes(elt, olst)
            else:
                my_type = elt['type'] 
                if isinstance(my_type, str):
                    self.dispatch(my_type, elt, olst)
                elif isinstance(my_type, dict):
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
                        my_type = self.enums[var][ival]
                    else:
                        ival = random.choice(possible_values)
                        bval = ival.to_bytes(length, byteorder=self.get_endian())
                        val_lst[0][var][0] = (bval, length)
                        my_type = self.enums[var][ival]

                    self.dispatch(my_type, elt, olst)
                else:
                    assert False

    def gen_seq(self, data, olst):
        seq = data['seq']
        self.scope_stack.append(olst)
        for elt in seq:
            odict = {}
            olst.append(odict)
            # check if it has a 'repeat' mode
            if 'repeat' in elt:
                assert False
            elif 'if' in elt:
                # get the if condition
                cond = elt['if']
                # remove the last variable, the remaining is the scope.
                assert False
            else:
                self.gen_element(elt, odict)

        # now parse instances too
        if 'instances' in data:
            instances = data['instances']
            my_env = {list(v.keys())[0]:int.from_bytes(list(v.values())[0][0][0], self.get_endian()) for v in olst}
            for prop_key in instances:
                value = instances[prop_key]['value']
                res = eval(value, {}, my_env)
                odict= {'$' + prop_key: res}
                olst.append(odict)
                # evaluate it, put it under $name

        self.scope_stack.pop()

    def load_meta(self):
        metadata = self.data['meta']
        self.default_endian = metadata['endian'] # le, be
        #print(data['id'], data['title'], data['endian'])

    def load_seqelt(self, elt):
        my_id = elt['id']
        my_type = elt['type']
        # does it have contents?
        if 'contents' in elt:
            print(elt['contents'])
        print(my_id, repr(my_type))
        #print(json.dumps(elt, indent=4))

    def load_types(self):
        if 'types' in self.data:
            self.types = self.data['types']
        else:
            self.types = {}

import sys
v = KaitaiFuzz(sys.argv[1]).fuzz()
for k in v:
    print(k)
