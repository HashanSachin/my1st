import streamlit as st
import psycopg2
import hashlib
from datetime import date, datetime
import pandas as pd
import plotly.express as px

# --- 1. PAGE SETUP & MODERN BLUE THEME ---
st.set_page_config(
    page_title="Smart Finance Blue Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Modern Sapphire & Midnight Blue UI Theme
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background: radial-gradient(circle at top, #0d1f42 0%, #060e21 100%);
        color: #f0f6ff;
    }
    [data-testid="collapsedControl"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] { background-color: transparent !important; }
    
    /* Forms & Containers */
    [data-testid="stForm"] {
        background-color: #0f2147 !important;
        border-radius: 18px !important;
        border: 1px solid #1e3a8a !important;
        padding: 22px !important;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4) !important;
    }
    
    /* Inputs */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea, .stDateInput>div>div>input {
        background-color: #162f65 !important;
        color: #ffffff !important;
        border-radius: 12px !important;
        border: 1px solid #2563eb !important;
    }
    
    /* Buttons */
    .stButton>button, .stFormSubmitButton>button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border-radius: 14px !important;
        border: 1px solid #3b82f6 !important;
        height: 52px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
        transition: 0.2s ease-in-out;
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        border-color: #60a5fa !important;
        transform: translateY(-1px);
    }
    
    h1, h2, h3, h4, p, label, span { color: #f0f6ff !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE UTILITIES ---
def get_db_connection():
    if "CLOUD_DB_URL" not in st.secrets:
        st.error("❌ CLOUD_DB_URL missing in st.secrets!")
        st.stop()
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"])

def run_query(query, params=(), fetch=False, fetchone=False):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute(query, params)
            if fetchone:
                res = c.fetchone()
                conn.commit()
                return res
            if fetch:
                res = c.fetchall()
                conn.commit()
                return res
            conn.commit()
    finally:
        conn.close()

def fetch_df(query, params=()):
    conn = get_db_connection()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

SECRET_SALT = st.secrets.get("SECRET_SALT", "CloudFinanceForce2026")

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), SECRET_SALT.encode('utf-8'), 100000).hex()

# --- 3. SAFE DATABASE AUTO-MIGRATION (PRESERVES ALL EXISTING DATA) ---
@st.cache_resource
def init_cloud_db_v3():
    try:
        tables = [
            """CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role VARCHAR(20) NOT NULL DEFAULT 'user',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                preferred_currency VARCHAR(30) NOT NULL DEFAULT 'KWD (د.ك)'
            );""",
            """CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL, type VARCHAR(50) NOT NULL, balance NUMERIC NOT NULL DEFAULT 0.0
            );""",
            """CREATE TABLE IF NOT EXISTS custom_assets (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                asset_name VARCHAR(100) NOT NULL, category VARCHAR(50) NOT NULL, estimated_value NUMERIC NOT NULL DEFAULT 0.0
            );""",
            """CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                account_id INT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, tx_date DATE NOT NULL,
                tx_type VARCHAR(20) NOT NULL, category VARCHAR(50) NOT NULL, amount NUMERIC NOT NULL, description TEXT
            );""",
            """CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(100) NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE
            );""",
            """CREATE TABLE IF NOT EXISTS budgets (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category VARCHAR(50) NOT NULL, monthly_limit NUMERIC NOT NULL, year_month VARCHAR(7) NOT NULL,
                UNIQUE(user_id, category, year_month)
            );""",
            """CREATE TABLE IF NOT EXISTS savings_goals (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                goal_name VARCHAR(100) NOT NULL, target_amount NUMERIC NOT NULL, current_amount NUMERIC NOT NULL DEFAULT 0.0
            );"""
        ]
        for q in tables:
            run_query(q)

        # Safely add preferred_currency column to existing users table without losing data
        run_query("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_currency VARCHAR(30) NOT NULL DEFAULT 'KWD (د.ك)';")

        admin_hash = hash_password("admin123")
        run_query(
            "INSERT INTO users (username, password_hash, role, status, preferred_currency) VALUES ('admin', %s, 'admin', 'active', 'KWD (د.ك)') ON CONFLICT (username) DO NOTHING;",
            (admin_hash,)
        )
    except Exception as e:
        st.error(f"DB Sync Error: {e}")

init_cloud_db_v3()

# --- 4. STATE MANAGEMENT ---
if "user" not in st.session_state:
    st.session_state.user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "currency" not in st.session_state:
    st.session_state.currency = "KWD (د.ك)"

def set_page(page):
    st.session_state.current_page = page

# --- 5. AUTHENTICATION MODULE ---
if st.session_state.user is None:
    st.markdown("<h1 style='text-align: center; color: #60a5fa; margin-top: 25px;'>💎 Finance Cloud Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #93c5fd;'>Sapphire Blue Edition • Smart Wealth Manager</p>", unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔐 Secure Sign In", "📝 Create Account"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In", use_container_width=True)

        if submit:
            if not username or not password:
                st.warning("Please provide username and password.")
            else:
                p_hash = hash_password(password)
                row = run_query(
                    "SELECT id, username, role, status, COALESCE(preferred_currency, 'KWD (د.ك)') FROM users WHERE username=%s AND password_hash=%s;",
                    (username.strip(), p_hash),
                    fetchone=True
                )
                if row:
                    if row[3] == "inactive":
                        st.error("❌ Account is currently inactive. Contact system administrator.")
                    else:
                        st.session_state.user = {"id": row[0], "username": row[1], "role": row[2]}
                        st.session_state.currency = row[4]
                        acc_cnt = run_query("SELECT COUNT(*) FROM accounts WHERE user_id=%s;", (row[0],), fetchone=True)[0]
                        if acc_cnt == 0:
                            run_query(
                                "INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, 'Main Bank', 'Bank', 0.0), (%s, 'Cash Wallet', 'Cash', 0.0);",
                                (row[0], row[0])
                            )
                        st.rerun()
                else:
                    st.error("❌ Invalid username or password.")

    with tab_register:
        with st.form("register_form", clear_on_submit=True):
            new_u = st.text_input("Choose Username")
            new_p = st.text_input("Choose Password", type="password")
            conf_p = st.text_input("Confirm Password", type="password")
            pref_curr = st.selectbox("Select Your Default Currency", ["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"])
            reg_btn = st.form_submit_button("Register New Account", use_container_width=True)

        if reg_btn:
            if not new_u.strip() or not new_p:
                st.warning("All registration fields are required.")
            elif new_p != conf_p:
                st.error("Passwords do not match.")
            else:
                try:
                    p_hash = hash_password(new_p)
                    run_query(
                        "INSERT INTO users (username, password_hash, role, status, preferred_currency) VALUES (%s, %s, 'user', 'active', %s);",
                        (new_u.strip(), p_hash, pref_curr)
                    )
                    st.success("✅ Account created with your default currency! Proceed to Sign In.")
                except Exception:
                    st.error("Username already exists. Please choose a different username.")

# --- 6. AUTHENTICATED WORKSPACE ---
else:
    uid = st.session_state.user['id']
    curr = st.session_state.currency.split()[0]
    today_date = date.today()
    today_str = today_date.strftime("%Y-%m-%d (%A)")

    # Universal Top Header for Sub-pages
    if st.session_state.current_page != "Home":
        if st.button("⬅️ Back to Main Menu", use_container_width=True):
            set_page("Home")
            st.rerun()
        st.markdown("<hr style='border-color: #1e3a8a; margin: 8px 0 16px 0;'>", unsafe_allow_html=True)

    # ================= HOME MENU =================
    if st.session_state.current_page == "Home":
        # Data aggregation (Overall & Today's Daily Totals)
        bank_bal = float(run_query("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE user_id=%s;", (uid,), fetchone=True)[0])
        asset_val = float(run_query("SELECT COALESCE(SUM(estimated_value), 0) FROM custom_assets WHERE user_id=%s;", (uid,), fetchone=True)[0])
        unread_cnt = int(run_query("SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=FALSE;", (uid,), fetchone=True)[0])
        
        today_inc = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Income' AND tx_date=%s;", (uid, today_date), fetchone=True)[0])
        today_exp = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Expense' AND tx_date=%s;", (uid, today_date), fetchone=True)[0])
        net_worth = bank_bal + asset_val

        st.markdown(f"<h2 style='margin-bottom:0; color:#93c5fd;'>Hello, {st.session_state.user['username'].capitalize()} 👋</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#60a5fa; margin-top:2px; font-weight:500;'>📅 {today_str} &nbsp;|&nbsp; 💱 Currency: <b>{curr}</b></p>", unsafe_allow_html=True)

        # Clean Hero Banner (Blue Sapphire Gradient)
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%); padding: 22px; border-radius: 20px; border: 1px solid #3b82f6; box-shadow: 0 8px 24px rgba(0,0,0,0.4); margin-bottom: 16px;">
                <p style="margin:0; color:#93c5fd; font-size:13px; font-weight:600; letter-spacing:1px;">💎 TOTAL NET WORTH</p>
                <h1 style="margin:4px 0 12px 0; color:#38bdf8; font-size:34px;">{curr} {net_worth:,.2f}</h1>
                <div style="display:flex; justify-content:space-between; border-top:1px solid #1d4ed8; padding-top:10px; font-size:14px;">
                    <span>🏦 Cash & Banks: <b>{curr} {bank_bal:,.2f}</b></span>
                    <span>🏠 Assets: <b>{curr} {asset_val:,.2f}</b></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Today's Income & Expense Summary Box
        st.markdown(
            f"""
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:20px;">
                <div style="background:#0f2147; padding:16px; border-radius:16px; border:1px solid #1e3a8a;">
                    <p style="margin:0; color:#93c5fd; font-size:12px;">📈 Today's Income ({today_date})</p>
                    <h3 style="margin:4px 0 0 0; color:#4ade80;">+ {curr} {today_inc:,.2f}</h3>
                </div>
                <div style="background:#0f2147; padding:16px; border-radius:16px; border:1px solid #1e3a8a;">
                    <p style="margin:0; color:#93c5fd; font-size:12px;">📉 Today's Expenses ({today_date})</p>
                    <h3 style="margin:4px 0 0 0; color:#f87171;">- {curr} {today_exp:,.2f}</h3>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("### 🧭 Main Navigation")
        grid_col1, grid_col2 = st.columns(2)
        with grid_col1:
            if st.button("💸 Add / View Transactions", use_container_width=True):
                set_page("Transactions")
                st.rerun()
            if st.button("📊 Analytics & Charts", use_container_width=True):
                set_page("Dashboard")
                st.rerun()
            if st.button("🏠 Property & Assets", use_container_width=True):
                set_page("Assets")
                st.rerun()
            inbox_btn = f"🔔 Inbox ({unread_cnt} New)" if unread_cnt > 0 else "🔔 Inbox"
            if st.button(inbox_btn, use_container_width=True):
                set_page("Inbox")
                st.rerun()

        with grid_col2:
            if st.button("💳 Accounts & Cards", use_container_width=True):
                set_page("Wallet")
                st.rerun()
            if st.button("🏦 Money Transfer", use_container_width=True):
                set_page("Transfer")
                st.rerun()
            if st.button("🎯 Budgets & Goals", use_container_width=True):
                set_page("Budgets")
                st.rerun()
            if st.button("⚙️ Settings & Currency", use_container_width=True):
                set_page("Profile")
                st.rerun()

        if st.session_state.user['role'] == "admin":
            st.markdown("<hr style='border-color: #1e3a8a;'>", unsafe_allow_html=True)
            if st.button("🔑 Admin Control Panel", use_container_width=True):
                set_page("Admin")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            set_page("Home")
            st.rerun()

    # ================= 1. TRANSACTIONS (WITH DATE, DAILY TOTALS & EMPTY AMOUNT) =================
    elif st.session_state.current_page == "Transactions":
        st.title("💸 Transactions Manager")
        st.markdown(f"<p style='color:#60a5fa; font-size:15px;'>📅 Today's Date: <b>{today_str}</b></p>", unsafe_allow_html=True)

        # Calculate Today's Income & Expense
        today_inc = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Income' AND tx_date=%s;", (uid, today_date), fetchone=True)[0])
        today_exp = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Expense' AND tx_date=%s;", (uid, today_date), fetchone=True)[0])

        st.markdown(
            f"""
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:18px;">
                <div style="background:#0f2147; padding:15px; border-radius:14px; border:1px solid #1e3a8a;">
                    <p style="margin:0; color:#93c5fd; font-size:12px;">📈 Today's Income ({today_date})</p>
                    <h3 style="margin:4px 0 0 0; color:#4ade80;">{curr} {today_inc:,.2f}</h3>
                </div>
                <div style="background:#0f2147; padding:15px; border-radius:14px; border:1px solid #1e3a8a;">
                    <p style="margin:0; color:#93c5fd; font-size:12px;">📉 Today's Expense ({today_date})</p>
                    <h3 style="margin:4px 0 0 0; color:#f87171;">{curr} {today_exp:,.2f}</h3>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        acc_df = fetch_df("SELECT id, name, balance FROM accounts WHERE user_id=%s ORDER BY id ASC", (uid,))
        acc_map = {f"{r['name']} ({curr} {float(r['balance']):,.2f})": r['id'] for _, r in acc_df.iterrows()}

        # Form with clear_on_submit=True & Empty Amount field (value=None)
        with st.form("tx_form", clear_on_submit=True):
            st.subheader("➕ Add New Transaction")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                tx_date = st.date_input("📅 Transaction Date", value=today_date)
                tx_type = st.selectbox("🔄 Transaction Type", ["Expense", "Income"])
                sel_acc = st.selectbox("🏦 Account", list(acc_map.keys()) if acc_map else ["None"])
            with col_t2:
                tx_amt = st.number_input(f"💰 Amount ({curr})", min_value=0.01, value=None, step=0.01, placeholder="Enter amount...")
                cat = st.selectbox("📂 Category", ["Food & Dining", "Groceries", "Rent & Utilities", "Salary", "Transport", "Shopping", "Entertainment", "Healthcare", "Investments", "Other"])
                tx_desc = st.text_input("📝 Notes / Description", placeholder="Optional note...")
            btn_add_tx = st.form_submit_button("✅ Save Transaction", use_container_width=True)

        if btn_add_tx:
            if not acc_map:
                st.error("❌ Please create an account first.")
            elif tx_amt is None or tx_amt <= 0:
                st.warning("⚠️ Please enter a valid amount!")
            else:
                acc_id = acc_map[sel_acc]
                run_query(
                    "INSERT INTO transactions (user_id, account_id, tx_date, tx_type, category, amount, description) VALUES (%s, %s, %s, %s, %s, %s, %s);",
                    (uid, acc_id, tx_date, tx_type, cat, tx_amt, tx_desc)
                )
                bal_mod = tx_amt if tx_type == "Income" else -tx_amt
                run_query("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (bal_mod, acc_id))
                st.success("✅ Transaction saved and form reset!")
                st.rerun()

        # Check Daily Summary for any specific date
        st.subheader("📅 Daily Summary & Transaction History")
        filter_date = st.date_input("Filter Daily Totals by Date", value=today_date, key="filter_dt")
        day_inc = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Income' AND tx_date=%s;", (uid, filter_date), fetchone=True)[0])
        day_exp = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Expense' AND tx_date=%s;", (uid, filter_date), fetchone=True)[0])
        st.info(f"📌 **Summary for {filter_date}:** Income: **{curr} {day_inc:,.2f}** | Expense: **{curr} {day_exp:,.2f}**")

        tx_hist = fetch_df("""
            SELECT t.id as "ID", t.tx_date as "Date", a.name as "Account", t.tx_type as "Type",
                   t.category as "Category", t.amount as "Amount", t.description as "Notes"
            FROM transactions t JOIN accounts a ON t.account_id = a.id
            WHERE t.user_id=%s ORDER BY t.tx_date DESC, t.id DESC LIMIT 100
        """, (uid,))

        if not tx_hist.empty:
            csv_export = tx_hist.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export All to CSV", data=csv_export, file_name="transactions.csv", mime="text/csv", use_container_width=True)

            disp_df = tx_hist.copy()
            disp_df["Amount"] = disp_df["Amount"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(disp_df, use_container_width=True, hide_index=True)

            with st.expander("🗑️ Delete & Revert a Transaction"):
                del_id = st.selectbox("Select ID to Delete", tx_hist["ID"].tolist())
                if st.button("Delete Transaction", use_container_width=True):
                    row = run_query("SELECT account_id, tx_type, amount FROM transactions WHERE id=%s AND user_id=%s;", (del_id, uid), fetchone=True)
                    if row:
                        rev = -float(row[2]) if row[1] == "Income" else float(row[2])
                        run_query("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (rev, row[0]))
                        run_query("DELETE FROM transactions WHERE id=%s AND user_id=%s;", (del_id, uid))
                        st.success("Transaction deleted and balance restored.")
                        st.rerun()
        else:
            st.info("No transactions logged yet.")

    # ================= 2. ANALYTICS & CHARTS =================
    elif st.session_state.current_page == "Dashboard":
        st.title("📊 Financial Dynamics & Charts")

        tot_inc = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Income';", (uid,), fetchone=True)[0])
        tot_exp = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Expense';", (uid,), fetchone=True)[0])

        m1, m2 = st.columns(2)
        m1.metric("📈 Lifetime Incomes", f"{curr} {tot_inc:,.2f}")
        m2.metric("📉 Lifetime Expenses", f"{curr} {tot_exp:,.2f}")

        tx_df = fetch_df("SELECT tx_date, tx_type, category, amount FROM transactions WHERE user_id=%s", (uid,))
        if not tx_df.empty:
            c_left, c_right = st.columns(2)
            with c_left:
                st.subheader("Expense Distribution")
                exp_df = tx_df[tx_df['tx_type'] == 'Expense']
                if not exp_df.empty:
                    fig_pie = px.pie(exp_df, values='amount', names='category', hole=0.45, color_discrete_sequence=px.colors.sequential.Blues_r)
                    fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#f0f6ff'))
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No expense data recorded.")

            with c_right:
                st.subheader("Daily Income vs. Expense")
                daily_trend = tx_df.groupby(['tx_date', 'tx_type'])['amount'].sum().reset_index()
                fig_bar = px.bar(daily_trend, x='tx_date', y='amount', color='tx_type', barmode='group', color_discrete_map={'Income': '#38bdf8', 'Expense': '#f87171'})
                fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#f0f6ff'))
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("💡 Record transactions to populate visual analytics.")

    # ================= 3. WALLET & ACCOUNTS =================
    elif st.session_state.current_page == "Wallet":
        st.title("💳 Accounts & Cards")
        accs = run_query("SELECT id, name, type, balance FROM accounts WHERE user_id=%s ORDER BY id ASC;", (uid,), fetch=True)
        
        if accs:
            for _, a_name, a_type, a_bal in accs:
                st.markdown(
                    f"""
                    <div style="background-color: #0f2147; padding: 16px; border-radius: 14px; border: 1px solid #1e3a8a; margin-bottom: 10px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="background:#2563eb; padding:3px 10px; border-radius:6px; font-size:12px;">{a_type}</span>
                            <h4 style="margin:6px 0 0 0;">{a_name}</h4>
                        </div>
                        <div style="text-align:right;">
                            <span style="color:#93c5fd; font-size:12px;">Available Balance</span>
                            <h3 style="margin:2px 0 0 0; color:#38bdf8;">{curr} {float(a_bal):,.2f}</h3>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with st.expander("➕ Add New Account or Card"):
            with st.form("new_acc_form", clear_on_submit=True):
                acc_name = st.text_input("Name (e.g., NBK Savings, Visa **** 4920)")
                acc_type = st.selectbox("Type", ["Bank", "Visa Card", "Mastercard", "Cash Wallet", "Crypto Wallet"])
                init_bal = st.number_input("Opening Balance", value=None, step=10.0, placeholder="0.00")
                if st.form_submit_button("Create Account", use_container_width=True) and acc_name.strip():
                    bal_val = init_bal if init_bal is not None else 0.0
                    run_query("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, %s, %s, %s);", (uid, acc_name.strip(), acc_type, bal_val))
                    st.success("Account added.")
                    st.rerun()

    # ================= 4. INTERNAL TRANSFER =================
    elif st.session_state.current_page == "Transfer":
        st.title("🏦 Money Transfer")
        accs = fetch_df("SELECT id, name, balance FROM accounts WHERE user_id=%s", (uid,))

        if len(accs) >= 2:
            with st.form("transfer_form", clear_on_submit=True):
                f_acc = st.selectbox("From Account", accs['name'].tolist(), index=0)
                t_acc = st.selectbox("To Account", accs['name'].tolist(), index=1)
                amt = st.number_input("Transfer Amount", min_value=0.01, value=None, step=10.0, placeholder="Enter transfer amount...")
                exec_trf = st.form_submit_button("Submit Transfer", use_container_width=True)

            if exec_trf:
                if amt is None or amt <= 0:
                    st.warning("Please enter a valid amount.")
                elif f_acc == t_acc:
                    st.error("Source and destination accounts must differ.")
                else:
                    run_query("UPDATE accounts SET balance = balance - %s WHERE name=%s AND user_id=%s;", (amt, f_acc, uid))
                    run_query("UPDATE accounts SET balance = balance + %s WHERE name=%s AND user_id=%s;", (amt, t_acc, uid))
                    st.success(f"Transferred {curr} {amt:,.2f} from {f_acc} to {t_acc}.")
                    st.rerun()
        else:
            st.warning("You must register at least two accounts in 'Accounts & Cards' to use transfers.")

    # ================= 5. CUSTOM ASSETS =================
    elif st.session_state.current_page == "Assets":
        st.title("🏠 Custom Assets & Net Worth")
        with st.form("asset_form", clear_on_submit=True):
            a_name = st.text_input("Asset Description (e.g., Real Estate, Gold, Stocks)")
            a_cat = st.selectbox("Category", ["Real Estate", "Gold & Metals", "Vehicles", "Equities/Bonds", "Crypto", "Other"])
            a_val = st.number_input("Current Estimated Value", min_value=0.01, value=None, step=100.0, placeholder="Enter value...")
            if st.form_submit_button("Add Asset", use_container_width=True):
                if a_name.strip() and a_val is not None:
                    run_query("INSERT INTO custom_assets (user_id, asset_name, category, estimated_value) VALUES (%s, %s, %s, %s);", (uid, a_name.strip(), a_cat, a_val))
                    st.success("Asset added.")
                    st.rerun()
                else:
                    st.warning("Please enter both asset name and value.")

        assets = fetch_df("SELECT id as \"ID\", asset_name as \"Asset\", category as \"Category\", estimated_value as \"Value\" FROM custom_assets WHERE user_id=%s", (uid,))
        if not assets.empty:
            disp_assets = assets.copy()
            disp_assets["Value"] = disp_assets["Value"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(disp_assets, use_container_width=True, hide_index=True)

            with st.expander("🗑️ Remove Asset"):
                del_asset_id = st.selectbox("Select Asset to Remove", assets["ID"].tolist())
                if st.button("Delete Asset Entry", use_container_width=True):
                    run_query("DELETE FROM custom_assets WHERE id=%s AND user_id=%s;", (del_asset_id, uid))
                    st.success("Asset entry removed.")
                    st.rerun()

    # ================= 6. BUDGETS & GOALS =================
    elif st.session_state.current_page == "Budgets":
        st.title("🎯 Goals & Budgets")
        tab_g, tab_b = st.tabs(["🚀 Savings Goals", "📊 Monthly Budgets"])

        with tab_g:
            goals = run_query("SELECT id, goal_name, target_amount, current_amount FROM savings_goals WHERE user_id=%s ORDER BY id ASC;", (uid,), fetch=True)
            if goals:
                for _, g_name, g_target, g_curr in goals:
                    pct = min(float(g_curr) / float(g_target) * 100, 100.0) if float(g_target) > 0 else 0.0
                    st.write(f"**🎯 {g_name}** — {pct:.1f}% ({curr} {float(g_curr):,.2f} / {curr} {float(g_target):,.2f})")
                    st.progress(min(float(g_curr) / float(g_target), 1.0))

            with st.expander("➕ New Goal"):
                with st.form("new_g_form", clear_on_submit=True):
                    gn = st.text_input("Goal Name (e.g. New Car, Emergency Fund)")
                    gt = st.number_input("Target Amount", min_value=1.0, value=None, step=100.0, placeholder="Enter target...")
                    gc = st.number_input("Initial Saved Amount", min_value=0.0, value=None, step=50.0, placeholder="0.00")
                    if st.form_submit_button("Add Goal", use_container_width=True) and gn.strip() and gt is not None:
                        init_g = gc if gc is not None else 0.0
                        run_query("INSERT INTO savings_goals (user_id, goal_name, target_amount, current_amount) VALUES (%s, %s, %s, %s);", (uid, gn.strip(), gt, init_g))
                        st.success("Goal registered.")
                        st.rerun()

            if goals:
                with st.expander("💰 Deposit to Goal"):
                    with st.form("dep_g_form", clear_on_submit=True):
                        g_opts = {g[1]: g[0] for g in goals}
                        chosen_g = st.selectbox("Goal", list(g_opts.keys()))
                        dep_val = st.number_input("Deposit Amount", min_value=1.0, value=None, step=25.0, placeholder="Enter deposit...")
                        if st.form_submit_button("Update Progress", use_container_width=True) and dep_val is not None:
                            run_query("UPDATE savings_goals SET current_amount = current_amount + %s WHERE id=%s;", (dep_val, g_opts[chosen_g]))
                            st.success("Progress saved.")
                            st.rerun()

        with tab_b:
            cur_m = datetime.now().strftime("%Y-%m")
            with st.form("b_form", clear_on_submit=True):
                b_cat = st.selectbox("Category", ["Food & Dining", "Groceries", "Rent & Utilities", "Transport", "Shopping", "Entertainment"])
                b_limit = st.number_input("Monthly Limit", min_value=1.0, value=None, step=25.0, placeholder="Enter monthly limit...")
                if st.form_submit_button("Apply Limit", use_container_width=True) and b_limit is not None:
                    run_query(
                        "INSERT INTO budgets (user_id, category, monthly_limit, year_month) VALUES (%s, %s, %s, %s) ON CONFLICT(user_id, category, year_month) DO UPDATE SET monthly_limit=EXCLUDED.monthly_limit;",
                        (uid, b_cat, b_limit, cur_m)
                    )
                    st.success("Budget set.")
                    st.rerun()

            b_df = fetch_df("SELECT category, monthly_limit FROM budgets WHERE user_id=%s AND year_month=%s", (uid, cur_m))
            spent_df = fetch_df("SELECT category, SUM(amount) as spent FROM transactions WHERE user_id=%s AND tx_type='Expense' AND TO_CHAR(tx_date, 'YYYY-MM')=%s GROUP BY category", (uid, cur_m))

            if not b_df.empty:
                for _, r in b_df.iterrows():
                    cat, limit = r['category'], float(r['monthly_limit'])
                    s_row = spent_df[spent_df['category'] == cat]
                    spent = float(s_row['spent'].values[0]) if not s_row.empty else 0.0
                    st.write(f"**{cat}** — Spent: {curr} {spent:,.2f} / Limit: {curr} {limit:,.2f}")
                    st.progress(min(spent / limit, 1.0))

    # ================= 7. INBOX =================
    elif st.session_state.current_page == "Inbox":
        st.title("🔔 Notifications Inbox")
        run_query("UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND is_read=FALSE;", (uid,))
        notifs = run_query("SELECT title, message, created_at FROM notifications WHERE user_id=%s ORDER BY created_at DESC;", (uid,), fetch=True)

        if notifs:
            for nt, nm, nd in notifs:
                st.markdown(
                    f"""
                    <div style="background-color: #0f2147; padding: 15px; border-radius: 12px; border: 1px solid #1e3a8a; margin-bottom: 10px;">
                        <div style="display:flex; justify-content:space-between;">
                            <b style="color:#38bdf8;">📢 {nt}</b>
                            <span style="font-size:12px; color:#93c5fd;">{str(nd)[:16]}</span>
                        </div>
                        <p style="margin:6px 0 0 0;">{nm}</p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("Your inbox is empty.")

    # ================= 8. PROFILE, SECURITY & PERMANENT CURRENCY SETTING =================
    elif st.session_state.current_page == "Profile":
        st.title("⚙️ Settings, Currency & Security")
        st.write(f"**User:** `{st.session_state.user['username']}` | **Privileges:** `{st.session_state.user['role'].upper()}`")

        with st.form("curr_save_form"):
            st.subheader("💱 Permanent Default Currency")
            st.caption("Once saved, this currency will automatically load every time you sign in.")
            currencies = ["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"]
            curr_idx = currencies.index(st.session_state.currency) if st.session_state.currency in currencies else 0
            saved_curr = st.selectbox("Select Default Currency", currencies, index=curr_idx)
            if st.form_submit_button("💾 Save Default Currency", use_container_width=True):
                run_query("UPDATE users SET preferred_currency=%s WHERE id=%s;", (saved_curr, uid))
                st.session_state.currency = saved_curr
                st.success(f"✅ Default currency permanently saved as {saved_curr}!")
                st.rerun()

        with st.form("pwd_form", clear_on_submit=True):
            st.subheader("🔒 Change Password")
            np1 = st.text_input("New Password", type="password")
            np2 = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if not np1 or np1 != np2:
                    st.error("Passwords must match and cannot be empty.")
                else:
                    run_query("UPDATE users SET password_hash=%s WHERE id=%s;", (hash_password(np1), uid))
                    st.success("Password changed successfully.")

    # ================= 9. ADMIN PANEL =================
    elif st.session_state.current_page == "Admin" and st.session_state.user['role'] == "admin":
        st.title("🔑 Master Admin Panel")
        u_df = fetch_df("SELECT id as \"ID\", username as \"User\", role as \"Role\", status as \"Status\", preferred_currency as \"Currency\" FROM users ORDER BY id ASC")
        st.dataframe(u_df, use_container_width=True, hide_index=True)

        other_users = u_df[u_df['User'] != 'admin']['User'].tolist()
        if other_users:
            with st.form("status_toggle_form"):
                target = st.selectbox("User", other_users)
                if st.form_submit_button("Toggle Active / Inactive Status", use_container_width=True):
                    current_status = run_query("SELECT status FROM users WHERE username=%s;", (target,), fetchone=True)[0]
                    next_status = "inactive" if current_status == "active" else "active"
                    run_query("UPDATE users SET status=%s WHERE username=%s;", (next_status, target))
                    st.success(f"Status for '{target}' changed to {next_status.upper()}.")
                    st.rerun()

        st.subheader("Broadcast System Notification")
        with st.form("bcast_form", clear_on_submit=True):
            bt = st.text_input("Title")
            bm = st.text_area("Message Body")
            if st.form_submit_button("Broadcast to All Registered Users", use_container_width=True) and bt.strip():
                all_ids = run_query("SELECT id FROM users;", fetch=True)
                for (usr_id,) in all_ids:
                    run_query("INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s);", (usr_id, bt.strip(), bm.strip()))
                st.success("Broadcast sent.")
