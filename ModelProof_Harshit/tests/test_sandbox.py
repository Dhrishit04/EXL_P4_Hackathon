import textwrap
from pathlib import Path

import pytest

from modelproof import sandbox

OK = """
import math
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

def f(df: pd.DataFrame) -> float:
    return float(np.log(df.x).sum()) + math.pi
"""


@pytest.mark.parametrize(
    "snippet",
    [
        "import os",
        "import subprocess",
        "from pathlib import Path",
        "import requests",
        "import importlib",
        "eval('1')",
        "exec('x = 1')",
        "compile('1', 'f', 'eval')",
        "open('/etc/passwd')",
        "__import__('os')",
        "x = (1).__class__",
        "getattr(object, 'sub' + 'classes')",
        "import pandas as pd\npd.read_csv('/etc/passwd')",
        "import numpy as np\nnp.load('x.npy')",
        "import pandas as pd\npd.DataFrame().to_pickle('x')",
    ],
)
def test_malicious_or_io_code_is_rejected(snippet):
    assert sandbox.check_code(snippet)


def test_numeric_code_with_allowed_imports_passes():
    assert sandbox.check_code(OK) == []


def test_syntax_error_is_a_violation():
    assert sandbox.check_code("def (")


def test_extra_allowed_imports_are_explicit():
    assert sandbox.check_code("import pytest")
    assert sandbox.check_code("import pytest", allow=("pytest",)) == []


def write(d: Path, name: str, body: str) -> None:
    (d / name).write_text(textwrap.dedent(body))


def test_run_pytest_passes_and_fails(tmp_path):
    write(tmp_path, "test_a.py", "def test_a():\n    assert 1 + 1 == 2\n")
    ok, out = sandbox.run_pytest(tmp_path)
    assert ok and "1 passed" in out
    write(tmp_path, "test_a.py", "def test_a():\n    assert 1 + 1 == 3\n")
    ok, out = sandbox.run_pytest(tmp_path)
    assert not ok and "1 failed" in out


def test_run_pytest_imports_the_module_next_to_the_tests(tmp_path):
    write(tmp_path, "cr_pd_002.py", "VALUE = 7\n")
    write(tmp_path, "test_m.py", "import cr_pd_002\n\ndef test_m():\n    assert cr_pd_002.VALUE == 7\n")
    assert sandbox.run_pytest(tmp_path)[0]


def test_run_pytest_times_out(tmp_path):
    write(tmp_path, "test_slow.py", "import time\n\ndef test_slow():\n    time.sleep(30)\n")
    ok, out = sandbox.run_pytest(tmp_path, timeout=2)
    assert not ok and "timed out" in out


def test_run_pytest_strips_secrets_from_the_environment(tmp_path, monkeypatch):
    for k in ("MY_API_KEY", "GH_TOKEN", "DB_SECRET"):
        monkeypatch.setenv(k, "leak")
    write(tmp_path, "test_env.py", """
        import os

        def test_env():
            assert not [k for k in os.environ if k.endswith(("_KEY", "_TOKEN", "_SECRET"))]
    """)
    assert sandbox.run_pytest(tmp_path)[0]


def test_only_named_type_hint_imports_are_allowed():
    assert sandbox.check_code("from __future__ import annotations\nfrom typing import Callable, Optional\n") == []


@pytest.mark.parametrize(
    "snippet",
    [
        "import typing",
        "from typing import get_type_hints",
        "from typing import ForwardRef",
        "from typing import sys",
        "import typing as t\nt.sys.modules",
        "import numpy as np\nnp.ctypeslib",
        "import pandas as pd\npd.io.common.get_handle",
        "import numpy as np\nnp._core",
    ],
)
def test_module_reexports_and_unnamed_typing_imports_are_rejected(snippet):
    assert sandbox.check_code(snippet)


@pytest.mark.parametrize(
    "test_code",
    [
        "import pytest\n\ndef test_x():\n    pytest.importorskip('os')\n",
        "def test_x(monkeypatch):\n    monkeypatch.setattr('os.system', print)\n",
        "def test_x(request):\n    request.getfixturevalue('x')\n",
    ],
)
def test_generated_tests_cannot_reach_pytest_or_its_fixtures(test_code):
    assert sandbox.check_tests(test_code)


def test_plain_generated_tests_on_the_module_are_allowed():
    assert sandbox.check_tests("import numpy as np\nimport cr_pd_002 as m\n\ndef test_x():\n    assert np.isnan(m.f())\n") == []


@pytest.mark.parametrize(
    "snippet",
    [
        "from pandas import io",
        "from numpy import testing",
        "from numpy import ctypeslib",
        "from scipy import io",
        "import scipy.io",
        "from numpy import *",
        "import statsmodels.formula.api as smf",
        "from statsmodels.formula.api import ols",
        "import statsmodels.api as sm\nsm.OLS.from_formula('y ~ x', None)",
        "import pandas as pd\npd.DataFrame().query('a > 1')",
    ],
)
def test_import_aliases_star_imports_and_string_evaluated_apis_are_rejected(snippet):
    assert sandbox.check_code(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        "import pandas as pd\npd.DataFrame().agg('to_csv', path_or_buf='x')",
        "import pandas as pd\npd.Series([1]).apply('__len__')",
        "import pandas as pd\npd.DataFrame().agg(['sum', 'to_pickle'])",
        "import pandas as pd\npd.DataFrame().agg({'a': 'to_csv'})",
        "import pandas as pd\npd.DataFrame().transform(func='to_json')",
        "import pandas as pd\npd.Series([1]).map('to_csv')",
    ],
)
def test_string_dispatch_to_methods_by_name_is_rejected(snippet):
    assert sandbox.check_code(snippet)


def test_reducer_names_and_callables_are_fine_in_agg_and_apply():
    code = "import pandas as pd\nd = pd.DataFrame({'a': [1]})\nd.groupby('a').agg({'a': 'sum'})\nd.agg('mean')\nd.apply(lambda r: r)\n"
    assert sandbox.check_code(code) == []


@pytest.mark.parametrize(
    "snippet",
    [
        "import pandas as pd\nd = pd.DataFrame()\nd.agg(*['to_csv'])",
        "import pandas as pd\nd = pd.DataFrame()\nd.agg(**{'func': 'to_csv'})",
        "import pandas as pd\nd = pd.DataFrame()\npd.DataFrame.agg(d, 'to_csv')",
        "import pandas as pd\nd = pd.DataFrame()\nd.agg(''.join(['to', '_csv']))",
        "import pandas as pd\nd = pd.DataFrame()\nd.pivot_table(index='a', aggfunc='to_csv')",
        "import pandas as pd\nd = pd.DataFrame()\npd.crosstab(d.a, d.b, aggfunc=['to_csv'])",
        "import pandas as pd\nd = pd.DataFrame()\nd.groupby('a').agg(n=('b', 'to_csv'))",
    ],
)
def test_dispatch_calls_are_deny_by_default(snippet):
    assert sandbox.check_code(snippet)


def test_named_aggregation_pivot_and_apply_with_callables_stay_allowed():
    code = ("import numpy as np\nimport pandas as pd\nd = pd.DataFrame({'a': [1], 'b': [1]})\n"
            "d.groupby('a').agg(n=('b', 'size'), s=('b', np.sum))\nd.pivot_table(index='a', values='b', aggfunc='sum')\n"
            "d.apply(np.log, axis=1)\nd.b.map(d.groupby('a').b.sum())\n")
    assert sandbox.check_code(code) == []


PRE = "import numpy as np\nimport pandas as pd\nd = pd.DataFrame()\n"


@pytest.mark.parametrize(
    "snippet",
    [
        PRE + "f = 'to_csv'\nd.agg(f)",
        PRE + "d.agg(func=('x', 'to_csv'))",
        PRE + "d.apply(arg=('x', 'to_csv'))",
        PRE + "d.pivot_table('v', 'i', 'c', 'to_csv')",
        PRE + "pd.crosstab(d.a, d.b, None, None, None, 'to_csv')",
        PRE + "class C:\n    m = 'to_csv'\nd.agg(C.m)",
        PRE + "def g(func):\n    return d.agg(func)",
    ],
)
def test_dispatch_arguments_must_be_provably_callable_or_reducer_literals(snippet):
    assert sandbox.check_code(snippet)


def test_defined_functions_library_callables_and_builtins_are_provably_callable():
    code = PRE + "def f(x):\n    return x\n\nd.apply(f)\nd.apply(np.log)\nd.apply(len)\nd.agg(np.sum)\npd.crosstab(d.a, d.b)\n"
    assert sandbox.check_code(code) == []


@pytest.mark.parametrize(
    "snippet",
    [
        PRE + "def f(x):\n    return x\nf = 'to_csv'\nd.agg(f)",
        PRE + "len = 'to_csv'\nd.agg(len)",
        PRE + "import math\nmath = 'to_csv'\nd.agg(math)",
        PRE + "import math as m\nfor m in ['to_csv']:\n    d.agg(m)",
        PRE + "np.sum = 'to_csv'\nd.agg(np.sum)",
        PRE + "class C:\n    sum = 'to_csv'\nnp = C\nd.agg(np.sum)",
        PRE + "def f(x):\n    return x\ndef f(x):\n    return 'to_csv'\nd.agg(f)",
        PRE + "g = np.log\nd.agg(g)",
    ],
)
def test_names_rebound_or_aliased_are_not_provably_callable(snippet):
    assert sandbox.check_code(snippet)


@pytest.mark.parametrize(
    "snippet",
    [
        PRE + "def deco(f):\n    return 'to_csv'\n@deco\ndef f(x):\n    return x\nd.agg(f)",
        PRE + "match 'to_csv':\n    case str() as g:\n        d.agg(g)",
        PRE + "match ['to_csv']:\n    case [*g]:\n        pass",
    ],
)
def test_decorators_and_match_statements_are_rejected(snippet):
    assert sandbox.check_code(snippet)
