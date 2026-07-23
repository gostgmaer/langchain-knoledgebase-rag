"""
============================================================
core/tools/calculator.py
============================================================

Production Ready Calculator Tool
--------------------------------

Features
--------
✔ Safe AST Evaluation
✔ LangChain Tool
✔ Arithmetic Operations
✔ Scientific Functions
✔ Statistics
✔ Constants
✔ Structured Response
✔ Logging
✔ Type Hints
✔ No eval()

Supported Operators
-------------------
+
-
*
/
//
%
**

Supported Functions
-------------------
sqrt
abs
round
ceil
floor
factorial
log
ln
sin
cos
tan
min
max
sum
avg

Constants
---------
pi
e

============================================================
"""

from __future__ import annotations

import ast
import math
import operator
import statistics
from dataclasses import asdict, dataclass
from typing import Any

from langchain.tools import tool

from packages.logging.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# Response Models
# ============================================================


@dataclass(slots=True)
class CalculatorSuccess:

    success: bool
    tool: str
    message: str
    query: dict[str, Any]
    data: dict[str, Any]
    summary: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class CalculatorError:

    success: bool
    tool: str
    message: str
    query: dict[str, Any]
    error: dict[str, Any]


# ============================================================
# Allowed Operators
# ============================================================

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


_ALLOWED_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


# ============================================================
# Allowed Constants
# ============================================================

_ALLOWED_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


# ============================================================
# Allowed Functions
# ============================================================

_ALLOWED_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
    "log": math.log10,
    "ln": math.log,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "min": min,
    "max": max,
    "sum": sum,
    "avg": lambda *values: statistics.mean(values),
}

# ============================================================
# Safe AST Calculator Engine
# ============================================================


class SafeCalculator:
    """
    Safely evaluates mathematical expressions using Python AST.

    Supported:
        +  -  *  /  //  %  **
        Parentheses
        sqrt(), log(), ln(), sin(), cos(), tan()
        abs(), round(), ceil(), floor()
        factorial()
        min(), max(), sum(), avg()
        pi, e
    """

    MAX_DEPTH = 25

    def evaluate(self, expression: str) -> Any:
        """
        Parse and evaluate a mathematical expression.
        """

        if not expression or not expression.strip():
            raise ValueError("Expression cannot be empty.")

        expression = expression.strip()

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("Invalid mathematical expression.") from exc

        self._validate_depth(tree)

        return self._eval(tree.body)

    # --------------------------------------------------------
    # AST Evaluator
    # --------------------------------------------------------

    def _eval(self, node: ast.AST) -> Any:

        # Numeric literals
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value

            raise ValueError("Only numeric constants are allowed.")

        # Binary operations
        if isinstance(node, ast.BinOp):

            left = self._eval(node.left)
            right = self._eval(node.right)

            operator_type = type(node.op)

            if operator_type not in _ALLOWED_OPERATORS:
                raise ValueError(
                    f"Operator '{operator_type.__name__}' is not supported."
                )

            return _ALLOWED_OPERATORS[operator_type](left, right)

        # Unary operations
        if isinstance(node, ast.UnaryOp):

            operand = self._eval(node.operand)

            operator_type = type(node.op)

            if operator_type not in _ALLOWED_UNARY:
                raise ValueError("Unary operator not supported.")

            return _ALLOWED_UNARY[operator_type](operand)

        # Named constants
        if isinstance(node, ast.Name):

            if node.id not in _ALLOWED_CONSTANTS:
                raise ValueError(f"Unknown constant '{node.id}'.")

            return _ALLOWED_CONSTANTS[node.id]

        # Function calls
        if isinstance(node, ast.Call):

            if not isinstance(node.func, ast.Name):
                raise ValueError("Invalid function call.")

            function_name = node.func.id

            if function_name not in _ALLOWED_FUNCTIONS:
                raise ValueError(f"Function '{function_name}' is not supported.")

            function = _ALLOWED_FUNCTIONS[function_name]

            arguments = [self._eval(argument) for argument in node.args]

            return function(*arguments)

        # Reject everything else
        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    # --------------------------------------------------------
    # Security
    # --------------------------------------------------------

    def _validate_depth(self, tree: ast.AST) -> None:
        """
        Prevent extremely deep ASTs.
        """

        def depth(node: ast.AST) -> int:

            children = list(ast.iter_child_nodes(node))

            if not children:
                return 1

            return 1 + max(depth(child) for child in children)

        if depth(tree) > self.MAX_DEPTH:
            raise ValueError("Expression is too complex.")


# ============================================================
# Calculator Instance
# ============================================================

calculator_engine = SafeCalculator()

# ============================================================
# Calculator Tool
# ============================================================


@tool(
    "calculator",
    description="""
Perform mathematical calculations.

Use this tool whenever the user asks to calculate, evaluate, or solve a mathematical expression.

Supported operators:
+  -  *  /  //  %  **

Supported functions:
sqrt(x)
abs(x)
round(x)
ceil(x)
floor(x)
factorial(x)
log(x)
ln(x)
sin(x)
cos(x)
tan(x)
min(...)
max(...)
sum(...)
avg(...)

Constants:
pi
e

Examples:
- 25 * 48
- (25 + 10) / 5
- sqrt(256)
- factorial(5)
- log(100)
- sin(pi/2)
- avg(10,20,30)
""",
    return_direct=False,
)
def calculator(expression: str) -> dict:
    """
    Evaluate a mathematical expression safely.
    """

    logger.info("Calculator Tool Invoked")
    logger.debug("Expression: %s", expression)

    try:

        result = calculator_engine.evaluate(expression)

        # `**`/`factorial` have no built-in size limit and can produce
        # a result thousands of digits long. Checked via `bit_length()`
        # (never converts to a string) so this never trips CPython's
        # own int-to-str digit-count guard first — that raises a
        # ValueError with a confusing "set_int_max_str_digits()"
        # message instead of the clean one below.
        if isinstance(result, int) and abs(result).bit_length() > 10_000:
            raise OverflowError

        response = CalculatorSuccess(
            success=True,
            tool="calculator",
            message="Calculation completed successfully.",
            query={
                "expression": expression,
            },
            data={
                "expression": expression,
                "result": result,
                "result_type": type(result).__name__,
            },
            summary=f"The result of '{expression}' is {result}.",
            metadata={
                "engine": "Safe AST Calculator",
                "version": "1.0.0",
            },
        )

        logger.info("Calculation Successful")

        return asdict(response)

    except ZeroDivisionError:

        logger.warning("Division by zero")

        response = CalculatorError(
            success=False,
            tool="calculator",
            message="Division by zero is not allowed.",
            query={
                "expression": expression,
            },
            error={
                "type": "ZeroDivisionError",
                "message": "Cannot divide by zero.",
            },
        )

        return asdict(response)

    except ValueError as exc:

        logger.warning("Validation Error: %s", exc)

        response = CalculatorError(
            success=False,
            tool="calculator",
            message="Invalid mathematical expression.",
            query={
                "expression": expression,
            },
            error={
                "type": "ValidationError",
                "message": str(exc),
            },
        )

        return asdict(response)

    except OverflowError:

        logger.exception("Overflow Error")

        response = CalculatorError(
            success=False,
            tool="calculator",
            message="Calculation overflowed.",
            query={
                "expression": expression,
            },
            error={
                "type": "OverflowError",
                "message": "Result is too large.",
            },
        )

        return asdict(response)

    except Exception as exc:

        logger.exception("Unexpected calculator error")

        response = CalculatorError(
            success=False,
            tool="calculator",
            message="Unexpected calculator error.",
            query={
                "expression": expression,
            },
            error={
                "type": type(exc).__name__,
                "message": str(exc),
            },
        )

        return asdict(response)

    # ============================================================


# Manual Testing
# ============================================================

if __name__ == "__main__":

    examples = [
        "2 + 2",
        "10 - 3",
        "5 * 8",
        "100 / 5",
        "2 ** 10",
        "25 % 4",
        "sqrt(256)",
        "factorial(6)",
        "round(10 / 3, 2)",
        "abs(-100)",
        "ceil(3.14)",
        "floor(3.99)",
        "log(1000)",
        "ln(e)",
        "sin(pi / 2)",
        "cos(0)",
        "tan(0)",
        "min(5,2,9,1)",
        "max(5,2,9,1)",
        "avg(10,20,30,40)",
        "sum([1,2,3,4])",
        "(25 + 10) * 3",
    ]

    print("=" * 70)
    print("Production Calculator Tool")
    print("=" * 70)

    for expression in examples:

        print("\nExpression:", expression)

        result = calculator.invoke(
            {
                "expression": expression,
            }
        )

        print(result)

    print("\nDone.")
