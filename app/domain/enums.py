from enum import Enum as PyEnum


class AccountType(str, PyEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    INVESTMENT = "investment"


class TransactionType(str, PyEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class CategoryType(str, PyEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    SAVINGS = "savings"


class TransactionSource(str, PyEnum):
    MANUAL = "manual"
    IMAP = "imap"
    API = "api"
    SYSTEM = "system"
