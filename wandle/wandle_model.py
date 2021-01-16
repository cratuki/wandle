#
# This module is concerned with transforming (an arpeggio tree in WandleDSL
# format) into (a tree structure of WandleX objects built upon WandleModel).
#

import copy
from pprint import pprint


class SyntaxError(Exception):

    def __init__(self, message):
        self.message = message
        

# --------------------------------------------------------
#   param
# --------------------------------------------------------
class Param:

    def __init__(self, wandle_class, name):
        self.wandle_class = wandle_class
        self.name = name

        self.wtype = self.__class__.__name__

    def __repr__(self):
        return '%s %s'%(self.wandle_class.name, self.name)

    def get_type(self):
        return self.wandle_class.name


# --------------------------------------------------------
#   statement
# --------------------------------------------------------
STYPE_NOTE_CONTENT = 'note_content'
STYPE_SYNC_VAR_NUL = 'sync_var_nul'
STYPE_SYNC_VAR_VAL = 'sync_var_val'
STYPE_SYNC_LHS_RHS = 'sync_lhs_rhs'
STYPE_ASYNC_LHS_RHS = 'async_lhs_rhs'

class Statement:

    def __init__(self, stype):
        self.stype = stype

        self.wandle_class = None
        self.lhs_dotref = None
        self.rhs_dotref = None
        self.lst_rhs_param = []
        self.txt = None

    def as_code(self):
        sb = []
        if self.stype == STYPE_NOTE_CONTENT:
            sb.append('xxx STYPE_NOTE_CONTENT')
        elif self.stype == STYPE_SYNC_VAR_NUL:
            sb.append('xxx STYPE_SYNC_VAR_NUL')
        elif self.stype == STYPE_SYNC_VAR_VAL:
            sb.append('xxx STYPE_SYNC_VAR_VAL')
        elif self.stype == STYPE_SYNC_LHS_RHS:
            sb.append('xxx STYPE_SYNC_LHS_RHS')
        elif self.stype == STYPE_ASYNC_LHS_RHS:
            sb.append('xxx STYPE_ASYNC_LHS_RHS')
        else:
            raise Exception("Unhandled stype %s"%(self.stype))
        return ''.join(sb)


# --------------------------------------------------------
#   local scope
# --------------------------------------------------------
class LocalScope:

    def __init__(self, wandle_model, compile_container):
        self.wandle_model = wandle_model
        self.compile_container = compile_container

        self.d = {}
        self.d['self'] = self.compile_container.as_wandle_object(
            b_ready=True)

    def __repr__(self):
        return '<LocalScope %s>'%(self.d)

    def set(self, name, wandle_object):
        self.d[name] = wandle_object

    def get_compile_container(self):
        return self.compile_container

    def get_class(self, cstring):
        return self.compile_container.get_class(cstring=cstring)

    def get_async(self, mname):
        return self.compile_container.get_async(mname=mname)

    def get_sync(self, mname):
        if mname in self.d:
            return self.d[mname]
        elif mname in self.wandle_model.d_single:
            return self.wandle_model.d_single[mname]
        else:
            return self.compile_container.get_sync(mname=mname)


def resolve_dotref_async_rhs(lst_dotref, local_scope):
    '''
    Each of the items in the chain will be sync, but the last one should be
    async.

    This corresponds to the right-hand side of an asynchronous statement.
    '''
    context = local_scope

    # Synchronous search for early tokens.
    for (idx, mname) in enumerate(lst_dotref[:-1]):
        prev_context = context
        context = context.get_sync(mname=mname)
        if context == None:
            print(prev_context)
            raise Exception(
                "[%s] Could not find %s."%(
                    '.'.join(lst_dotref), mname))

    # Asynchronous search for the last token.
    prev_context = context
    mname = lst_dotref[-1]
    context = context.get_async(mname=mname)
    if context == None:
        print(prev_context)
        raise Exception(
            "[%s] Could not find %s."%(
                '.'.join(lst_dotref), mname))

    return context

def resolve_dotref_sync_only(lst_dotref, local_scope):
    '''
    Follow the dotref, lookup up synchronous members only.
    '''
    context = local_scope
    for (idx, mname) in enumerate(lst_dotref):
        prev_context = context
        context = context.get_sync(mname=mname)
        if context == None:
            print(prev_context)
            raise Exception(
                "[%s] Could not find %s."%(
                    '.'.join(lst_dotref), mname))
    return context

def populate_function(node, wandle_model, wandle_function):
    #
    # The grammar structure _cb_grammar contains a list of Statements. That
    # may be notes, variable definitions, synchronous calls, asynchronous
    # calls.
    #
    # This function interpreters and type-check each statement. Then, it
    # appends the statement to the local scope.
    #

    assert wandle_function.wtype == 'WandleFunction'

    # This is a working space into which we accumulate 
    # work through the statements in this method.
    local_scope = LocalScope(
        wandle_model=wandle_model,
        compile_container=wandle_function.compile_container)
    for param in wandle_function.lst_param:
        print(param)
        wandle_object = param.wandle_class.as_wandle_object()
        wandle_object.mark_ready()
        local_scope.set(
            name=param.name,
            wandle_object=wandle_object)

    # This is a var where we will keep track of whether we saw a valid return
    # or not. It is only relevant when we return non-Void.
    b_valid_return = False
    if wandle_function.rtype.name == 'Void':
        b_valid_return = True

    # Iterate through the code block node.
    for our_node in node[1:-1]:
        try:
            rule_name = our_node.rule_name
            if rule_name == '_cb_sync_copy':
                lhs_dotref = [n.value for n in our_node[0] if n != '.']
                rhs_dotref = [n.value for n in our_node[2] if n != '.']

                lhs_wandle_context = resolve_dotref_sync_only(
                    lst_dotref=lhs_dotref,
                    local_scope=local_scope)
                rhs_wandle_context = resolve_dotref_sync_only(
                    lst_dotref=rhs_dotref,
                    local_scope=local_scope)

                if lhs_wandle_context.wtype != 'WandleObject':
                    raise Exception(
                        "Invalid LHS. %s Can only assign to object."%(
                            lhs_wandle_context))

                if lhs_wandle_context.get_type() != rhs_wandle_context.get_type():
                    msg = ' '.join([
                        "Inconsistent type in copy statement",
                        "%s = %s."%(lhs_dotref, rhs_dotref),
                        "LHS is %s,"%(lhs_wandle_context.wandle_class),
                        "RHS is %s."%(rhs_wandle_context.wandle_class),
                    ])
                    raise SyntaxError(msg)

                # Assume that the call has been made, now we can mark the lhs
                # as having been set.
                lhs_wandle_context.mark_ready()

                statement = Statement(STYPE_SYNC_LHS_RHS)
                statement.wandle_class = lhs_wandle_context.wandle_class
                statement.lhs_dotref = lhs_dotref
                statement.rhs_dotref = rhs_dotref

                wandle_function.add_statement(statement)
            elif rule_name == '_cb_sync_from':
                lhs_dotref = [n.value for n in our_node[0] if n != '.']

                sync_call = our_node[1]
                rhs_dotref = [n.value for n in sync_call[1] if n != '.']

                lhs_wandle_context = resolve_dotref_sync_only(
                    local_scope=local_scope,
                    lst_dotref=lhs_dotref)
                rhs_wandle_context = resolve_dotref_sync_only(
                    local_scope=local_scope,
                    lst_dotref=rhs_dotref)

                if lhs_wandle_context.wtype == 'WandleVoid':
                    pass
                elif lhs_wandle_context.wtype != 'WandleObject':
                    raise Exception(
                        "Invalid LHS. %s Can only assign to object."%(
                            lhs_wandle_context))

                if lhs_wandle_context.get_type() != rhs_wandle_context.get_type():
                    msg = ' '.join([
                        "Inconsistent type in copy statement",
                        "%s = %s."%(lhs_dotref, rhs_dotref),
                        "LHS is %s,"%(lhs_wandle_context),
                        "RHS is %s."%(rhs_wandle_context),
                    ])
                    raise SyntaxError(msg)

                if rhs_wandle_context.wtype != 'WandleFunction':
                    print("Syntax error, |%s|"%(our_node))
                    msg = "RHS is not a function/method. (It is %s)."%(
                        rhs_wandle_context.wtype)
                    raise SyntaxError(msg)

                lst_param_node = [p for p in sync_call[2][1:-1] if p != ',']

                # Confirm that we have the correct number of params.
                if len(lst_param_node) != len(rhs_wandle_context.lst_param):
                    print("Syntax error, |%s|"%(our_node))
                    msg = "Incorrect number of params."
                    raise SyntaxError(msg)

                # Confirm that the param types are correct.
                for (idx, param_node) in enumerate(lst_param_node):
                    lst_dotref = [n.value for n in param_node if n != '.']
                    dotref = '.'.join(lst_dotref)

                    wandle_object = resolve_dotref_sync_only(
                        local_scope=local_scope,
                        lst_dotref=lst_dotref)
                    if wandle_object == None:
                        print("Syntax error, |%s|"%(our_node))
                        raise SyntaxError("There is no member |%s|."%(dotref))
                    elif wandle_object.wtype == 'WandleVoid':
                        pass
                    elif wandle_object.wtype == 'WandleObject':
                        if not wandle_object.is_ready():
                            raise Exception(
                                "Var %s has not been set."%(dotref))
                    else:
                        print("Syntax error, |%s|"%(our_node))
                        raise SyntaxError("Member %s is not a var."%(dotref))

                    ptype = wandle_object.get_type()
                    xtype = rhs_wandle_context.lst_param[idx].get_type()
                    if ptype != xtype:
                        print("Syntax error, |%s|"%(our_node))
                        raise SyntaxError(
                            "Param mismatch. Expected type %s, got %s"%(
                                xtype, ptype))

                # Assume that the call has been made, now we can mark the lhs
                # as having been set.
                lhs_wandle_context.mark_ready()

                statement = Statement(STYPE_SYNC_LHS_RHS)
                statement.wandle_class = lhs_wandle_context.wandle_class
                statement.lhs_dotref = lhs_dotref
                statement.rhs_dotref = rhs_dotref

                wandle_function.add_statement(statement)
            elif rule_name == '_cb_async_from':
                lhs_dotref = [n.value for n in our_node[0] if n != '.']

                async_call = our_node[1]
                rhs_dotref = [n.value for n in async_call[1] if n != '.']

                lhs_wandle_context = resolve_dotref_sync_only(
                    local_scope=local_scope,
                    lst_dotref=lhs_dotref)
                rhs_wandle_context = resolve_dotref_async_rhs(
                    local_scope=local_scope,
                    lst_dotref=rhs_dotref)

                if lhs_wandle_context.get_type() != rhs_wandle_context.get_type():
                    msg = ' '.join([
                        "Inconsistent type in copy statement",
                        "%s = %s."%(lhs_dotref, rhs_dotref),
                        "LHS is %s,"%(lhs_wandle_context.wandle_class.name),
                        "RHS is %s."%(rhs_wandle_context.wandle_class.name),
                    ])
                    raise SyntaxError(msg)

                if rhs_wandle_context.wtype != 'WandleFunction':
                    print("Syntax error, |%s|"%(our_node))
                    msg = "RHS is not a function/method. (It is %s)."%(
                        rhs_wandle_context.wtype)
                    raise SyntaxError(msg)

                lst_param_node = [p for p in async_call[2][1:-1] if p != ',']

                # Confirm that we have the correct number of params.
                if len(lst_param_node) != len(rhs_wandle_context.lst_param):
                    print("Syntax error, |%s|"%(our_node))
                    msg = "Incorrect number of params."
                    raise SyntaxError(msg)

                # Confirm that the param types are correct.
                for (idx, param_node) in enumerate(lst_param_node):
                    lst_dotref = [n.value for n in param_node if n != '.']
                    dotref = '.'.join(lst_dotref)

                    wandle_member = resolve_dotref_sync_only(
                        local_scope=local_scope,
                        lst_dotref=lst_dotref)
                    if wandle_member == None:
                        print("Syntax error, |%s|"%(our_node))
                        raise SyntaxError("There is no member |%s|."%(dotref))
                    elif wandle_member.wtype == 'WandleVoid':
                        pass
                    elif wandle_member.wtype == 'WandleObject':
                        pass
                    else:
                        print("Syntax error, |%s|"%(our_node))
                        raise SyntaxError("Member %s is not a var."%(dotref))

                    # Confirm that the param var is set as part of the if/elif block above.
                    pass # xxx investigate later

                    ptype = wandle_member.get_type()
                    xtype = rhs_wandle_context.lst_param[idx].get_type()
                    if ptype != xtype:
                        print("Syntax error, |%s|"%(our_node))
                        raise SyntaxError(
                            "Param mismatch. Expected type %s, got %s"%(
                                xtype, ptype))

                statement = Statement(STYPE_ASYNC_LHS_RHS)
                statement.wandle_class = lhs_wandle_context.wandle_class
                statement.lhs_dotref = lhs_dotref
                statement.rhs_dotref = rhs_dotref

                wandle_function.add_statement(statement)
            elif rule_name == '_cb_note':
                sb = []
                for sub in our_node[2:-1]:
                    sb.append(sub.value)
                txt = ' '.join(sb)

                statement = Statement(STYPE_NOTE_CONTENT)
                statement.txt = txt
                wandle_function.add_statement(statement)
            elif rule_name == '_cb_var_stub':
                cstring = our_node[0].value
                name = our_node[1].value

                wandle_class = local_scope.get_class(cstring=cstring)
                if wandle_class == None:
                    raise Exception("Class %s does not exist."%(cstring))

                wandle_object = wandle_class.as_wandle_object()
                local_scope.set(
                    name=name,
                    wandle_object=wandle_object)

                statement = Statement(STYPE_SYNC_VAR_NUL)
                statement.wandle_class = wandle_class
                statement.lhs_dotref = name
                wandle_function.add_statement(statement)
            elif rule_name == '_cb_var_ready':
                cstring = our_node[0].value
                name = our_node[1].value

                wandle_class = local_scope.get_class(cstring=cstring)
                wandle_object = wandle_class.as_wandle_object()
                wandle_object.mark_ready()
                local_scope.set(
                    name=name,
                    wandle_object=wandle_object)

                statement = Statement(STYPE_SYNC_VAR_VAL)
                statement.wandle_class = wandle_class
                statement.lhs_dotref = name
                wandle_function.add_statement(statement)
            elif rule_name == '_cb_return':
                # Type check the return against the scope we are in.
                #
                # This is what the method signature says we should return.
                sig_rtype_wandle_class = wandle_function.rtype

                # This is what we return.
                rhs_dotref = [n.value for n in our_node[1] if n != '.']
                rhs_wandle_context = resolve_dotref_sync_only(
                    lst_dotref=rhs_dotref,
                    local_scope=local_scope)
                got_rtype_wandle_class = rhs_wandle_context.wandle_class

                if sig_rtype_wandle_class != got_rtype_wandle_class:
                    raise Exception(
                        "Incorrect return type for method %s."%(
                            wandle_function.name))
                b_valid_return = True
            else:
                raise SyntaxError('rule_name %s is not handled'%(rule_name))
        except SyntaxError as e:
            sb = []
            for thing in our_node:
                sb.append(thing.value)
            print("[!] Syntax error in |%s|"%(' '.join(sb)))
            print(e.message)
            raise Exception("Syntax error. See log.")

    if not b_valid_return:
        raise Exception(
            "Method %s must return %s"%(
                wandle_function.name,
                wandle_function.rtype.name))


# --------------------------------------------------------
#   contexts
# --------------------------------------------------------
class WandleModel:
    # The Model does very little, and exists as a container for the root
    # scope. This also serves as a global scope for Void void.

    def __init__(self):
        self.parent_type_scope = None
        self.parent_runtime_scope = None

        self.wtype = self.__class__.__name__

        #
        # These vars related to Type.
        #
        # str vs WandleClass
        self.d_specific = {}
        # str vs WandleGeneric
        self.d_generic = {}
        # str vs str
        self.d_alias = {}

        #
        # These vars relate to Membership.
        #
        # str vs WandleFunction
        self.d_flow = {}
        # str vs WandleObject
        self.d_object = {}
        # str vs WandleSingle
        self.d_single = {}

        #
        # This is part of a hack that makes generics work. See
        # populate_specific_classes_derived_from_generics.
        #
        # str vs List<WandleObject>
        self.d_register = {}

        # Void void is automatically declared at the root level.
        self.__prep_void()

    def __repr__(self):
        return '<WandleModel>'

    def __prep_void(self):
        self.class_void = WandleClass(
            wandle_model=self,
            name='Void')
        self.d_specific['Void'] = self.class_void

        ob_void = WandleVoid(
            wandle_model=self)
        self.d_object['void'] = ob_void

    def __is_name_known(self, name):
        if name in self.d_specific: return True
        if name in self.d_generic: return True
        if name in self.d_flow: return True
        if name in self.d_object: return True
        if name in self.d_single: return True
        return False

    def stub_specific(self, name, b_placeholder=False):
        if self.__is_name_known(name) and not b_placeholder:
            raise Exception("Duplicate name definition, %s"%(name))

        wandle_class = WandleClass(
            wandle_model=self,
            name=name,
            b_placeholder=b_placeholder)
        self.d_specific[name] = wandle_class

    def stub_generic(self, name, lst_template_type):
        if self.__is_name_known(name):
            raise Exception("Duplicate name definition, %s"%(name))

        wandle_generic = WandleGeneric(
            wandle_model=self,
            name=name,
            lst_template_type=lst_template_type)
        self.d_generic[name] = wandle_generic

    def set_alias(self, name, tstring):
        if '/' in name:
            raise Exception(
                "Char / is not valid in an alias name. (%s)"%(
                    name))
        self.d_alias[name] = tstring

    def stub_single(self, name):
        if self.__is_name_known(name):
            raise Exception("Duplicate name definition, %s"%(name))

        wandle_single = WandleSingle(
            wandle_model=self,
            name=name)
        self.d_single[name] = wandle_single

    def stub_flow(self, name):
        if self.__is_name_known(name):
            raise Exception("Duplicate name definition, %s"%(name))

        compile_container = self
        b_is_async = True
        rtype = self.class_void
        lst_param = [] 
        wandle_function = WandleFunction(
            compile_container=compile_container,
            b_is_async=b_is_async,
            rtype=rtype,
            name=name,
            lst_param=lst_param)
        self.d_flow[name] = wandle_function

    def validate_alias_entries(self):
        for (aname, cstring) in self.d_alias.items():
            wandle_class = self.get_class(cstring=cstring)
            if wandle_class == None:
                raise Exception("Invalid type given for alias, %s"%(cstring))

    def register_object(self, wandle_object):
        # The reason we do this is related to needing to retrospectively
        # update objects-derived-from-generics during the compile process.
        type_name = wandle_object.get_type()
        if type_name not in self.d_register:
            self.d_register[type_name] = []
        self.d_register[type_name].append(wandle_object)

    def clear_register(self):
        self.d_register.clear()

    def populate_specific_classes_derived_from_generics(self):
        # Background: when we use alias to create a generic class, the
        # language automatically creates a class to represent that. But there
        # is a complication: we create them before we know the members of the
        # generic. Here, we update them with the appropriate contents, and
        # all WandleObject instances that were derived from that.
        for cstring in self.d_specific.keys():
            if '/' not in cstring:
                continue
            gname = cstring.split('/')[0]
            wandle_generic = self.get_generic(name=gname)
            wandle_class = wandle_generic.create_derived_class(
                cstring=cstring,
                type_scope=self)
            self.d_specific[cstring] = wandle_class

        for (cstring, lst) in self.d_register.items():
            wandle_class = self.get_class(cstring=cstring)
            for wandle_object in lst:
                for (name, wandle_function) in wandle_class.d_fab_sync.items():
                    wandle_object.set_fab_sync(
                        name=name,
                        wandle_function=wandle_function)
                for (name, wandle_function) in wandle_class.d_fab_async.items():
                    wandle_object.set_fab_async(
                        name=name,
                        wandle_function=wandle_function)
                for (name, sub) in wandle_class.d_object.items():
                    wandle_object.set_object(
                        name=name,
                        wandle_object=sub)

    def get_class(self, cstring):
        if cstring in self.d_alias:
            cstring = self.d_alias[cstring]

        if cstring in self.d_specific:
            return self.d_specific[cstring]
        elif '/' in cstring:
            # The first time we encounter a specialised-generic, we type check
            # it, create a derived type, and store that derivation in
            # d_specific so it is ready for future lookups.
            gname = cstring.split('/')[0]
            if gname not in self.d_generic:
                raise Exception("No generic exists for %s"%(gname))

            wandle_generic = self.d_generic[gname]
            type_scope = self
            wandle_class = wandle_generic.create_derived_class(
                cstring=cstring,
                type_scope=type_scope)
            self.d_specific[cstring] = wandle_class
            return wandle_class
        elif self.parent_type_scope != None:
            return self.parent_type_scope.get_class(cstring=cstring)
        else:
            return None

    def get_async(self, mname):
        if mname in self.d_flow:
            return self.d_flow[mname]
        else:
            return None

    def get_sync(self, mname):
        if mname in self.d_flow:
            raise Exception("%s found, but it is an (async!) flow."%(mname))
        elif mname in self.d_object:
            return self.d_object[mname]
        elif mname in self.d_single:
            return self.d_single[mname]
        else:
            return None

    def get_single(self, name):
        wandle_object = self.d_single[name]
        return wandle_object

    def get_generic(self, name):
        return self.d_generic[name]

    def as_wandle_object(self, b_ready=True):
        '''
        WandleModel can masquerage as a WandleObject. There is a kind of
        logic to it if you think about it: you can view the root of the
        tree as an object which itself contains everything else.

        It is a special-case of object, though, because it is where classes
        and generics are grounded.
        '''
        return self

    def as_code(self):
        sb = []
        for (name, wandle_object) in sorted(self.d_object.items()):
            sb.append(wandle_object.as_code(name))
            sb.append('')
        for (name, wandle_generic) in sorted(self.d_generic.items()):
            sb.append(wandle_generic.as_code(name=name))
            sb.append('')
        for (name, dst) in sorted(self.d_alias.items()):
            sb.append('alias %s to %s.'%(dst, name))
        if self.d_alias: sb.append('')
        for (name, wandle_single) in sorted(self.d_single.items()):
            sb.append(wandle_single.as_code())
            sb.append('')
        for (name, wandle_class) in sorted(self.d_specific.items()):
            if wandle_class.b_placeholder: continue
            if '/' in name: continue
            sb.append(wandle_class.as_code(name=name))
            sb.append('')
        for (name, wandle_function) in sorted(self.d_flow.items()):
            sb.append(wandle_function.as_code(name=name, b_flow=True))
            sb.append('')
        return '\n'.join(sb)


class WandleClass:

    def __init__(self, wandle_model, name, b_placeholder=False):
        self.wandle_model = wandle_model
        self.name = name
        self.b_placeholder = b_placeholder

        self.compile_container = wandle_model
        self.wtype = self.__class__.__name__

        # List<str>
        self.lst_inherits_from = []
        # Set<str>
        self.set_name = set()
        # str vs WandleFunction
        self.d_fab_async = {}
        # str vs WandleFunction
        self.d_fab_sync = {}
        # str vs WandleObject
        self.d_object = {}

    def __repr__(self):
        return '<WandleClass %s>'%(self.name)

    def __is_name_known(self, name):
        return name in self.set_name

    def get_type(self):
        return self.name

    def add_inherits_from(self, cname):
        self.lst_inherits_from.append(cname)

    def set_fab_async(self, name, wandle_function):
        self.d_fab_async[name] = wandle_function
        self.set_name.add(name)

    def set_fab_sync(self, name, wandle_function):
        self.d_fab_sync[name] = wandle_function
        self.set_name.add(name)

    def set_object(self, name, wandle_object):
        self.d_object[name] = wandle_object
        self.set_name.add(name)

    def get_class(self, cstring):
        return self.wandle_model.get_class(cstring=cstring)

    def get_async(self, mname):
        if mname in self.d_fab_async:
            return self.d_fab_async[mname]
        else:
            return self.compile_container.get_async(mname=mname)

    def get_sync(self, mname):
        if mname in self.d_fab_async:
            raise Exception("%s found, but it is an (async!) flow."%(mname))
        elif mname in self.d_fab_sync:
            return self.d_fab_sync[mname]
        elif mname in self.d_object:
            return self.d_object[mname]
        else:
            return self.compile_container.get_sync(mname=mname)

    def as_wandle_object(self, b_ready=False):
        wandle_object = WandleObject(
            compile_container=self,
            wandle_class=self)
        if b_ready:
            wandle_object.mark_ready()

        for (name, wandle_function) in self.d_fab_async.items():
            wandle_object.set_fab_async(
                name=name,
                wandle_function=wandle_function)
        for (name, wandle_function) in self.d_fab_sync.items():
            wandle_object.set_fab_sync(
                name=name,
                wandle_function=wandle_function)
        for (name, sub) in self.d_object.items():
            wandle_object.set_fab_sync(
                name=name,
                wandle_function=sub)

        # Now we track it in the model.
        self.wandle_model.register_object(wandle_object)

        return wandle_object

    def as_code(self, name):
        b_block = False
        if self.set_name:
            b_block = True

        sb = []
        if self.lst_inherits_from:
            csep = ','.join(self.lst_inherits_from)
            if b_block:
                sb.append('class %s is %s {'%(name, csep))
            else:
                return 'class %s is %s.'%(name, csep)
        else:
            if b_block:
                sb.append('class %s {'%(name))
            else:
                return 'class %s.'%(name)

        indent = 4
        for (name, wandle_object) in self.d_object.items():
            sb.append(wandle_object.as_code(indent=indent, name=name))
        for (name, wandle_function) in self.d_fab_async.items():
            sb.append(wandle_function.as_code(name=name, b_flow=False))
        for (name, wandle_function) in self.d_fab_sync.items():
            sb.append(wandle_function.as_code(name=name, b_flow=False))

        sb.append('}')
        return '\n'.join(sb)


class WandleGeneric:

    def __init__(self, wandle_model, name, lst_template_type):
        self.wandle_model = wandle_model
        self.name = name
        self.lst_template_type = lst_template_type

        self.wtype = self.__class__.__name__

        self.set_name = set()

        # str vs WandleFunction
        self.d_fab_async = {}
        # str vs WandleFunction
        self.d_fab_sync = {}
        # str vs WandleObject
        self.d_object = {}

    def __repr__(self):
        return '<WandleGeneric %s>'%(self.name)

    def __is_name_known(self, name):
        if name in self.d_fab_async: return True
        if name in self.d_fab_sync: return True
        if name in self.d_object: return True
        return False

    def add_template_type(self, name):
        if name in self.lst_template_type:
            raise Exception("Cannot have duplicate template type names.")
        self.lst_template_type.append(name)

    def create_derived_class(self, cstring, type_scope):
        lst_tok = [t for t in cstring.split('/') if len(t) > 0]
        if len(lst_tok) != 2:
            raise Exception("Invalid type string, %s"%(cstring))
        lst_template_type = lst_tok[1].split(',')

        if len(lst_template_type) != len(self.lst_template_type):
            raise Exception(
                "Wrong number of comma args. Got:%s, but generic is:%s/%s"%(
                    cstring, self.name, ','.join(self.scope.lst_template_type)))

        # Map the name of our template type to the name of the realised type.
        d_tt = {}
        for (idx, tt_name) in enumerate(self.lst_template_type):
            d_tt[tt_name] = lst_template_type[idx]

        wandle_class = WandleClass(
            wandle_model=self.wandle_model,
            name=cstring)
        for (name, wandle_function) in self.d_fab_async.items():
            wandle_function = wandle_function.generic_to_specific(
                d_tt=d_tt)
            wandle_class.set_fab_async(
                name=name,
                wandle_function=wandle_function)
        for (name, wandle_function) in self.d_fab_sync.items():
            wandle_function = wandle_function.generic_to_specific(
                d_tt=d_tt)
            wandle_class.set_fab_sync(
                name=name,
                wandle_function=wandle_function)
        for (name, wandle_object) in self.d_object.items():
            wandle_object = wandle_object.generic_to_specific(
                d_tt=d_tt)
            wandle_class.set_object(
                name=name,
                wandle_object=wandle_object)

        return wandle_class

    def set_fab_async(self, name, wandle_function):
        self.d_fab_async[name] = wandle_function
        self.set_name.add(name)

    def set_fab_sync(self, name, wandle_function):
        self.d_fab_sync[name] = wandle_function
        self.set_name.add(name)

    def set_object(self, name, wandle_object):
        self.d_object[name] = wandle_object
        self.set_name.add(name)

    def get_class(self, cstring):
        return self.wandle_model.get_class(cstring=cstring)

    def as_code(self, name):
        sb = []

        b_block = False
        if self.set_name:
            b_block = True

        csep = ','.join(self.lst_template_type)
        if b_block:
            sb.append('generic %s %s {'%(name, csep))
        else:
            return 'generic %s %s.'%(name, csep)

        indent = 4
        for (name, wandle_object) in self.d_object.items():
            sb.append(wandle_object.as_code(indent=indent, name=name))
        for (name, wandle_function) in self.d_fab_async.items():
            sb.append(wandle_function.as_code(name=name, b_flow=False))
        for (name, wandle_function) in self.d_fab_sync.items():
            sb.append(wandle_function.as_code(name=name, b_flow=False))

        sb.append('}')
        return '\n'.join(sb)


class WandleFunction:

    def __init__(self, compile_container, b_is_async, rtype, name, lst_param):
        self.compile_container = compile_container
        self.b_is_async = b_is_async
        self.rtype = rtype
        self.name = name
        self.lst_param = lst_param

        self.wtype = self.__class__.__name__

        self.lst_statement = []

    def __repr__(self):
        return '<WandleFunction %s %s>'%(self.rtype.name, self.name)

    def get_type(self):
        return self.rtype.name

    def is_async(self):
        return self.b_is_async

    def add_statement(self, statement):
        self.lst_statement.append(statement)

    def generic_to_specific(self, d_tt):
        '''
        Creates a clone instance of WandleFunction, with the generic
        types substituted for non-generic types. d_tt gives this mapping.
        '''
        rtype = self.rtype
        if rtype.get_type() in d_tt:
            cstring = d_tt[rtype.get_type()]
            rtype = self.compile_container.get_class(cstring=cstring)

        lst_param = []
        for param in self.lst_param:
            wandle_class = param.wandle_class
            name = param.name

            if wandle_class.get_type() in d_tt:
                cstring = d_tt[wandle_class.get_type()]
                wandle_class = self.compile_container.get_class(
                    cstring=cstring)

            new_param = Param(
                wandle_class=wandle_class,
                name=name)
            lst_param.append(new_param)

        wandle_function = WandleFunction(
            compile_container=self.compile_container,
            b_is_async=self.b_is_async,
            rtype=rtype,
            name=self.name,
            lst_param=lst_param)
        return wandle_function

    def as_code(self, name, b_flow):
        if b_flow: s_indent = ''
        else: s_indent = '    '

        if b_flow: t_string = 'flow'
        else: t_string = self.rtype.name

        csep = ', '.join( [str(p) for p in self.lst_param] )
        sb = []
        sb.append('%s%s %s(%s).'%(
            s_indent, t_string, name, csep))
        return '\n'.join(sb)


class WandleObject:

    def __init__(self, compile_container, wandle_class):
        self.compile_container = compile_container
        self.wandle_class = wandle_class

        self.wtype = self.__class__.__name__

        self.b_ready = False
        self.d_fab_async = {}
        self.d_fab_sync = {}
        self.d_object = {}

    def __repr__(self):
        return '<WandleObject %s>'%(self.wandle_class.name)

    def get_type(self):
        return self.wandle_class.name

    def get_async(self, mname):
        if mname in self.d_fab_async:
            return self.d_fab_async[mname]
        else:
            return self.compile_container.get_async(mname=mname)

    def get_sync(self, mname):
        if mname in self.d_fab_async:
            raise Exception("%s found, but it is async."%(mname))
        elif mname in self.d_fab_sync:
            return self.d_fab_sync[mname]
        elif mname in self.d_object:
            return self.d_object[mname]
        else:
            return self.compile_container.get_sync(mname=mname)

    def is_ready(self):
        return self.b_ready

    def mark_ready(self):
        self.b_ready = True

    def set_fab_async(self, name, wandle_function):
        self.d_fab_async[name] = wandle_function

    def set_fab_sync(self, name, wandle_function):
        self.d_fab_sync[name] = wandle_function

    def set_object(self, name, wandle_object):
        self.d_object[name] = wandle_object

    def generic_to_specific(self, d_tt):
        '''
        Creates a clone instance of WandleFunction, with the generic
        types substituted for non-generic types. d_tt gives this mapping.
        '''
        wandle_object = WandleObject(
            compile_container=self.compile_container,
            wandle_class=self.wandle_class)
        for (name, wff) in self.d_fab_async.items():
            wff = wff.generic_to_specific(
                d_tt=d_tt)
            wandle_object.set_fab_async(
                name=name,
                wandle_function=wff)
        for (name, wff) in self.d_fab_sync.items():
            wff = wff.generic_to_specific(
                d_tt=d_tt)
            wandle_object.set_fab_sync(
                name=name,
                wandle_function=wff)
        for (name, wfo) in self.d_object.items():
            # We are not doing generic-to-specific conversion for submembers.
            # I expect we will get away with not doing it for major use-cases.
            # If we come to do it, it will take some effort to avoid an
            # endless loop.
            wandle_object.set_object(
                name=name,
                wandle_object=wfo)
        return wandle_object

    def as_code(self, indent, name):
        s_indent = ' '*indent
        return '%s%s %s.'%(s_indent, self.wandle_class.name, name)


class WandleSingle:
    # This is effectively a container for a WandleObject. The thing that
    # is odd about a single is that it has a one-off class.

    def __init__(self, wandle_model, name):
        self.wandle_model = wandle_model
        self.name = name

        self.wtype = self.__class__.__name__

        name = 'Single|%s'%(name)
        self.wandle_model.stub_specific(name)
        self.wandle_class = self.wandle_model.get_class(cstring=name)
        self.wandle_object = self.wandle_class.as_wandle_object()

    def set_fab_async(self, name, wandle_function):
        self.wandle_class.set_fab_async(
            name=name,
            wandle_function=wandle_function)
        self.wandle_object.set_fab_sync(
            name=name,
            wandle_function=wandle_function)

    def set_fab_sync(self, name, wandle_function):
        self.wandle_class.set_fab_sync(
            name=name,
            wandle_function=wandle_function)
        self.wandle_object.set_fab_sync(
            name=name,
            wandle_function=wandle_function)

    def set_object(self, name, wandle_object):
        self.wandle_class.set_object(
            name=name,
            wandle_object=wandle_object)
        self.wandle_object.set_object(
            name=name,
            wandle_object=wandle_object)

    def get_class(self, cstring):
        return self.wandle_model.get_class(cstring=cstring)

    def get_async(self, mname):
        return self.wandle_object.get_async(mname)

    def get_sync(self, mname):
        return self.wandle_object.get_sync(mname)

    def as_wandle_object(self, b_ready=True):
        return self.wandle_object

    def as_code(self):
        indent = 4

        sb = []
        sb.append('single %s {'%(self.name))
        for (name, wandle_object) in self.wandle_class.d_object.items():
            sb.append(wandle_object.as_code(indent=indent, name=name))
        for (name, wandle_function) in self.wandle_class.d_fab_async.items():
            sb.append(wandle_function.as_code(name=name, b_flow=False))
        for (name, wandle_function) in self.wandle_class.d_fab_sync.items():
            sb.append(wandle_function.as_code(name=name, b_flow=False))
        sb.append('}')
        return '\n'.join(sb)


class WandleVoid:

    def __init__(self, wandle_model):
        self.wandle_model = wandle_model
        self.wtype = self.__class__.__name__

        self.name = 'Void'

        self.wandle_class = WandleClass(
            wandle_model=wandle_model,
            name=self.name)

    def get_type(self):
        return self.name

    def mark_ready(self):
        pass

    def as_code(self, name):
        return '\n'.join([
            "# Void is built-in."])


# --------------------------------------------------------
#   api
# --------------------------------------------------------
def wandle_model_build(parse_tree):
    wandle_model = WandleModel()

    #
    # :: First Pass
    #
    # Purpose: declare placeholders in the root level scope for class, generic
    # and single names. We also set aliases.
    #
    def first_pass(non_terminal):
        for node in non_terminal:
            rule_name = node.rule_name
            if rule_name == '_class_gram':
                name = node[0][1].value

                wandle_model.stub_specific(
                    name=name)
            elif rule_name == '_generic_gram':
                node = node[0]

                name = node[1].value
                _csep_caps = node[2]

                lst_template_type = []
                for cs in _csep_caps:
                    s = cs.value
                    if s == ',':
                        continue
                    lst_template_type.append(s)

                    wandle_model.stub_specific(name=s, b_placeholder=True)

                wandle_model.stub_generic(
                    name=name,
                    lst_template_type=lst_template_type)
            elif rule_name == '_single_gram':
                node = node[0]
                name = node[1].value

                wandle_model.stub_single(
                    name=name)
            elif rule_name == '_alias_gram':
                tstring = node[1].value
                name = node[3].value

                wandle_model.set_alias(name=name, tstring=tstring)
            elif rule_name == '_flow_gram':
                name = node[0][1].value

                wandle_model.stub_flow(name=name)
            elif rule_name == 'EOF':
                continue
            else:
                raise Exception("Unhandled, %s"%(rule_name))
    first_pass(parse_tree)

    #
    # :: Intermission: Type-check the alias entries
    #
    # If we had a type, 'List/Effect', this would check that we had defined
    # types for 'List' and 'Effect'.
    #
    wandle_model.validate_alias_entries()

    #
    # :: Second Pass
    #
    # Purpose: populate classes and generics with their immediate (i.e.
    # not-inherited) members.
    #
    context_stack = []
    def recurs(node):
        rule_name = node.rule_name
        if rule_name == '_grammar':
            for sub in node:
                recurs(sub)
        #
        elif rule_name == '_alias_gram':
            return
        elif rule_name == '_class_gram':
            sub = node[0]
            recurs(sub)
        elif rule_name == '_generic_gram':
            sub = node[0]
            recurs(sub)
        elif rule_name == '_single_gram':
            sub = node[0]
            recurs(sub)
        #
        elif rule_name in ('_class_base_stub', '_class_inh_stub'):
            return
        elif rule_name == '_class_base_impl':
            cstring = node[1].value
            sub = node[-1]

            wandle_class = wandle_model.get_class(cstring=cstring)
            context_stack.append(wandle_class)
            recurs(sub)
            context_stack.pop()
        elif rule_name == '_class_inh_impl':
            cstring = node[1].value
            node_interface_list = node[3]
            sub = node[-1]

            wandle_class = wandle_model.get_class(cstring=cstring)
            for (idx, inh_node) in enumerate(node_interface_list):
                if idx % 2 == 1:
                    continue

                inh_name = inh_node.value
                wandle_class.add_inherits_from(inh_name)

            context_stack.append(wandle_class)
            recurs(sub)
            context_stack.pop()
        #
        elif rule_name == '_generic_stub':
            return
        elif rule_name == '_generic_impl':
            name = node[1].value
            sub = node[3]

            wandle_generic = wandle_model.get_generic(name=name)
            context_stack.append(wandle_generic)
            recurs(sub)
            context_stack.pop()
        #
        elif rule_name == '_single_impl':
            name = node[1].value
            sub = node[2]

            wandle_single = wandle_model.get_single(name)

            context_stack.append(wandle_single)
            recurs(sub)
            context_stack.pop()
        #
        elif rule_name == '_cgs_block':
            for sub in node[1:-1]:
                recurs(sub)
        elif rule_name in ('_cgs_async_gram', '_cgs_sync_gram'):
            sub = node[0]
            recurs(sub)
        elif rule_name in ('_cgs_async_stub', '_cgs_async_impl'):
            wandle_context = context_stack[-1]

            cstring = node[1].value
            name = node[2].value
            method_sig = node[3]

            rtype = wandle_model.get_class(cstring=cstring)
            if rtype == None:
                raise Exception("Invalid return type %s. (%s)"%(cstring, node))

            lst_param = []
            for (idx, sig_pair) in enumerate(method_sig[1:-1]):
                if sig_pair.value == ',':
                    continue

                if len(sig_pair) != 2:
                    raise Exception("Invalid sig_pair |%s|"%(str(sig_pair)))

                param_cstring = sig_pair[0].value
                param_name = sig_pair[1].value

                wandle_class = wandle_model.get_class(
                    cstring=param_cstring)
                if wandle_class == None:
                    raise Exception(
                        "Wandle class %s does not exist."%(param_cstring))
                param = Param(
                    wandle_class=wandle_class,
                    name=param_name)
                lst_param.append(param)

            compile_container = wandle_context
            wandle_function = WandleFunction(
                compile_container=compile_container,
                b_is_async=True,
                rtype=rtype,
                name=name,
                lst_param=lst_param)
            wandle_context.set_fab_async(
                name=name,
                wandle_function=wandle_function)
        elif rule_name in ('_cgs_sync_stub', '_cgs_sync_impl'):
            wandle_context = context_stack[-1]

            cstring = node[1].value
            name = node[2].value
            method_sig = node[3]

            rtype = wandle_model.get_class(cstring=cstring)
            if rtype == None:
                raise Exception("Invalid return type %s. (%s)"%(cstring, node))

            lst_param = []
            for (idx, sig_pair) in enumerate(method_sig[1:-1]):
                if sig_pair.value == ',':
                    continue

                param_cstring = sig_pair[0].value
                param_name = sig_pair[1].value

                wandle_class = wandle_model.get_class(
                    cstring=param_cstring)
                if wandle_class == None:
                    raise Exception("Could not match %s"%(param_cstring))
                param = Param(
                    wandle_class=wandle_class,
                    name=param_name)
                lst_param.append(param)

            compile_container = wandle_context
            wandle_function = WandleFunction(
                compile_container=compile_container,
                b_is_async=False,
                rtype=rtype,
                name=name,
                lst_param=lst_param)

            wandle_context = context_stack[-1]
            wandle_context.set_fab_sync(
                name=name,
                wandle_function=wandle_function)
        elif rule_name in ('_cgs_var_stub', '_cgs_var_ready'):
            cstring = node[0].value
            name = node[1].value

            wandle_class = wandle_model.get_class(cstring=cstring)
            wandle_object = wandle_class.as_wandle_object()
            if rule_name == '_cgs_var_ready':
                wandle_object.mark_ready()

            wandle_context = context_stack[-1]
            wandle_context.set_object(
                name=name,
                wandle_object=wandle_object)
        elif rule_name == '_flow_gram':
            pass
        elif rule_name == 'EOF':
            pass
        else:
            raise Exception("rule_name |%s| not handled."%(rule_name))
    recurs(parse_tree)

    #
    # :: Intermission: update the contents of generic-derived classes.
    #
    # This is so they can pick up the contents that we processed above
    #
    wandle_model.populate_specific_classes_derived_from_generics()

    #
    # :: Intermission: build an inheritance hierarchy
    #
    # For each member that is in the parent and not the child, we make an
    # entry to the child pointing to the parent method implementation.
    #
    # This implementation is inefficient from a Big-O perspective. Revisit if
    # we bottleneck.
    #
    def build_class_inheritance_hierarchy():
        d_depend_on = {} # key depends on lst of values
        d_needed_by = {} # key is depended on by lst of values
        lst_cname_nodep = []
        set_cname_done = set()

        d_specific = wandle_model.d_specific

        # Populate d_depend_on
        for (cname, wclass) in d_specific.items():
            d_depend_on[cname] = [cstring for cstring in wclass.lst_inherits_from]

        # Populate d_needed_by
        for (cname, wclass) in d_specific.items():
            d_needed_by[cname] = []
        for (cname, wclass) in d_specific.items():
            for cstring in wclass.lst_inherits_from:
                d_needed_by[cstring].append(cname)

        # Populate lst_cname_nodep
        for (cname, wclass) in d_specific.items():
            if not wclass.lst_inherits_from:
                lst_cname_nodep.append(cname)

        # Progressively process items from lst_cname_nodep into
        # lst_cname_done.
        while True:
            if len(lst_cname_nodep) == 0:
                break

            for child_cname in lst_cname_nodep:
                child_wcs = d_specific[child_cname]
                for parent_cname in d_depend_on[child_cname]:
                    parent_wcs = d_specific[parent_cname]
                    for (mname, wandle_function) in parent_wcs.d_fab_async.items():
                        if mname not in child_wcs.set_name:
                            child_wcs.set_fab_async(
                                name=mname,
                                wandle_function=wandle_function)
                    for (mname, wandle_function) in parent_wcs.d_fab_sync.items():
                        if mname not in child_wcs.set_name:
                            child_wcs.set_fab_sync(
                                name=mname,
                                wandle_function=wandle_function)
                    for (mname, wandle_object) in parent_wcs.d_object.items():
                        if mname not in child_wcs.set_name:
                            child_wcs.set_object(
                                name=mname,
                                wandle_object=wandle_object)

            for cname in lst_cname_nodep:
                set_cname_done.add(cname)

            # Prepare lst_cname_nodep ahead of the next loop
            lst_old = lst_cname_nodep
            lst_cname_nodep = []
            for done_cname in lst_old:
                for candidate_cname in d_needed_by[done_cname]:
                    b_ok = True
                    for other_cname in d_depend_on[candidate_cname]:
                        if other_cname not in set_cname_done:
                            b_ok = False
                            break
                    if b_ok:
                        lst_cname_nodep.append(candidate_cname)

        if len(set_cname_done) != len(d_specific):
            raise Exception(
                "Did not process enough entries. %s/%s"%(
                    len(set_cname_done), len(d_class_specific)))
    build_class_inheritance_hierarchy()

    #
    # :: Third Pass
    #
    # Harvest source code blocks into Functions and Statements.
    #
    stack = [wandle_model]
    def recurs(node):
        rule_name = node.rule_name
        if rule_name == '_grammar':
            # This is the top-level block.
            for sub in node:
                recurs(sub)
        elif rule_name == '_alias_gram':
            pass
        elif rule_name == '_class_gram':
            # This is an aggregate form. We recurse to the specialisation.
            sub = node[0]
            recurs(sub)
        elif rule_name == '_generic_gram':
            # This is an aggregate form. We recurse to the specialisation.
            sub = node[0]
            recurs(sub)
        elif rule_name == '_single_gram':
            # This is an aggregate form. We recurse to the specialisation.
            sub = node[0]
            recurs(sub)
        elif rule_name == '_flow_gram':
            sub = node[0]
            recurs(sub)
        elif rule_name in ('_class_base_stub', '_class_inh_stub'):
            pass
        elif rule_name in ('_class_base_impl', '_class_inh_impl'):
            cname = node[1].value
            sub = node[-1]

            wandle_class = stack[-1].d_specific[cname]
            stack.append(wandle_class)
            recurs(sub)
            stack.pop()
        elif rule_name == '_generic_stub':
            pass
        elif rule_name == '_generic_impl':
            fname = node[1].value
            sub = node[3]

            wandle_generic = stack[-1].d_generic[fname]
            stack.append(wandle_generic)
            recurs(sub)
            stack.pop()
        elif rule_name == '_single_impl':
            sname = node[1].value
            sub = node[2]

            wandle_single = stack[-1].d_single[sname]
            stack.append(wandle_single)
            recurs(sub)
            stack.pop()
        elif rule_name == '_cgs_block':
            # get rid of parens
            lst_entry = node[1:-1]

            for sub in lst_entry:
                recurs(sub)
        elif rule_name in ('_cgs_sync_gram', '_cgs_async_gram'):
            sub = node[0]
            recurs(sub)
        elif rule_name in ('_cgs_var_stub', '_cgs_sync_stub', '_cgs_async_stub', '_cgs_var_ready'):
            pass
        elif rule_name in ('_cgs_async_impl'):
            mname = node[2].value
            sub = node[-1]

            wandle_container = stack[-1]
            member = wandle_container.get_async(mname)
            stack.append(member)
            recurs(sub)
            stack.pop()
        elif rule_name in ('_cgs_sync_impl'):
            mname = node[2].value
            sub = node[-1]

            wandle_container = stack[-1]
            member = wandle_container.get_sync(mname)
            stack.append(member)
            recurs(sub)
            stack.pop()
        elif rule_name == '_cgs_sync_stub':
            pass
        elif rule_name == '_flow_impl':
            flow_name = node[1].value
            sub = node[2]

            wandle_flow = wandle_model.d_flow[flow_name]
            stack.append(wandle_flow)
            recurs(sub)
            stack.pop()
        elif rule_name == '_cb_grammar':
            wandle_function = stack[-1]
            populate_function(
                node=node,
                wandle_model=wandle_model,
                wandle_function=wandle_function)
        elif rule_name == 'EOF':
            pass
        else:
            raise Exception("rule_name %s not handled."%(rule_name))
    recurs(parse_tree)

    return wandle_model
