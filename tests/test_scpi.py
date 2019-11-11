import pytest

from scpi import sanitize_msgs, min_max_cmd, cmd_expr_to_reg_expr
from scpi import (
    Commands,
    COMMANDS,
    Cmd,
    FuncCmd,
    IntCmd,
    IntCmdR,
    IntCmdW,
    FloatCmdR,
    StrCmdR,
    IDNCmd,
    ErrCmd,
)


def test_sanitize_msgs():
    r = sanitize_msgs("*rst", "*idn?;*cls")
    assert r == (["*rst", "*idn?", "*cls"], ["*idn?"], "*rst\n*idn?\n*cls\n")

    r = sanitize_msgs("*rst", "*idn?;*cls", eol="\r\n")
    assert r == (["*rst", "*idn?", "*cls"], ["*idn?"], "*rst\r\n*idn?\r\n*cls\r\n")

    r = sanitize_msgs("*rst", "*idn?;*cls", strict_query=False)
    assert r == (["*rst", "*idn?", "*cls"], ["*idn?"], "*rst\n*idn?;*cls\n")

    r = sanitize_msgs("*rst", "*idn?;*cls", strict_query=False)
    assert r == (["*rst", "*idn?", "*cls"], ["*idn?"], "*rst\n*idn?;*cls\n")


def test_min_max_cmd():
    assert min_max_cmd("*OPC") == ("*OPC", "*OPC")
    assert min_max_cmd(":*OPC") == ("*OPC", "*OPC")
    assert min_max_cmd("SYSTem:ERRor[:NEXT]") == ("SYST:ERR", "SYSTEM:ERROR:NEXT")
    assert min_max_cmd("MEASure[:CURRent[:DC]]") == ("MEAS", "MEASURE:CURRENT:DC")
    assert min_max_cmd("[SENSe[1]:]CURRent[:DC]:RANGe[:UPPer]") == (
        "CURR:RANG",
        "SENSE1:CURRENT:DC:RANGE:UPPER",
    )


def test_cmd_expr_to_reg_expr():
    cmd_exprs = {
        "idn": ("*IDN", "\\:?\\*IDN$"),
        "err": ("SYSTem:ERRor[:NEXT]", "\\:?SYST(EM)?\\:ERR(OR)?(\\:NEXT)?$"),
        "meas": ("MEASure[:CURRent[:DC]]", "\\:?MEAS(URE)?(\\:CURR(ENT)?(\\:DC)?)?$"),
        "rupper": (
            "[SENSe[1]:]CURRent[:DC]:RANGe[:UPPer]",
            "\\:?(SENS(E)?(1)?\\:)?CURR(ENT)?(\\:DC)?\\:RANG(E)?(\\:UPP(ER)?)?$",
        ),
    }

    for _, (expr, reg_expr) in list(cmd_exprs.items()):
        assert cmd_expr_to_reg_expr(expr).pattern == reg_expr

    cmd_re = dict(
        [(k, cmd_expr_to_reg_expr(expr)) for k, (expr, _) in list(cmd_exprs.items())]
    )

    idn_re = cmd_re["idn"]
    assert idn_re.match("*IDN")
    assert idn_re.match("*idn")
    assert not idn_re.match("IDN")

    def test_cmd(name, match, no_match):
        reg_expr = cmd_re[name]
        for m in match:
            assert reg_expr.match(m), "{0}: {1} does not match {2}".format(
                name, m, cmd_exprs[name][0]
            )
        for m in no_match:
            assert not reg_expr.match(m), "{0}: {1} matches {2}".format(
                name, m, cmd_exprs[name][0]
            )

    test_cmd("idn", ("*IDN", "*idn", "*IdN"), ("IDN", " *IDN", "**IDN", "*IDN "))

    test_cmd(
        "err",
        ("SYST:ERR", "SYSTEM:ERROR:NEXT", "syst:error", "system:err:next"),
        ("sys", "syst:erro", "system:next"),
    )

    test_cmd(
        "err",
        ("SYST:ERR", "SYSTEM:ERROR:NEXT", "syst:error", "system:err:next"),
        ("sys", "syst:erro", "system:next"),
    )

    test_cmd(
        "rupper",
        ("CURR:RANG", "SENS:CURR:RANG:UPP", "SENSE1:CURRENT:DC:RANGE:UPPER"),
        ("sense:curren:rang", "sens1:range:upp"),
    )


def test_commands():
    cmd_dict = {
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
            "*TST": Cmd(get=lambda x: not decode_OnOff(x), doc="self-test query"),
            "*WAI": FuncCmd(doc="wait to continue"),
            "SYSTem:ERRor[:NEXT]": ErrCmd(doc="return and clear oldest system error"),
    }

    commands = Commands(cmd_dict,
        {"MEASure[:CURRent[:DC]]": FloatCmdR(get=lambda x: float(x[:-1]))},
    )
    keys = set(cmd_dict).union({"MEASure[:CURRent[:DC]]"})

    assert "*idn" in commands
    assert commands["*idn"] is commands["*IDN"]
    assert commands.get("idn") == None
    assert "SYST:ERR" in commands
    assert "SYSTEM:ERROR:NEXT" in commands
    assert "syst:error" in commands
    assert commands["SYST:ERR"] is commands["system:error:next"]
    assert commands["MEAS"] is commands["measure:current:dc"]
    assert len(commands) == len(cmd_dict)+1
    assert set(commands.keys()) == keys

    assert commands.get_command(":*idn")["min_command"] == "*IDN"
    assert commands.get_command("system:error:next")["min_command"] == "SYST:ERR"

    with pytest.raises(KeyError) as err:
        commands["IDN"]
    assert "IDN" in str(err.value)
