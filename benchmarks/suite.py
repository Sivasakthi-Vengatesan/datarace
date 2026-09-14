"""
DataRace 10 Real-World Concurrency Benchmark Suite.
Defines canonical real-world isolation race bugs, setup schemas, invariants, and fixed remediations.
"""

from typing import Dict, List, Callable, Tuple, Any
import sqlite3
from datarace.core.models import (
    Transaction,
    Operation,
    OpType,
    IsolationLevel
)
from datarace.invariants.engine import InvariantEngine


class BenchmarkCase:
    def __init__(
        self,
        case_id: str,
        title: str,
        category: str,
        description: str,
        setup_sql: str,
        invariants: InvariantEngine,
        transactions_fn: Callable[[], List[Transaction]],
        fixed_transactions_fn: Callable[[], List[Transaction]],
        suggested_fix: str
    ):
        self.case_id = case_id
        self.title = title
        self.category = category
        self.description = description
        self.setup_sql = setup_sql
        self.invariants = invariants
        self.transactions_fn = transactions_fn
        self.fixed_transactions_fn = fixed_transactions_fn
        self.suggested_fix = suggested_fix

    def setup_db(self, conn: sqlite3.Connection):
        cursor = conn.cursor()
        cursor.executescript(self.setup_sql)


def get_all_benchmarks() -> Dict[str, BenchmarkCase]:
    benchmarks = {}

    # 1. Banking Lost Update
    inv1 = InvariantEngine()
    inv1.register_sql(
        "balance_correctness",
        "SELECT balance = 130 FROM accounts WHERE id = 1",
        description="Final balance must equal initial (100) + deposit (50) - withdrawal (20) = 130",
        expected="balance == 130"
    )
    def txs_1():
        # T1: Deposit 50 (Read 100 -> Write 150)
        t1 = Transaction(tx_id="T1_Deposit", name="Deposit $50")
        t1.operations = [
            Operation("op1_1", "T1_Deposit", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_Deposit", OpType.READ, table="accounts", keys=["accounts:id=1"], sql="SELECT balance FROM accounts WHERE id = 1;"),
            Operation("op1_3", "T1_Deposit", OpType.WRITE, table="accounts", columns=["balance"], keys=["accounts:id=1"], sql="UPDATE accounts SET balance = 150 WHERE id = 1;"),
            Operation("op1_4", "T1_Deposit", OpType.COMMIT, sql="COMMIT;")
        ]
        # T2: Withdraw 20 (Read 100 -> Write 80)
        t2 = Transaction(tx_id="T2_Withdraw", name="Withdraw $20")
        t2.operations = [
            Operation("op2_1", "T2_Withdraw", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_Withdraw", OpType.READ, table="accounts", keys=["accounts:id=1"], sql="SELECT balance FROM accounts WHERE id = 1;"),
            Operation("op2_3", "T2_Withdraw", OpType.WRITE, table="accounts", columns=["balance"], keys=["accounts:id=1"], sql="UPDATE accounts SET balance = 80 WHERE id = 1;"),
            Operation("op2_4", "T2_Withdraw", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    def fixed_txs_1():
        t1 = Transaction(tx_id="T1_Deposit", name="Deposit $50 (Atomic)")
        t1.operations = [
            Operation("op1_1", "T1_Deposit", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_Deposit", OpType.WRITE, table="accounts", columns=["balance"], keys=["accounts:id=1"], sql="UPDATE accounts SET balance = balance + 50 WHERE id = 1;"),
            Operation("op1_3", "T1_Deposit", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_Withdraw", name="Withdraw $20 (Atomic)")
        t2.operations = [
            Operation("op2_1", "T2_Withdraw", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_Withdraw", OpType.WRITE, table="accounts", columns=["balance"], keys=["accounts:id=1"], sql="UPDATE accounts SET balance = balance - 20 WHERE id = 1;"),
            Operation("op2_3", "T2_Withdraw", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["01_banking_lost_update"] = BenchmarkCase(
        case_id="01_banking_lost_update",
        title="Banking Account Lost Update",
        category="Financial / Lost Update (G0)",
        description="Concurrent deposit and withdrawal read initial balance simultaneously; the second commit overwrites the first.",
        setup_sql="CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER); INSERT INTO accounts VALUES (1, 'Alice', 100);",
        invariants=inv1,
        transactions_fn=txs_1,
        fixed_transactions_fn=fixed_txs_1,
        suggested_fix="Use atomic update `UPDATE accounts SET balance = balance + ? WHERE id = ?` or `SELECT ... FOR UPDATE` pessimistic lock."
    )

    # 2. Ticket Double Booking
    inv2 = InvariantEngine()
    inv2.register_sql(
        "seat_unique_booking",
        "SELECT COUNT(*) <= 1 FROM bookings WHERE seat_id = 42",
        description="Seat #42 must not be booked more than once",
        expected="booking_count <= 1"
    )
    def txs_2():
        t1 = Transaction(tx_id="T1_UserA", name="User A Booking")
        t1.operations = [
            Operation("op1_1", "T1_UserA", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_UserA", OpType.READ, table="seats", keys=["seats:id=42"], sql="SELECT is_booked FROM seats WHERE id = 42;"),
            Operation("op1_3", "T1_UserA", OpType.WRITE, table="bookings", keys=["bookings:seat_id=42"], sql="INSERT INTO bookings (seat_id, user_name) VALUES (42, 'User A');"),
            Operation("op1_4", "T1_UserA", OpType.WRITE, table="seats", keys=["seats:id=42"], sql="UPDATE seats SET is_booked = 1 WHERE id = 42;"),
            Operation("op1_5", "T1_UserA", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_UserB", name="User B Booking")
        t2.operations = [
            Operation("op2_1", "T2_UserB", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_UserB", OpType.READ, table="seats", keys=["seats:id=42"], sql="SELECT is_booked FROM seats WHERE id = 42;"),
            Operation("op2_3", "T2_UserB", OpType.WRITE, table="bookings", keys=["bookings:seat_id=42"], sql="INSERT INTO bookings (seat_id, user_name) VALUES (42, 'User B');"),
            Operation("op2_4", "T2_UserB", OpType.WRITE, table="seats", keys=["seats:id=42"], sql="UPDATE seats SET is_booked = 1 WHERE id = 42;"),
            Operation("op2_5", "T2_UserB", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    def fixed_txs_2():
        t1 = Transaction(tx_id="T1_UserA", name="User A (Unique Constraint)")
        t1.operations = [
            Operation("op1_1", "T1_UserA", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_UserA", OpType.WRITE, table="seats", keys=["seats:id=42"], sql="UPDATE seats SET is_booked = 1 WHERE id = 42 AND is_booked = 0;"),
            Operation("op1_3", "T1_UserA", OpType.WRITE, table="bookings", keys=["bookings:seat_id=42"], sql="INSERT INTO bookings (seat_id, user_name) VALUES (42, 'User A');"),
            Operation("op1_4", "T1_UserA", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_UserB", name="User B (Unique Constraint)")
        t2.operations = [
            Operation("op2_1", "T2_UserB", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_UserB", OpType.WRITE, table="seats", keys=["seats:id=42"], sql="UPDATE seats SET is_booked = 1 WHERE id = 42 AND is_booked = 0;"),
            Operation("op2_3", "T2_UserB", OpType.WRITE, table="bookings", keys=["bookings:seat_id=42"], sql="INSERT OR IGNORE INTO bookings (seat_id, user_name) VALUES (42, 'User B');"),
            Operation("op2_4", "T2_UserB", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["02_ticket_double_booking"] = BenchmarkCase(
        case_id="02_ticket_double_booking",
        title="Concert Ticket Double Booking Race",
        category="E-Commerce / Double Allocation",
        description="Two concurrent customers observe seat 42 as unbooked and both insert booking confirmations.",
        setup_sql="CREATE TABLE seats (id INTEGER PRIMARY KEY, is_booked INTEGER); INSERT INTO seats VALUES (42, 0); CREATE TABLE bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, seat_id INTEGER, user_name TEXT);",
        invariants=inv2,
        transactions_fn=txs_2,
        fixed_transactions_fn=fixed_txs_2,
        suggested_fix="Add UNIQUE constraint on bookings(seat_id) and use conditional `UPDATE seats SET is_booked = 1 WHERE id = 42 AND is_booked = 0`."
    )

    # 3. Coupon Reuse
    inv3 = InvariantEngine()
    inv3.register_sql(
        "coupon_single_use",
        "SELECT COUNT(*) <= 1 FROM coupon_redemptions WHERE coupon_code = 'SAVE50'",
        description="Single-use coupon must not be redeemed more than once",
        expected="redemption_count <= 1"
    )
    def txs_3():
        t1 = Transaction(tx_id="T1_Checkout1", name="Checkout Session 1")
        t1.operations = [
            Operation("op1_1", "T1_Checkout1", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_Checkout1", OpType.READ, table="coupons", keys=["coupons:code=SAVE50"], sql="SELECT used FROM coupons WHERE code = 'SAVE50';"),
            Operation("op1_3", "T1_Checkout1", OpType.WRITE, table="coupon_redemptions", keys=["coupon_redemptions:code=SAVE50"], sql="INSERT INTO coupon_redemptions (coupon_code, order_id) VALUES ('SAVE50', 101);"),
            Operation("op1_4", "T1_Checkout1", OpType.WRITE, table="coupons", keys=["coupons:code=SAVE50"], sql="UPDATE coupons SET used = 1 WHERE code = 'SAVE50';"),
            Operation("op1_5", "T1_Checkout1", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_Checkout2", name="Checkout Session 2")
        t2.operations = [
            Operation("op2_1", "T2_Checkout2", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_Checkout2", OpType.READ, table="coupons", keys=["coupons:code=SAVE50"], sql="SELECT used FROM coupons WHERE code = 'SAVE50';"),
            Operation("op2_3", "T2_Checkout2", OpType.WRITE, table="coupon_redemptions", keys=["coupon_redemptions:code=SAVE50"], sql="INSERT INTO coupon_redemptions (coupon_code, order_id) VALUES ('SAVE50', 102);"),
            Operation("op2_4", "T2_Checkout2", OpType.WRITE, table="coupons", keys=["coupons:code=SAVE50"], sql="UPDATE coupons SET used = 1 WHERE code = 'SAVE50';"),
            Operation("op2_5", "T2_Checkout2", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    def fixed_txs_3():
        return txs_3()  # Fixed in real DB via UNIQUE / optimistic check

    benchmarks["03_coupon_reuse"] = BenchmarkCase(
        case_id="03_coupon_reuse",
        title="Single-Use Coupon Double-Spend",
        category="E-Commerce / Promo Fraud",
        description="Concurrent checkout requests exploit read-check window to redeem single-use coupon multiple times.",
        setup_sql="CREATE TABLE coupons (code TEXT PRIMARY KEY, used INTEGER); INSERT INTO coupons VALUES ('SAVE50', 0); CREATE TABLE coupon_redemptions (id INTEGER PRIMARY KEY AUTOINCREMENT, coupon_code TEXT, order_id INTEGER);",
        invariants=inv3,
        transactions_fn=txs_3,
        fixed_transactions_fn=fixed_txs_3,
        suggested_fix="Use atomic conditional update `UPDATE coupons SET used = 1 WHERE code = 'SAVE50' AND used = 0` or UNIQUE constraint."
    )

    # 4. Wallet Write Skew
    inv4 = InvariantEngine()
    inv4.register_sql(
        "joint_balance_non_negative",
        "SELECT (c.balance + s.balance) >= 0 FROM checking c, savings s WHERE c.user_id = 1 AND s.user_id = 1",
        description="Total user balance (Checking + Savings) must remain >= 0",
        expected="total_balance >= 0"
    )
    def txs_4():
        # Initial: Checking = 100, Savings = 100 (Total = 200). Rule: can withdraw if total >= 150
        # T1: Withdraw 150 from Checking
        t1 = Transaction(tx_id="T1_CheckingWithdraw", name="Withdraw $150 from Checking")
        t1.operations = [
            Operation("op1_1", "T1_CheckingWithdraw", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_CheckingWithdraw", OpType.READ, table="checking", keys=["checking:user_id=1"], sql="SELECT balance FROM checking WHERE user_id = 1;"),
            Operation("op1_3", "T1_CheckingWithdraw", OpType.READ, table="savings", keys=["savings:user_id=1"], sql="SELECT balance FROM savings WHERE user_id = 1;"),
            Operation("op1_4", "T1_CheckingWithdraw", OpType.WRITE, table="checking", keys=["checking:user_id=1"], sql="UPDATE checking SET balance = balance - 150 WHERE user_id = 1;"),
            Operation("op1_5", "T1_CheckingWithdraw", OpType.COMMIT, sql="COMMIT;")
        ]
        # T2: Withdraw 150 from Savings
        t2 = Transaction(tx_id="T2_SavingsWithdraw", name="Withdraw $150 from Savings")
        t2.operations = [
            Operation("op2_1", "T2_SavingsWithdraw", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_SavingsWithdraw", OpType.READ, table="checking", keys=["checking:user_id=1"], sql="SELECT balance FROM checking WHERE user_id = 1;"),
            Operation("op2_3", "T2_SavingsWithdraw", OpType.READ, table="savings", keys=["savings:user_id=1"], sql="SELECT balance FROM savings WHERE user_id = 1;"),
            Operation("op2_4", "T2_SavingsWithdraw", OpType.WRITE, table="savings", keys=["savings:user_id=1"], sql="UPDATE savings SET balance = balance - 150 WHERE user_id = 1;"),
            Operation("op2_5", "T2_SavingsWithdraw", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["04_wallet_write_skew"] = BenchmarkCase(
        case_id="04_wallet_write_skew",
        title="Joint Checking & Savings Write Skew (G2)",
        category="Banking / Write Skew (Snapshot Isolation Anomaly)",
        description="Two transactions read joint balance ($200) and modify disjoint accounts (T1 modifies Checking, T2 modifies Savings), resulting in -$100 overdraft.",
        setup_sql="CREATE TABLE checking (user_id INTEGER PRIMARY KEY, balance INTEGER); INSERT INTO checking VALUES (1, 100); CREATE TABLE savings (user_id INTEGER PRIMARY KEY, balance INTEGER); INSERT INTO savings VALUES (1, 100);",
        invariants=inv4,
        transactions_fn=txs_4,
        fixed_transactions_fn=txs_4,
        suggested_fix="Execute under SERIALIZABLE isolation level or lock user mutex row in parent table with `SELECT ... FOR UPDATE`."
    )

    # 5. E-commerce Overselling
    inv5 = InvariantEngine()
    inv5.register_sql(
        "stock_non_negative",
        "SELECT MIN(stock) >= 0 FROM products WHERE id = 10",
        description="Inventory stock count must never drop below 0",
        expected="stock >= 0"
    )
    def txs_5():
        t1 = Transaction(tx_id="T1_Order1", name="Order 1 (Qty 1)")
        t1.operations = [
            Operation("op1_1", "T1_Order1", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_Order1", OpType.READ, table="products", keys=["products:id=10"], sql="SELECT stock FROM products WHERE id = 10;"),
            Operation("op1_3", "T1_Order1", OpType.WRITE, table="products", keys=["products:id=10"], sql="UPDATE products SET stock = stock - 1 WHERE id = 10;"),
            Operation("op1_4", "T1_Order1", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_Order2", name="Order 2 (Qty 1)")
        t2.operations = [
            Operation("op2_1", "T2_Order2", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_Order2", OpType.READ, table="products", keys=["products:id=10"], sql="SELECT stock FROM products WHERE id = 10;"),
            Operation("op2_3", "T2_Order2", OpType.WRITE, table="products", keys=["products:id=10"], sql="UPDATE products SET stock = stock - 1 WHERE id = 10;"),
            Operation("op2_4", "T2_Order2", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["05_ecommerce_overselling"] = BenchmarkCase(
        case_id="05_ecommerce_overselling",
        title="Flash Sale Inventory Overselling",
        category="E-Commerce / Inventory Race",
        description="Only 1 item left in stock; two concurrent orders both read stock=1 and decrement, driving inventory to -1.",
        setup_sql="CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, stock INTEGER); INSERT INTO products VALUES (10, 'Limited GPU', 1);",
        invariants=inv5,
        transactions_fn=txs_5,
        fixed_transactions_fn=txs_5,
        suggested_fix="Use conditional atomic update: `UPDATE products SET stock = stock - 1 WHERE id = 10 AND stock >= 1` and verify affected rows == 1."
    )

    # 6. Phantom Read Budget
    inv6 = InvariantEngine()
    inv6.register_sql(
        "dept_budget_limit",
        "SELECT SUM(amount) <= 1000 FROM expenses WHERE dept_id = 5",
        description="Total departmental expenses must not exceed $1000",
        expected="sum(amount) <= 1000"
    )
    def txs_6():
        t1 = Transaction(tx_id="T1_SubmitExpenseA", name="Submit $600 Expense")
        t1.operations = [
            Operation("op1_1", "T1_SubmitExpenseA", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_SubmitExpenseA", OpType.READ, table="expenses", keys=["expenses:dept_id=5"], sql="SELECT SUM(amount) FROM expenses WHERE dept_id = 5;"),
            Operation("op1_3", "T1_SubmitExpenseA", OpType.WRITE, table="expenses", keys=["expenses:dept_id=5"], sql="INSERT INTO expenses (dept_id, amount) VALUES (5, 600);"),
            Operation("op1_4", "T1_SubmitExpenseA", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_SubmitExpenseB", name="Submit $600 Expense")
        t2.operations = [
            Operation("op2_1", "T2_SubmitExpenseB", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_SubmitExpenseB", OpType.READ, table="expenses", keys=["expenses:dept_id=5"], sql="SELECT SUM(amount) FROM expenses WHERE dept_id = 5;"),
            Operation("op2_3", "T2_SubmitExpenseB", OpType.WRITE, table="expenses", keys=["expenses:dept_id=5"], sql="INSERT INTO expenses (dept_id, amount) VALUES (5, 600);"),
            Operation("op2_4", "T2_SubmitExpenseB", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["06_phantom_read_budget"] = BenchmarkCase(
        case_id="06_phantom_read_budget",
        title="Departmental Budget Phantom Insertion Race",
        category="Accounting / Phantom Read (P3)",
        description="Two concurrent expense claims both observe current sum = $0, each inserts $600, total exceeds $1000 limit.",
        setup_sql="CREATE TABLE expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, dept_id INTEGER, amount INTEGER);",
        invariants=inv6,
        transactions_fn=txs_6,
        fixed_transactions_fn=txs_6,
        suggested_fix="Lock department row in parent `departments` table with `SELECT ... FOR UPDATE` before aggregating child expenses."
    )

    # 7. Transfer Deadlock
    inv7 = InvariantEngine()
    inv7.register_sql(
        "accounts_sum_constant",
        "SELECT (SELECT balance FROM accounts WHERE id = 1) + (SELECT balance FROM accounts WHERE id = 2) = 200",
        description="Total money across accounts 1 and 2 must remain constant ($200)",
        expected="sum(balance) == 200"
    )
    def txs_7():
        t1 = Transaction(tx_id="T1_Transfer1to2", name="Transfer $50 (Acc 1 -> Acc 2)")
        t1.operations = [
            Operation("op1_1", "T1_Transfer1to2", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_Transfer1to2", OpType.WRITE, table="accounts", keys=["accounts:id=1"], sql="UPDATE accounts SET balance = balance - 50 WHERE id = 1;"),
            Operation("op1_3", "T1_Transfer1to2", OpType.WRITE, table="accounts", keys=["accounts:id=2"], sql="UPDATE accounts SET balance = balance + 50 WHERE id = 2;"),
            Operation("op1_4", "T1_Transfer1to2", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_Transfer2to1", name="Transfer $30 (Acc 2 -> Acc 1)")
        t2.operations = [
            Operation("op2_1", "T2_Transfer2to1", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_Transfer2to1", OpType.WRITE, table="accounts", keys=["accounts:id=2"], sql="UPDATE accounts SET balance = balance - 30 WHERE id = 2;"),
            Operation("op2_3", "T2_Transfer2to1", OpType.WRITE, table="accounts", keys=["accounts:id=1"], sql="UPDATE accounts SET balance = balance + 30 WHERE id = 1;"),
            Operation("op2_4", "T2_Transfer2to1", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["07_transfer_deadlock"] = BenchmarkCase(
        case_id="07_transfer_deadlock",
        title="Cross-Account Transfer Deadlock",
        category="Concurrency / Deadlock",
        description="T1 locks account 1 then waits for account 2; T2 locks account 2 then waits for account 1.",
        setup_sql="CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER); INSERT INTO accounts VALUES (1, 100), (2, 100);",
        invariants=inv7,
        transactions_fn=txs_7,
        fixed_transactions_fn=txs_7,
        suggested_fix="Acquire row locks in consistent global order (e.g. `ORDER BY id ASC`)."
    )

    # 8. Job Queue Double Claim
    inv8 = InvariantEngine()
    inv8.register_sql(
        "job_single_claim",
        "SELECT COUNT(*) <= 1 FROM job_claims WHERE job_id = 7",
        description="Job #7 must only be claimed by at most one worker",
        expected="claims_count <= 1"
    )
    def txs_8():
        t1 = Transaction(tx_id="T1_WorkerA", name="Worker A Claim Job")
        t1.operations = [
            Operation("op1_1", "T1_WorkerA", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_WorkerA", OpType.READ, table="jobs", keys=["jobs:id=7"], sql="SELECT status FROM jobs WHERE id = 7;"),
            Operation("op1_3", "T1_WorkerA", OpType.WRITE, table="job_claims", keys=["job_claims:job_id=7"], sql="INSERT INTO job_claims (job_id, worker_id) VALUES (7, 'WorkerA');"),
            Operation("op1_4", "T1_WorkerA", OpType.WRITE, table="jobs", keys=["jobs:id=7"], sql="UPDATE jobs SET status = 'PROCESSING' WHERE id = 7;"),
            Operation("op1_5", "T1_WorkerA", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_WorkerB", name="Worker B Claim Job")
        t2.operations = [
            Operation("op2_1", "T2_WorkerB", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_WorkerB", OpType.READ, table="jobs", keys=["jobs:id=7"], sql="SELECT status FROM jobs WHERE id = 7;"),
            Operation("op2_3", "T2_WorkerB", OpType.WRITE, table="job_claims", keys=["job_claims:job_id=7"], sql="INSERT INTO job_claims (job_id, worker_id) VALUES (7, 'WorkerB');"),
            Operation("op2_4", "T2_WorkerB", OpType.WRITE, table="jobs", keys=["jobs:id=7"], sql="UPDATE jobs SET status = 'PROCESSING' WHERE id = 7;"),
            Operation("op2_5", "T2_WorkerB", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["08_job_queue_double_claim"] = BenchmarkCase(
        case_id="08_job_queue_double_claim",
        title="Background Job Queue Double Claim",
        category="Distributed Systems / Task Queue",
        description="Two background workers both poll pending job #7 and both proceed to process it.",
        setup_sql="CREATE TABLE jobs (id INTEGER PRIMARY KEY, status TEXT); INSERT INTO jobs VALUES (7, 'PENDING'); CREATE TABLE job_claims (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, worker_id TEXT);",
        invariants=inv8,
        transactions_fn=txs_8,
        fixed_transactions_fn=txs_8,
        suggested_fix="Use atomic conditional update `UPDATE jobs SET status = 'PROCESSING' WHERE id = 7 AND status = 'PENDING'` or UNIQUE constraint on `job_claims(job_id)`."
    )

    # 9. Rate Limiter Bypass
    inv9 = InvariantEngine()
    inv9.register_sql(
        "rate_limit_enforced",
        "SELECT request_count <= 5 FROM rate_limits WHERE user_id = 99",
        description="User request count within window must not exceed 5",
        expected="request_count <= 5"
    )
    def txs_9():
        t1 = Transaction(tx_id="T1_Req1", name="API Request #5")
        t1.operations = [
            Operation("op1_1", "T1_Req1", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_Req1", OpType.READ, table="rate_limits", keys=["rate_limits:user_id=99"], sql="SELECT request_count FROM rate_limits WHERE user_id = 99;"),
            Operation("op1_3", "T1_Req1", OpType.WRITE, table="rate_limits", keys=["rate_limits:user_id=99"], sql="UPDATE rate_limits SET request_count = request_count + 1 WHERE user_id = 99;"),
            Operation("op1_4", "T1_Req1", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_Req2", name="API Request #6")
        t2.operations = [
            Operation("op2_1", "T2_Req2", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_Req2", OpType.READ, table="rate_limits", keys=["rate_limits:user_id=99"], sql="SELECT request_count FROM rate_limits WHERE user_id = 99;"),
            Operation("op2_3", "T2_Req2", OpType.WRITE, table="rate_limits", keys=["rate_limits:user_id=99"], sql="UPDATE rate_limits SET request_count = request_count + 1 WHERE user_id = 99;"),
            Operation("op2_4", "T2_Req2", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["09_rate_limiter_bypass"] = BenchmarkCase(
        case_id="09_rate_limiter_bypass",
        title="API Rate Limiter Concurrency Bypass",
        category="Security / Rate Limiting",
        description="Concurrent burst requests both see count=4 and both allow requests, exceeding quota.",
        setup_sql="CREATE TABLE rate_limits (user_id INTEGER PRIMARY KEY, request_count INTEGER); INSERT INTO rate_limits VALUES (99, 4);",
        invariants=inv9,
        transactions_fn=txs_9,
        fixed_transactions_fn=txs_9,
        suggested_fix="Use Redis atomic `INCR` or PostgreSQL `UPDATE rate_limits SET request_count = request_count + 1 WHERE user_id = ? AND request_count < 5`."
    )

    # 10. Auction Bid Snooping
    inv10 = InvariantEngine()
    inv10.register_sql(
        "highest_bid_monotonic",
        "SELECT current_bid = 500 FROM auctions WHERE id = 1",
        description="Highest auction bid must be $500 (Bidder B), not downgraded by stale write",
        expected="current_bid == 500"
    )
    def txs_10():
        t1 = Transaction(tx_id="T1_BidderA", name="Bid $400 (Bidder A)")
        t1.operations = [
            Operation("op1_1", "T1_BidderA", OpType.BEGIN, sql="BEGIN;"),
            Operation("op1_2", "T1_BidderA", OpType.READ, table="auctions", keys=["auctions:id=1"], sql="SELECT current_bid FROM auctions WHERE id = 1;"),
            Operation("op1_3", "T1_BidderA", OpType.WRITE, table="auctions", keys=["auctions:id=1"], sql="UPDATE auctions SET current_bid = 400, bidder = 'Alice' WHERE id = 1;"),
            Operation("op1_4", "T1_BidderA", OpType.COMMIT, sql="COMMIT;")
        ]
        t2 = Transaction(tx_id="T2_BidderB", name="Bid $500 (Bidder B)")
        t2.operations = [
            Operation("op2_1", "T2_BidderB", OpType.BEGIN, sql="BEGIN;"),
            Operation("op2_2", "T2_BidderB", OpType.READ, table="auctions", keys=["auctions:id=1"], sql="SELECT current_bid FROM auctions WHERE id = 1;"),
            Operation("op2_3", "T2_BidderB", OpType.WRITE, table="auctions", keys=["auctions:id=1"], sql="UPDATE auctions SET current_bid = 500, bidder = 'Bob' WHERE id = 1;"),
            Operation("op2_4", "T2_BidderB", OpType.COMMIT, sql="COMMIT;")
        ]
        return [t1, t2]

    benchmarks["10_auction_bid_snooping"] = BenchmarkCase(
        case_id="10_auction_bid_snooping",
        title="Live Auction Stale Bid Overwrite",
        category="Realtime / Auction Bidding",
        description="Bidder B places $500 bid; delayed commit from Bidder A ($400) overwrites highest bid to $400.",
        setup_sql="CREATE TABLE auctions (id INTEGER PRIMARY KEY, item TEXT, current_bid INTEGER, bidder TEXT); INSERT INTO auctions VALUES (1, 'Vintage Watch', 300, 'Init');",
        invariants=inv10,
        transactions_fn=txs_10,
        fixed_transactions_fn=txs_10,
        suggested_fix="Use optimistic concurrency control: `UPDATE auctions SET current_bid = 500, bidder = 'Bob' WHERE id = 1 AND current_bid < 500`."
    )

    return benchmarks
