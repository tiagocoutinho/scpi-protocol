import re
import inspect
from functools import partial
from collections import namedtuple

import numpy

__version__ = '0.2.0'


def decode_IDN(s):
    manuf, model, serial, version = map(str.strip, s.split(","))
    return dict(manufacturer=manuf, model=model, serial=serial, version=version)


def __decode_Err(s):
    code, desc = map(str.strip, s.split(",", 1))
    return dict(code=int(code), desc=desc[1:-1])


def __decode_ErrArray(s):
    msgs = list(map(str.strip, s.split(",")))
    result = []
    for i in range(0, len(msgs), 2):
        code, desc = int(msgs[i]), msgs[i + 1][1:-1]
        if code == 0:
            continue
        result.append(dict(code=code, desc=desc))
    return result


def __decode_OnOff(s):
    su = s.upper()
    if su in ("1", "ON"):
        return True
    elif su in ("0", "OFF"):
        return False
    else:
        raise ValueError("Cannot decode OnOff value {0}".format(s))


def __encode_OnOff(s):
    if s in (0, False, "off", "OFF"):
        return "OFF"
    elif s in (1, True, "on", "ON"):
        return "ON"
    else:
        raise ValueError("Cannot encode OnOff value {0}".format(s))


__decode_IntArray = partial(numpy.fromstring, dtype=int, sep=",")
__decode_FloatArray = partial(numpy.fromstring, dtype=float, sep=",")

#: SCPI command
#: accepts the following keys:
#:
#:   - get - translation function called on the result of a query.
#:           If not present means command cannot be queried.
#:           If present and is None means ignore query result
#:   - set - translation function called before a write.
#:           If not present means command cannot be written.
#:           If present and is None means it doesn't receive any argument
#:   - doc - command documentation (str, optional)
Cmd = dict

FuncCmd = partial(Cmd, set=None)

IntCmd = partial(Cmd, get=int, set=str)
IntCmdR = partial(Cmd, get=int)
IntCmdW = partial(Cmd, set=str)

FloatCmd = partial(Cmd, get=float, set=str)
FloatCmdR = partial(Cmd, get=float)
FloatCmdW = partial(Cmd, set=str)

StrCmd = partial(Cmd, get=str, set=str)
StrCmdR = partial(Cmd, get=str)
StrCmdW = partial(Cmd, set=str)

IntArrayCmdR = partial(Cmd, get=__decode_IntArray)
FloatArrayCmdR = partial(Cmd, get=__decode_FloatArray)
StrArrayCmd = partial(Cmd, get=lambda x: x.split(","), set=lambda x: ",".join(x))
StrArrayCmdR = partial(Cmd, get=lambda x: x.split(","))

OnOffCmd = partial(Cmd, get=__decode_OnOff, set=__encode_OnOff)
OnOffCmdR = partial(Cmd, get=__decode_OnOff)
OnOffCmdW = partial(Cmd, set=__encode_OnOff)
BoolCmd = OnOffCmd
BoolCmdR = OnOffCmdR
BoolCmdW = OnOffCmdW

IDNCmd = partial(Cmd, get=decode_IDN, doc="identification query")

ErrCmd = partial(Cmd, get=__decode_Err)
ErrArrayCmd = partial(Cmd, get=__decode_ErrArray)


def min_max_cmd(cmd_expr):
    """
    Find the shortest and longest version of a SCPI command expression

    Example::

    >>> min_max_cmd('SYSTem:ERRor[:NEXT]')
    ('SYST:ERR', 'SYSTEM:ERROR:NEXT')
    """
    result_min, optional = "", 0
    for c in cmd_expr:
        if c.islower():
            continue
        if c == "[":
            optional += 1
            continue
        if c == "]":
            optional -= 1
            continue
        if optional:
            continue
        result_min += c
    result_min = result_min.lstrip(":")
    result_max = cmd_expr.replace("[", "").replace("]", "").upper().lstrip(":")
    return result_min, result_max


def cmd_expr_to_reg_expr_str(cmd_expr):
    """
    Return a regular expression string from the given SCPI command expression.
    """
    # Basicaly we replace [] -> ()?, and LOWercase -> LOW(ercase)?
    # Also we add :? optional to the start and $ to the end to make sure
    # we have an exact match
    reg_expr, low_zone = r"\:?", False
    for c in cmd_expr:
        cl = c.islower()
        if not cl:
            if low_zone:
                reg_expr += ")?"
            low_zone = False
        if c == "[":
            reg_expr += "("
        elif c == "]":
            reg_expr += ")?"
        elif cl:
            if not low_zone:
                reg_expr += "("
            low_zone = True
            reg_expr += c.upper()
        elif c in "*:":
            reg_expr += "\\" + c
        else:
            reg_expr += c

    # if cmd expr ends in lower case we close the optional zone 'by hand'
    if low_zone:
        reg_expr += ")?"

    return reg_expr + "$"


def cmd_expr_to_reg_expr(cmd_expr):
    """
    Return a compiled regular expression object from the given SCPI command
    expression.
    """
    return re.compile(cmd_expr_to_reg_expr_str(cmd_expr), re.IGNORECASE)


class Commands(object):
    """
    A dict like container for SCPI commands. Construct a Commands object like a
    dict.  When creating a Commands object, *args* must either:

    * another *Commands* object
    * a dict where keys should be SCPI command expressions
      (ex: `SYSTem:ERRor[:NEXT]`). Values can be any python objects
      Common use-case is instance of *Cmd* which contain information on how to
      handle a get/set operation and optional docstrings
    * a sequence of pairs where first element must be SCPI command expression
      and second element is any python object

    *kwargs* should also be SCPI command expressions;

    The same way, assignment keys should be SCPI command expressions and
    assignment values can be any python object.

    Examples::

        from bliss.comm.scpi import FuncCmd, ErrCmd, IntCmd, Commands

        # c1 will only have *CLS command
        c1 = Commands({'*CLS': FuncCmd(doc='clear status'),
                       '*RST': FuncCmd(doc='reset')})

        # c2 will have *CLS and VOLTage commands
        c2 = Commands(c1, VOLTage=IntCmd())

        # add error command to c2
        c2['SYSTem:ERRor[:NEXT]'] = ErrCmd()

    Access to a command will return the same python object for any text
    that resolves to the same SCPI command::

        >>> c2['SYST:ERR']
        <ErrCmd at 0x7f3f663bf390>
        >>> c2[':system:error:next']
        <ErrCmd at 0x7f3f663bf390>
        >>> c2[':system:error:next'] == c2['SYST:ERR']
        True
    """

    def __init__(self, *args, **kwargs):
        self.command_expressions = {}
        self._command_cache = {}
        for arg in args:
            self.update(arg)
        self.update(kwargs)

    def __setitem__(self, cmd_expr, command):
        min_cmd, max_cmd = min_max_cmd(cmd_expr)
        cmd_info = dict(
            value=command,
            re=cmd_expr_to_reg_expr(cmd_expr),
            min_command=min_cmd,
            max_command=max_cmd,
        )
        self.command_expressions[cmd_expr] = cmd_info
        # update cache with short and long version
        self.get_command_expression(min_cmd)
        self.get_command_expression(max_cmd)
        return cmd_info

    def __getitem__(self, cmd_name):
        return self.get_command(cmd_name)['value']

    def __delitem__(self, cmd_expr):
        reg_expr = self.command_expressions.pop(cmd_expr)['re']
        del_cache = {k for k, v in self._command_cache.items()
                     if reg_expr.match(k)}
        for k in del_cache:
            del self._command_cache[k]

    def __contains__(self, cmd_name):
        return self.get(cmd_name) is not None

    def __len__(self):
        return len(self.command_expressions)

    def clear(self):
        self.command_expressions.clear()
        self._command_cache.clear()

    def keys(self):
        return self.command_expressions.keys()

    def values(self):
        return {k:v['value'] for k, v in self.command_expressions.items()}.values()

    def get_command(self, cmd_name):
        cmd_expr = self.get_command_expression(cmd_name)
        return self.command_expressions[cmd_expr]

    def get_command_expression(self, cmd_name):
        cmd_name_u = cmd_name.upper()
        try:
            return self._command_cache[cmd_name_u]
        except KeyError:
            for cmd_expr, cmd_info in self.command_expressions.items():
                reg_expr = cmd_info["re"]
                if reg_expr.match(cmd_name):
                    self._command_cache[cmd_name.upper()] = cmd_expr
                    return cmd_expr
        raise KeyError(cmd_name)

    def get(self, cmd_name, default=None):
        try:
            return self[cmd_name]
        except KeyError:
            return default

    def update(self, commands):
        if isinstance(commands, Commands):
            self.command_expressions.update(commands.command_expressions)
            self._command_cache.update(commands._command_cache)
        elif isinstance(commands, dict):
            for cmd_expr, cmd in commands.items():
                self[cmd_expr] = cmd
        else:
            for cmd_expr, cmd in commands:
                self[cmd_expr] = cmd


COMMANDS = Commands(
    {
        "*CLS": FuncCmd(doc="clear status"),
        "*ESE": IntCmd(doc="standard event status enable register"),
        "*ESR": IntCmdR(doc="standard event event status register"),
        "*IDN": IDNCmd(),
        "*OPC": IntCmdR(set=None, doc="operation complete"),
        "*OPT": IntCmdR(doc="return model number of any installed options"),
        "*RCL": IntCmdW(set=int, doc="return to user saved setup"),
        "*RST": FuncCmd(doc="reset"),
        "*SAV": IntCmdW(doc="save the preset setup as the user-saved setup"),
        "*SRE": IntCmdW(doc="service request enable register"),
        "*STB": StrCmdR(doc="status byte register"),
        "*TRG": FuncCmd(doc="bus trigger"),
        "*TST": Cmd(get=lambda x: not __decode_OnOff(x), doc="self-test query"),
        "*WAI": FuncCmd(doc="wait to continue"),
        "SYSTem:ERRor[:NEXT]": ErrCmd(doc="return and clear oldest system error"),
    }
)


class SCPIError(Exception):
    """
    Base :term:`SCPI` error
    """


def sanitize_msgs(*msgs, eol='\n', sep=';', strict_query=True):
    """
    Transform a tuple of messages into a list  of
    (<individual commands>, <individual queries>, <full_message>):

    if strict_query=True, sep=';', eol='\n' (default):
        msgs = ('*rst', '*idn?;*cls') =>
            (['*RST', '*IDN?', '*CLS'], ['*IDN?'], '*RST\n*IDN?\n*CLS')

    if strict_query=False, sep=';', eol='\n' (default):
        msgs = ('*rst', '*idn?;*cls') =>
            (['*RST', '*IDN?', '*CLS'], ['*IDN?'], '*RST\n*IDN?;*CLS')
    """
    # in case a single message comes with several eol separated commands
    msgs = eol.join(msgs).split(eol)
    result, commands, queries = [], [], []
    for msg in msgs:
        sub_result = []
        for cmd in msg.split(sep):
            cmd = cmd.strip()
            if not cmd:
                continue
            commands.append(cmd)
            is_query = "?" in cmd
            if is_query:
                queries.append(cmd)
            if is_query and strict_query:
                if sub_result:
                    result.append(sep.join(sub_result))
                    sub_result = []
                result.append(cmd)
            else:
                sub_result.append(cmd)
        if sub_result:
            result.append(sep.join(sub_result))
    return commands, queries, eol.join(result) + eol


Request = namedtuple('Request', 'name args query')


def split_line(line, sep=';'):
    line = line.strip().strip(';')
    requests = []
    for req_str in line.split(sep):
        if not req_str:
            continue
        query = '?' in req_str
        req_str = req_str.replace('?', '')
        name, _, args = req_str.partition(' ')
        name, args = name.strip(), args.strip()
        requests.append(Request(name, args, query))
    return requests
